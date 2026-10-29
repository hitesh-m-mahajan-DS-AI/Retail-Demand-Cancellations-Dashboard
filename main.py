"""Audit and summarize the fixed retail subset. Run directly to export evidence."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import math
import time
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def load_data():
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    raw = gzip.decompress((ROOT / "data/retail_first_50000.csv.gz").read_bytes())
    if hashlib.sha256(raw).hexdigest() != manifest["subset_uncompressed_sha256"]:
        raise ValueError("Bundled data changed; restore the source or audit a new version.")
    data = pd.read_csv(io.BytesIO(raw), dtype={name: "string" for name in ["InvoiceNo", "StockCode", "Description", "CustomerID", "Country"]})
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    if len(data) != 50000 or data["source_row"].tolist() != list(range(1, 50001)):
        raise ValueError("Expected exactly the first 50,000 sequential source rows.")
    return data


def prepare(data):
    """Assign one exclusion reason to each row; preserve all originals for audit."""
    data = data.copy()
    data["cancellation_marker"] = data["InvoiceNo"].str.upper().str.startswith("C", na=False)
    # A format proxy, not a verified product catalogue: excludes fees/manual codes.
    product_format = data["StockCode"].str.fullmatch(r"[0-9]{5}[A-Za-z]{0,2}", na=False)
    duplicate = data.duplicated(subset=SOURCE_COLUMNS, keep="first")
    numeric_ok = data["Quantity"].map(lambda value: pd.notna(value) and math.isfinite(value) and value == int(value))
    price_ok = data["UnitPrice"].map(lambda value: pd.notna(value) and math.isfinite(value) and value > 0)
    required = data[["InvoiceNo", "StockCode", "InvoiceDate", "Country"]].notna().all(axis=1) & numeric_ok
    direction_ok = ((data["cancellation_marker"] & data["Quantity"].lt(0)) |
                    (~data["cancellation_marker"] & data["Quantity"].gt(0)))
    data["status"] = "included"
    # First matching reason wins; counts form an exclusive, reconcilable partition.
    rules = [(duplicate, "suspect_duplicate"), (~required, "invalid_required_field"),
             (~product_format, "non_product_format"), (~price_ok, "nonpositive_or_invalid_price"),
             (~direction_ok, "ambiguous_quantity_direction")]
    for mask, reason in rules:
        data.loc[data["status"].eq("included") & mask, "status"] = reason
    # GBP prices in this source are exact to pennies; reject sub-penny changes.
    rounded = (data["UnitPrice"] * 100).round()
    if ((data["UnitPrice"] * 100 - rounded).abs() > 1e-7).any():
        raise ValueError("Sub-penny prices require an explicit rounding policy.")
    data["unit_price_pence"] = rounded.astype("Int64")
    return data


def analyze(included):
    """All views and filters share these definitions and integer-penny arithmetic."""
    data = included.copy()
    sale = ~data["cancellation_marker"]
    data["sales_units"] = data["Quantity"].where(sale, 0)
    data["cancelled_units"] = (-data["Quantity"]).where(~sale, 0)
    data["gross_pence"] = data["sales_units"] * data["unit_price_pence"]
    data["cancel_pence"] = data["cancelled_units"] * data["unit_price_pence"]
    products = data.groupby("StockCode", sort=True).agg(
        sales_units=("sales_units", "sum"), cancelled_units=("cancelled_units", "sum"),
        gross_pence=("gross_pence", "sum"), cancel_pence=("cancel_pence", "sum"),
        observed_lines=("source_row", "size")).reset_index()
    # Labels are only display aids; grouping always uses the original SKU code.
    labels = data.dropna(subset=["Description"]).drop_duplicates("StockCode").set_index("StockCode")["Description"]
    products["description"] = products["StockCode"].map(labels).fillna("Description unavailable")
    products["gross_gbp"] = products["gross_pence"] / 100
    products["cancel_gbp"] = products["cancel_pence"] / 100
    products["net_recorded_gbp"] = (products["gross_pence"] - products["cancel_pence"]) / 100
    # Only positive-sale products belong in the demand-concentration denominator.
    pareto = products.loc[products["sales_units"].gt(0)].sort_values(
        ["sales_units", "StockCode"], ascending=[False, True]).copy()
    total_units = int(pareto["sales_units"].sum())
    pareto["rank"] = range(1, len(pareto) + 1)
    pareto["cumulative_units"] = pareto["sales_units"].cumsum()
    pareto["cumulative_share"] = pareto["cumulative_units"] / total_units if total_units else 0.0
    to_80 = int((pareto["cumulative_units"] * 5 < total_units * 4).sum() + 1) if total_units else 0
    # Aggregate only observed dates. Missing dates are not asserted to be zero sales.
    data["date"] = data["InvoiceDate"].dt.date
    daily = data.groupby("date")[["sales_units", "cancelled_units", "gross_pence", "cancel_pence"]].sum().reset_index()
    gross, cancel = int(data["gross_pence"].sum()), int(data["cancel_pence"].sum())
    cancel_lines = int((~sale).sum())
    metrics = {"included_lines": len(data), "sales_lines": int(sale.sum()), "cancellation_lines": cancel_lines,
               "observed_sale_invoices": int(data.loc[sale, "InvoiceNo"].nunique()),
               "sales_units": total_units, "cancelled_units": int(data["cancelled_units"].sum()),
               "gross_sales_gbp": gross / 100, "cancellation_value_gbp": cancel / 100,
               "net_recorded_value_gbp": (gross - cancel) / 100,
               "cancellation_line_share_pct": 100 * cancel_lines / len(data) if len(data) else None,
               "products_with_sales": len(pareto), "products_to_80pct_units": to_80,
               "product_share_to_80pct": 100 * to_80 / len(pareto) if len(pareto) else None,
               "top10_units_share_pct": 100 * int(pareto.head(10)["sales_units"].sum()) / total_units if total_units else None}
    return metrics, products, pareto, daily


def filter_rows(data, countries, start, end):
    return data.loc[data["Country"].isin(countries) & data["InvoiceDate"].dt.date.between(start, end)].copy()


def recommendations(metrics, products, pareto):
    if not metrics["included_lines"]:
        return ["No eligible records match these filters. Widen the date or country selection."]
    leader = pareto.iloc[0] if len(pareto) else None
    cancellations = products.sort_values(["cancelled_units", "StockCode"], ascending=[False, True])
    result = []
    if leader is not None:
        result.append(f"Review availability and listing accuracy for SKU {leader['StockCode']} ({int(leader['sales_units']):,} observed sales units). These transactions do not reveal stock on hand.")
        result.append(f"Prioritize a catalogue review of the {metrics['products_to_80pct_units']:,} SKUs covering at least 80% of observed sales units; validate on a longer period before changing replenishment policy.")
    if len(cancellations) and cancellations.iloc[0]["cancelled_units"] > 0:
        row = cancellations.iloc[0]
        result.append(f"Investigate cancellation records for SKU {row['StockCode']} ({int(row['cancelled_units']):,} units); review causes and original invoices before drawing return-rate conclusions.")
    else:
        result.append("No eligible cancellation-marked lines occur in this selection; this does not establish a zero cancellation rate for original purchases.")
    return result


def export():
    started = time.perf_counter()
    raw = load_data()
    audited = prepare(raw)
    included = audited.loc[audited["status"].eq("included")]
    metrics, products, pareto, daily = analyze(included)
    audit = {"raw_rows": len(raw), "source_date_min": str(raw["InvoiceDate"].min()),
             "source_date_max": str(raw["InvoiceDate"].max()), "missing_by_column": raw[SOURCE_COLUMNS].isna().sum().to_dict(),
             "suspect_duplicate_extras": int(raw.duplicated(SOURCE_COLUMNS).sum()),
             "raw_cancellation_marked_lines": int(audited["cancellation_marker"].sum()),
             "raw_negative_quantity_lines": int(raw["Quantity"].lt(0).sum()),
             "exclusive_status_counts": audited["status"].value_counts().to_dict(),
             "included_missing_customer_id": int(included["CustomerID"].isna().sum()),
             "included_missing_description": int(included["Description"].isna().sum()),
             "boundary_cuts_invoice": json.loads((ROOT / "data/manifest.json").read_text())["boundary_cuts_invoice"],
             "last_date_is_partial": True}
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    for name, frame in [("products", products), ("pareto", pareto), ("daily", daily)]:
        frame.to_csv(output / f"{name}.csv", index=False, lineterminator="\n")
    audited.loc[~audited["status"].eq("included"), ["source_row", "InvoiceNo", "StockCode", "Quantity", "UnitPrice", "status"]].to_csv(output / "excluded_rows.csv", index=False, lineterminator="\n")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (output / "data_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "recommendations.txt").write_text("\n\n".join(recommendations(metrics, products, pareto)) + "\n")
    save_chart(products, pareto, daily, output)
    print(json.dumps(metrics, indent=2))
    print(json.dumps(audit, indent=2))
    print(f"Analysis/export seconds: {time.perf_counter() - started:.3f}")


def save_chart(products, pareto, daily, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), layout="constrained")
    top = products.sort_values(["sales_units", "StockCode"], ascending=[False, True]).head(10).iloc[::-1]
    axes[0].barh(top["StockCode"], top["sales_units"], color="#207d82")
    axes[0].set(title="Top 10 SKUs by observed sales units", xlabel="Positive sale units", ylabel="Original StockCode")
    axes[1].plot(pareto["rank"], 100 * pareto["cumulative_share"], color="#207d82")
    axes[1].axhline(80, color="#b96a38", linestyle="--", label="80% of sale units")
    axes[1].set(title="Sales-unit concentration", xlabel="Products ranked by sale units", ylabel="Cumulative share (%)", ylim=(0, 102))
    axes[1].legend()
    axes[2].plot(pd.to_datetime(daily["date"]), daily["sales_units"], color="#207d82", marker=".", label="Sale units")
    axes[2].plot(pd.to_datetime(daily["date"]), daily["cancelled_units"], color="#b96a38", marker=".", label="Cancellation units")
    axes[2].set(title="Recorded activity by observed date", ylabel="Units")
    axes[2].tick_params(axis="x", rotation=45)
    axes[2].legend()
    fig.suptitle("UCI Online Retail: first 50,000 source rows only; audited product lines", fontsize=14)
    fig.savefig(output / "retail_analysis.png", dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    export()
