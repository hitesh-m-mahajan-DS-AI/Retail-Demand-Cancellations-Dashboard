# Project 11 - copyable files

Each authored file has its own block. The source bundle and generated charts/tables are saved beside this file; `prepare_data.py` rebuilds the source and `main.py` regenerates analytical outputs.

## Folder structure

```text
11-retail-demand-cancellations-dashboard/
  .gitattributes
  .gitignore
  README.md
  app.py
  data/SOURCE.md
  data/manifest.json
  data/retail_first_50000.csv.gz
  main.py
  outputs/daily.csv
  outputs/dashboard_preview.png
  outputs/data_audit.json
  outputs/excluded_rows.csv
  outputs/metrics.json
  outputs/pareto.csv
  outputs/products.csv
  outputs/recommendations.txt
  outputs/retail_analysis.png
  outputs/verification.md
  prepare_data.py
  requirements.txt
  test_dashboard.py
  PROJECT_FILES.md
```

## app.py

```python
"""Run with: python -m streamlit run app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st
from main import SOURCE_COLUMNS, load_data, prepare, analyze, filter_rows, recommendations

st.set_page_config(page_title="Retail Demand & Cancellations", layout="wide")
st.title("Retail Demand & Cancellations")
st.caption("Hitesh Milind Mahajan · UCI Online Retail · First 50,000 source rows only")


@st.cache_data
def get_data():
    return prepare(load_data())


audited = get_data()
eligible = audited.loc[audited["status"].eq("included")]
st.sidebar.header("Explore the subset")
countries = st.sidebar.multiselect("Countries", sorted(eligible["Country"].unique()), default=sorted(eligible["Country"].unique()))
minimum, maximum = eligible["InvoiceDate"].min().date(), eligible["InvoiceDate"].max().date()
dates = st.sidebar.date_input("Invoice dates", value=(minimum, maximum), min_value=minimum, max_value=maximum)
top_n = st.sidebar.slider("Products in ranking charts", 5, 20, 10)
st.sidebar.caption("Clear Countries to check an empty selection. All calculations update together.")
st.info("Teaching subset: 1 Dec 2010–9 Jan 2011. The final day is partial. Cancellation records are not confirmed physical returns or matched purchase outcomes.")
if len(dates) != 2:
    st.info("Choose both a start date and an end date.")
    st.stop()
filtered = filter_rows(eligible, countries, dates[0], dates[1])
if filtered.empty:
    st.warning("No eligible transaction lines match these filters. Select countries or widen the dates.")
    st.stop()
metrics, products, pareto, daily = analyze(filtered)
st.caption(f"Selected: {dates[0]:%d %b %Y}–{dates[1]:%d %b %Y} · {len(countries)} countries · {len(filtered):,} eligible lines")
cards = st.columns(4)
cards[0].metric("Observed sales units", f"{metrics['sales_units']:,}")
cards[1].metric("Gross recorded sales", f"£{metrics['gross_sales_gbp']:,.2f}")
cards[2].metric("Cancellation line share", f"{metrics['cancellation_line_share_pct']:.2f}%")
cards[3].metric("Net recorded value", f"£{metrics['net_recorded_value_gbp']:,.2f}")
st.caption(f"{metrics['cancellation_lines']:,} cancellation lines / {metrics['included_lines']:,} eligible sale + cancellation lines. Net value = positive sale value − cancellation value; this is not profit or recognized accounting revenue.")

left, right = st.columns(2)
with left:
    st.subheader("Which products drive sales?")
    top = products.sort_values(["sales_units", "StockCode"], ascending=[False, True]).head(top_n)
    fig = px.bar(top.iloc[::-1], x="sales_units", y="StockCode", orientation="h", hover_data=["description", "gross_gbp"], labels={"sales_units": "Observed positive sale units", "StockCode": "Product code"}, color_discrete_sequence=["#207d82"])
    fig.update_yaxes(type="category")
    st.plotly_chart(fig, width="stretch")
with right:
    st.subheader("Which products have cancellation units?")
    cancelled = products.loc[products["cancelled_units"].gt(0)].sort_values(["cancelled_units", "StockCode"], ascending=[False, True]).head(top_n)
    if cancelled.empty:
        st.info("No cancellation-marked product lines in this selection.")
    else:
        fig = px.bar(cancelled.iloc[::-1], x="cancelled_units", y="StockCode", orientation="h", hover_data=["description", "cancel_gbp"], labels={"cancelled_units": "Cancellation-marked units", "StockCode": "Product code"}, color_discrete_sequence=["#b96a38"])
        fig.update_yaxes(type="category")
        st.plotly_chart(fig, width="stretch")

st.subheader("How concentrated are observed sales units?")
if pareto.empty:
    st.info("No positive sale units in this selection; concentration is unavailable.")
else:
    st.write(f"**{metrics['products_to_80pct_units']:,} of {metrics['products_with_sales']:,} products ({metrics['product_share_to_80pct']:.2f}%)** cover at least 80% of observed sale units. The top 10 account for **{metrics['top10_units_share_pct']:.2f}%**.")
    fig = px.line(pareto, x="rank", y="cumulative_share", hover_data=["StockCode", "description"], labels={"rank": "Products ranked by sale units", "cumulative_share": "Cumulative share of sale units"}, color_discrete_sequence=["#207d82"])
    fig.add_hline(y=.8, line_dash="dash", line_color="#b96a38", annotation_text="80% of sale units", annotation_font_color="#b96a38")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.02])
    st.plotly_chart(fig, width="stretch")

st.subheader("Recorded activity over the selected dates")
fig = px.line(daily, x="date", y=["sales_units", "cancelled_units"], labels={"value": "Units", "date": "Invoice date", "variable": "Recorded activity"}, color_discrete_sequence=["#207d82", "#b96a38"])
st.plotly_chart(fig, width="stretch")
st.caption("Only observed invoice dates are shown. A gap is not proof of zero demand; the final day is partial. The source-row cutoff falls between invoices 540541 and 540542.")
st.subheader("Suggested investigations")
for text in recommendations(metrics, products, pareto):
    st.write(f"- {text}")

with st.expander("Data quality and metric definitions"):
    st.write("Quality counts below describe the full 50,000-row source subset before dashboard filters.")
    quality = audited["status"].value_counts().rename_axis("Row status").reset_index(name="Rows")
    st.dataframe(quality, hide_index=True, width="stretch")
    st.dataframe(audited[SOURCE_COLUMNS].isna().sum().rename_axis("Source column").reset_index(name="Missing rows"), hide_index=True, width="stretch")
    st.write("Rules: exclude later exact repeats of the eight source fields, invalid required fields, non-product-format codes, nonpositive prices and inconsistent quantity directions, in that order. Suspect repeats may represent legitimate lines; the raw source is preserved.")
    st.write("Product-format proxy: five digits with zero to two letters. This is not a verified catalogue. StockCode case is preserved; descriptions do not define grouping. Missing customer IDs are retained; missing descriptions use a display fallback.")
    st.write("Sales: non-C invoice with positive quantity and price. Cancellation: C-prefixed invoice with negative quantity and positive price. Cancellation line share = cancellation lines / all eligible lines. No sale-to-cancellation matching is attempted. GBP values use integer pennies.")
st.subheader("Filtered product summary")
st.dataframe(products[["StockCode", "description", "sales_units", "cancelled_units", "gross_gbp", "cancel_gbp", "net_recorded_gbp"]].sort_values("sales_units", ascending=False), hide_index=True, width="stretch")
st.download_button("Download filtered product summary", products.to_csv(index=False).encode("utf-8"), "filtered_products.csv", "text/csv")
```

## main.py

```python
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
```

## prepare_data.py

```python
"""Optional: rebuild the exact teaching subset from the public UCI workbook."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import urllib.request
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parent
URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
ARCHIVE_SHA = "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b"
WORKBOOK_SHA = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"


def prepare(archive_path=None):
    # Keep the full 22.6 MB workbook out of Git; normal runs use the bundled CSV.
    raw = Path(archive_path).read_bytes() if archive_path else urllib.request.urlopen(URL, timeout=120).read()
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Source archive changed; review it before rebuilding.")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        workbook = archive.read("Online Retail.xlsx")
    if hashlib.sha256(workbook).hexdigest() != WORKBOOK_SHA:
        raise ValueError("Unexpected source workbook.")
    source = pd.read_excel(io.BytesIO(workbook), engine="openpyxl", nrows=50001,
                         dtype={"InvoiceNo": "string", "StockCode": "string", "CustomerID": "string"})
    data = source.iloc[:50000].copy()
    data.insert(0, "source_row", range(1, len(data) + 1))
    target = ROOT / "data" / "retail_first_50000.csv.gz"
    target.parent.mkdir(exist_ok=True)
    csv = data.to_csv(index=False, lineterminator="\n", date_format="%Y-%m-%d %H:%M:%S").encode("utf-8")
    target.write_bytes(gzip.compress(csv, mtime=0))
    manifest = {"source_url": URL, "archive_sha256": ARCHIVE_SHA,
                "workbook_sha256": WORKBOOK_SHA, "subset_uncompressed_sha256": hashlib.sha256(csv).hexdigest(),
                "rows": len(data), "selection": "First 50,000 data rows in original workbook order; header excluded",
                "boundary_invoice": str(data.iloc[-1]["InvoiceNo"]),
                "next_source_invoice": str(source.iloc[50000]["InvoiceNo"]),
                "boundary_cuts_invoice": bool(data.iloc[-1]["InvoiceNo"] == source.iloc[50000]["InvoiceNo"])}
    (ROOT / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", help="Optional already downloaded official ZIP")
    prepare(parser.parse_args().archive)
```

## test_dashboard.py

```python
"""Small business-rule fixtures plus an actual Streamlit interaction check."""
import unittest
from datetime import date
import pandas as pd
from streamlit.testing.v1 import AppTest
from main import ROOT, load_data, prepare, analyze, filter_rows


def fixture():
    columns = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    rows = [
        ["100", "10000", "Example A", 2, "2010-12-01 23:59", 1.25, None, "UK"],
        ["101", "20000", "Example B", 1, "2010-12-02 09:00", 2.00, "1", "France"],
        ["C102", "10000", "Example A", -1, "2010-12-02 15:00", 1.25, "2", "UK"],
        ["103", "30000", None, 1, "2010-12-02 23:59", 3.00, None, "UK"],
        ["104", "POST", "Postage", 2, "2010-12-02 09:00", 5.00, "1", "UK"],
        ["105", "10000", "Unmarked negative", -2, "2010-12-02 09:00", 1.25, "1", "UK"],
        ["C106", "10000", "Positive cancellation", 2, "2010-12-02 09:00", 1.25, "1", "UK"],
        ["107", "10000", "Zero price", 1, "2010-12-02 09:00", 0, "1", "UK"],
    ]
    rows.append(rows[0].copy())
    data = pd.DataFrame(rows, columns=columns)
    data.insert(0, "source_row", range(1, len(data) + 1))
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"])
    return data


class BusinessChecks(unittest.TestCase):
    def test_hand_counted_signed_money_and_line_denominator(self):
        data = prepare(fixture())
        metrics, products, _, _ = analyze(data.loc[data["status"].eq("included")])
        self.assertEqual((metrics["included_lines"], metrics["sales_units"], metrics["cancelled_units"]), (4, 4, 1))
        self.assertEqual((metrics["gross_sales_gbp"], metrics["cancellation_value_gbp"], metrics["net_recorded_value_gbp"]), (7.5, 1.25, 6.25))
        self.assertEqual(metrics["cancellation_line_share_pct"], 25)
        self.assertEqual(data["status"].value_counts().to_dict(), {"included": 4, "ambiguous_quantity_direction": 2, "non_product_format": 1, "nonpositive_or_invalid_price": 1, "suspect_duplicate": 1})
        self.assertEqual(products.loc[products["StockCode"].eq("30000"), "description"].iloc[0], "Description unavailable")

    def test_inclusive_dates_and_country_filter(self):
        data = prepare(fixture())
        included = data.loc[data["status"].eq("included")]
        selected = filter_rows(included, ["UK"], date(2010, 12, 2), date(2010, 12, 2))
        self.assertEqual(selected["source_row"].tolist(), [3, 4])
        metrics, _, _, _ = analyze(selected)
        self.assertEqual(metrics["net_recorded_value_gbp"], 1.75)
        self.assertTrue(filter_rows(included, [], date(2010, 12, 1), date(2010, 12, 2)).empty)

    def test_empty_and_cancellation_only_views(self):
        included = prepare(fixture()).query("status == 'included'")
        empty, _, pareto, _ = analyze(included.iloc[:0])
        self.assertIsNone(empty["cancellation_line_share_pct"])
        self.assertIsNone(empty["product_share_to_80pct"])
        self.assertTrue(pareto.empty)
        cancelled, _, pareto, _ = analyze(included.loc[included["cancellation_marker"]])
        self.assertEqual(cancelled["cancellation_line_share_pct"], 100)
        self.assertEqual(cancelled["net_recorded_value_gbp"], -1.25)
        self.assertTrue(pareto.empty)

    def test_pareto_threshold_and_unmerged_sku_case(self):
        data = fixture().iloc[:2].copy()
        data["Quantity"] = [80, 20]
        data["StockCode"] = ["15056BL", "15056bl"]
        metrics, products, pareto, _ = analyze(prepare(data).query("status == 'included'"))
        self.assertEqual(metrics["products_to_80pct_units"], 1)
        self.assertEqual(metrics["product_share_to_80pct"], 50)
        self.assertEqual(len(products), 2)
        self.assertEqual(pareto.iloc[-1]["cumulative_share"], 1)

    def test_source_partition_and_reconciliations(self):
        raw = load_data()
        audited = prepare(raw)
        self.assertEqual(audited["status"].value_counts().sum(), 50000)
        included = audited.query("status == 'included'")
        metrics, products, pareto, daily = analyze(included)
        self.assertEqual(metrics["included_lines"], 48931)
        self.assertEqual(metrics["sales_lines"] + metrics["cancellation_lines"], 48931)
        self.assertEqual(int(products["sales_units"].sum()), metrics["sales_units"])
        self.assertEqual(int(daily["gross_pence"].sum()), 90396573)
        self.assertEqual(int(products["cancel_pence"].sum()), 2231189)
        self.assertEqual(int(included["CustomerID"].isna().sum()), 17489)
        self.assertTrue(pareto["cumulative_share"].is_monotonic_increasing)
        self.assertEqual(pareto.iloc[-1]["cumulative_share"], 1)

    def test_streamlit_default_country_filter_and_empty_state(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, "433,219")
        app.sidebar.multiselect[0].set_value(["France"]).run()
        self.assertEqual(len(app.exception), 0)
        included = prepare(load_data()).query("status == 'included'")
        expected, _, _, _ = analyze(included.loc[included["Country"].eq("France")])
        self.assertEqual(app.metric[0].value, f"{expected['sales_units']:,}")
        app.sidebar.multiselect[0].set_value([]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertIn("No eligible transaction lines", app.warning[0].value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

## requirements.txt

```text
pandas==3.1.0
openpyxl==3.1.5
streamlit==1.66.1
plotly==6.9.0
matplotlib==3.11.2
```

## .gitignore

```text
__pycache__/
*.py[cod]
.venv/
.env
.env.*
.streamlit/secrets.toml
.cache/
*.xlsx
*.zip
```

## .gitattributes

```text
data/*.gz binary
```

## data/SOURCE.md

````markdown
# Source and subset provenance

- Source: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail).
- Citation: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33.
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit the source when sharing this adaptation.
- Official no-login ZIP: https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip.
- Full source: 541,909 rows, eight columns, UK online retail transactions. This project does **not** summarize that full population.
- Transformation: read the first **50,000 data rows**, excluding the header, of `Online Retail.xlsx` in original sheet order. Append the traceability field `source_row` 1–50,000, retain all eight original fields, serialize dates as ISO timestamps and store as UTF-8 gzip-compressed CSV. There is no sampling seed because this is a deterministic prefix, not a random sample.
- The subset spans **2010-12-01 08:26:00 to 2011-01-09 15:13:00**. Source row 50,001 starts invoice **540542**, after subset invoice **540541**. The cutoff falls between invoices, but the final day is partial and the short, holiday-period prefix is not representative of a year.
- `manifest.json` records archive/workbook/uncompressed-subset SHA-256 values. Normal offline runs verify the decompressed CSV checksum. `prepare_data.py` optionally downloads/verifies the official archive and recreates the subset; it reads one extra source row only to check the boundary.
- CustomerID is a public source pseudonymous identifier and is not used for profiling or product metrics. Missing IDs are retained. Missing descriptions are not filled in the source; the app has a display fallback.
- Original StockCode case is preserved. Descriptions can vary; the first available description per filtered code is a display label, not the aggregation key.
- Product-format filtering, duplicate quarantine and transaction-direction rules are this project's analytical choices, not source corrections or a verified product catalogue. Every original row remains in the bundle; excluded-row reasons are exported separately.
- Prices are in sterling (GBP). All observed source prices resolve exactly to pennies. Integer-penny arithmetic is used for sums; changes with sub-penny prices fail for review.
- A C-prefixed invoice means cancellation according to UCI. Negative quantities without C are not automatically relabeled. No original-purchase matching, physical-return confirmation, profit, inventory levels or causal demand model is provided.
````

## data/manifest.json

```json
{
  "source_url": "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip",
  "archive_sha256": "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b",
  "workbook_sha256": "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d",
  "subset_uncompressed_sha256": "a236999d5fd3429de9a2726aa69bdf73ca83256cf9ed5284db9fe35756e0715a",
  "rows": 50000,
  "selection": "First 50,000 data rows in original workbook order; header excluded",
  "boundary_invoice": "540541",
  "next_source_invoice": "540542",
  "boundary_cuts_invoice": false
}
```

## README.md

````markdown
# Retail Demand & Cancellations Dashboard

An interactive retail analytics application that audits a bounded transaction prefix, separates positive sales from cancellation records, reconciles signed monetary values and measures product-unit concentration.

> Data boundary: results use the first 50,000 original workbook rows, not a representative full year. Cancellation records are not matched purchases or verified physical returns.

## Contents

- [Overview](#overview)
- [Dataset and data contract](#dataset-and-data-contract)
- [Architecture and components](#architecture-and-components)
- [Processing pipeline](#processing-pipeline)
- [Configuration and metric definitions](#configuration-and-metric-definitions)
- [Recorded results and evidence](#recorded-results-and-evidence)
- [Interpretation and operational use](#interpretation-and-operational-use)
- [Running locally](#running-locally)
- [Validation and reproducibility](#validation-and-reproducibility)
- [Project structure](#project-structure)
- [Technology stack](#technology-stack)
- [Limitations and next steps](#limitations-and-next-steps)
- [Further technical documentation](#further-technical-documentation)

## Overview

Which products drive **observed sales units and cancellation records**, and how concentrated is the recorded activity?

## Dataset and data contract

[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), a public UK online retailer dataset, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Citation: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. [DOI: 10.24432/C5BW33](https://doi.org/10.24432/C5BW33).

The original has **541,909 transaction lines**. This project uses only the **first 50,000 data rows in original workbook order**, bundled as a small compressed CSV for offline use. They span **1 December 2010, 08:26 to 9 January 2011, 15:13**. This deterministic teaching prefix is not a random or annual representative sample. The final day is partial; an extra source-row check confirms the cutoff falls between invoices 540541 and 540542.

| Column | Meaning and treatment |
|---|---|
| source_row | Added row number, 1–50,000, for tracing exclusions |
| InvoiceNo | Transaction identifier; C prefix identifies a cancellation record |
| StockCode | Original product/item code; grouping key, preserving case |
| Description | Display label; first available description per filtered SKU |
| Quantity | Signed units per line; direction must agree with invoice marker |
| InvoiceDate | Source transaction timestamp; inclusive calendar-date filtering |
| UnitPrice | Price per unit in GBP, converted exactly to integer pennies |
| CustomerID | Public source identifier; missing IDs are retained, not imputed |
| Country | Customer country in source; dashboard filter |

See [source provenance](data/SOURCE.md) and [checksums](data/manifest.json). The original XLSX/ZIP is not committed. `prepare_data.py` can optionally recreate the exact subset from the free, no-login UCI archive. Normal dashboard runs need no download.

## Architecture and components

```mermaid
flowchart LR
    N0["Bundled 50000-row UCI prefix"]
    N1["Exclusive row-status audit"]
    N2["Eligible sale and cancellation records"]
    N3["Integer-penny aggregates"]
    N4["Country and inclusive date filters"]
    N5["Product ranks, Pareto curve and exports"]
    N0 --> N1 --> N2 --> N3 --> N4 --> N5
```

| Component | Entry points or assets | Responsibility |
|---|---|---|
| [prepare_data.py](prepare_data.py) | Source preparation | Reproduce the bounded public-workbook prefix and its checksum manifest. |
| [main.py](main.py) | load_data / prepare | Verify source order and assign one mutually exclusive audit status per row. |
| [main.py](main.py) | filter_rows / analyze | Apply country/date filters, aggregate signed transaction values and calculate concentration. |
| [main.py](main.py) | recommendations / export / save_chart | Produce investigation priorities and auditable static evidence. |
| [app.py](app.py) | Streamlit interface | Expose synchronized KPIs, ranking controls, plots, quality context and filtered downloads. |
| [test_dashboard.py](test_dashboard.py) | Automated checks | Verify signed-money arithmetic, denominators, Pareto boundaries, filters and empty/cancellation-only views. |

## Processing pipeline

1. Verify the compressed source's decompressed checksum and its sequential 50,000 source-row IDs. Audit actual missingness rather than assuming the catalogue summary covers every field.
2. Assign each line one status, using the first matching reason: later exact repeat of the eight source fields, invalid required field, non-product-format code, nonpositive/invalid price, inconsistent quantity direction, or included. Suspect repeats are quarantined conservatively; they may be legitimate repeated lines. Preserve all raw records.
3. Use a disclosed **product-format proxy**: five digits followed by zero to two letters. This excludes postage/manual/fee/voucher and other nonstandard codes, but is not a verified merchandise catalogue. It retains codes such as `15056BL` and `15056bl` separately. Missing customer IDs do not exclude an otherwise eligible transaction.
4. Define sales as eligible non-C lines with positive units and price. Define cancellation records as eligible C lines with negative units and positive price. Report cancellation units as positive magnitudes. Do not match cancellation invoices to earlier purchases or reinterpret unmarked negatives as returns.
5. Sum quantity × price in integer pennies. **Gross recorded sales** are positive sale value. **Cancellation value** is the magnitude on cancellation lines. **Net recorded value = gross − cancellation value**. These are transaction summaries, not profit or recognized accounting revenue.
6. Group by StockCode, rank positive-sale products by units, and accumulate their units to find the smallest number covering at least 80%. Ties break by the original code. Products with cancellation records but no positive sales are outside this concentration denominator.
7. Apply country and inclusive date filters to every business summary, chart, download and recommendation together. Global quality counts remain explicitly labeled as the full subset. Show an empty-selection message and avoid inventing values for unavailable concentration.

**Cancellation line share = eligible C-negative lines / all eligible sale + cancellation lines.** It is neither a unit share nor the probability that an original order was cancelled. An invoice count is a distinct invoice count, not a line count. Only observed dates are plotted; gaps are not filled with invented zero demand.

## Configuration and metric definitions

| Measure or rule | Definition |
|---|---|
| Sale line | Eligible non-C invoice, positive quantity and positive price |
| Cancellation line | Eligible C-prefixed invoice, negative quantity and positive price |
| Gross recorded sales | Sum of positive sale-line values in integer pennies |
| Cancellation value | Magnitude of eligible cancellation-line value |
| Net recorded value | Gross recorded sales minus cancellation value |
| Cancellation line share | Cancellation lines divided by all eligible sale/cancellation lines |
| Concentration | Smallest ranked positive-sale SKU prefix covering at least 80% of sale units |
| Product-format proxy | Five digits followed by zero to two letters; code case is preserved |

The audit uses the first applicable reason, so exclusions reconcile without double counting. Missing customer identifiers remain eligible when other conditions pass. Quality totals describe the full raw prefix; filtered business summaries describe only the selected eligible records. An absent date is not filled with invented zero demand.

## Recorded results and evidence

These values were computed from the bundled 50,000-row prefix, using all countries and the full available date range.

| Metric | Measured result |
|---|---:|
| Raw source lines | 50,000 |
| Eligible product lines | **48,931** |
| Positive sale lines | 48,058 |
| Cancellation-marked eligible lines | 873 |
| Observed positive-sale invoices | 1,785 |
| Observed positive sale units | **433,219** |
| Cancellation-marked units | 17,635 |
| Gross recorded sales | **£903,965.73** |
| Cancellation value | £22,311.89 |
| Net recorded value | **£881,653.84** |
| Cancellation line share | **1.78%** (873 / 48,931) |
| Products with positive sales | 2,826 |
| Products needed to cover at least 80% of sale units | **623 (22.05%)** |
| Top 10 products' share of sale units | 8.66% |

Quality reconciliation: **50,000 = 48,931 included + 537 suspect duplicate extras + 237 non-product-format lines + 295 nonpositive-price lines**. These exclusion counts are exclusive and depend on the documented priority. No additional rows fall into the remaining exclusion categories after earlier rules. The raw subset contains 923 C-marked lines, 1,008 negative-quantity lines, 142 missing descriptions and **17,881 missing customer IDs**. Of the eligible lines, **17,489 anonymous-customer lines remain included**.

![Computed rankings, Pareto curve and dated activity for the full teaching subset](outputs/retail_analysis.png)

The leading sales-unit SKU is **84077: 5,820 units**. The leading cancellation-unit SKU is **84347: 9,375 units**, compared with 2,350 observed positive-sale units in this window. Cancellation units can exceed observed sales because records are not matched and the prefix omits earlier/later purchases. These counts do not establish a return rate.

Interactive verification with **France only** produced **583 eligible lines**, **6,771 sale units**, **£11,593.60 gross recorded sales**, **£11,530.75 net recorded value**, and **7 cancellation lines (1.20%)**. The empty-country selection displays a message with no stale KPI cards.

Saved evidence: [metrics](outputs/metrics.json), [data audit](outputs/data_audit.json), [products](outputs/products.csv), [Pareto ranks](outputs/pareto.csv), [daily summaries](outputs/daily.csv), [excluded source rows](outputs/excluded_rows.csv), [recommendations](outputs/recommendations.txt), [dashboard screenshot](outputs/dashboard_preview.png) and [verification record](outputs/verification.md). The dashboard also offers a filtered product CSV download.

## Interpretation and operational use

- **Review the main sales drivers:** SKU 84077 leads with 5,820 sale units. Check catalogue accuracy and availability using actual inventory data before making a replenishment decision.
- **Focus catalogue investigation:** 623 of 2,826 positive-sale products cover at least 80% of sale units. Review those items first, then validate the pattern over a longer, representative period. Do not assume a universal 80/20 split.
- **Investigate the cancellation concentration:** SKU 84347 has 9,375 cancellation-marked units. Inspect the source invoices, reasons and matching original transactions before treating them as physical returns or measuring a purchase cancellation rate.

## Running locally

Prerequisite: **Python 3.12+**, verified with Python 3.12. From the repository root, use these three commands in your Python environment:

```powershell
cd projects/11-retail-demand-cancellations-dashboard
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Optional, separate from launch: `python main.py` regenerates static evidence; `python -m unittest -v` runs six checks. `python prepare_data.py` downloads the original archive to memory and recreates the source bundle if required. This is unnecessary for normal use and requires an internet connection. Source checksum changes stop explicitly for review.

## Validation and reproducibility

The automated suite contains **6 tests**. It checks the following implementation boundaries:

Test implementation: [test_dashboard.py](test_dashboard.py).

- Hand counted signed money and line denominator.
- Inclusive dates and country filter.
- Empty and cancellation only views.
- Pareto threshold and unmerged sku case.
- Source partition and reconciliations.
- Streamlit default country filter and empty state.

From the project directory, run:

```powershell
python -m unittest -v
```

Recorded execution and any browser-review evidence is retained in [outputs/verification.md](outputs/verification.md). Reported figures correspond to saved execution artifacts; running a report generator can overwrite its generated outputs. Package requirements, source checksums and fixed parameters define the reproducibility boundary; elapsed times and some model/solver outputs can vary across environments.

## Project structure

```text
11-retail-demand-cancellations-dashboard/
  app.py
  main.py
  prepare_data.py
  PROJECT_FILES.md
  README.md
  requirements.txt
  test_dashboard.py
  data/
    Bundled inputs, provenance and prepared data
  outputs/
    Recorded metrics, audit files, tables and figures
```

Generated environments, database files, model artifacts and compiled assets follow the project's [.gitignore](.gitignore). The [copyable source bundle](PROJECT_FILES.md) mirrors the README and contains individual file blocks.

## Technology stack

Python, pandas, openpyxl for optional XLSX ingestion, Streamlit, Plotly, matplotlib for a static export, and standard-library unittest/gzip/hashlib/urllib/zipfile. Versions are pinned in [requirements.txt](requirements.txt). There is no model training or paid API.

## Limitations and next steps

- The prefix spans a short holiday period and part of January, with a partial final day. It cannot support annual totals, seasonality claims, month-to-month growth comparisons or representative customer behavior.
- Exact-repeat quarantine can exclude legitimate identical lines. The source has no unique line ID or documented duplicate semantics; all original rows and excluded-row references remain available for review.
- The SKU format is an analytical proxy. It can exclude genuine nonstandard items and cannot establish that every retained code is physical merchandise. An authoritative item catalogue would improve this decision.
- StockCode case is preserved without a canonical map. Descriptions may change and the displayed label can vary with filters. No category or warehouse stock level is inferred.
- Missing customer identifiers prevent complete customer analysis; anonymous transactions still contribute to product summaries. No missing original descriptions or identities are fabricated.
- C markers and signed quantities do not prove physical return, cancellation cause, link to an original purchase or financial recognition. Unmatched net recorded value can be negative for a product or filtered window.
- Observed sales reflect recorded transactions, not unmet demand, availability or a forecast. No inventory balance, purchase recommendation, causal intervention or savings was measured.
- The bundled checksum intentionally rejects arbitrary replacement data. A different dataset needs a reviewed schema, price/rounding policy and new provenance.

## Further technical documentation

- [Dataset attribution, licensing and source transformations](data/SOURCE.md)
- [Pinned Python dependencies](requirements.txt)
- [Recorded execution and verification evidence](outputs/verification.md)
- [Folder structure and individually copyable source files](PROJECT_FILES.md)

[Back to contents](#contents)
````

## outputs/verification.md

````markdown
# Verification record - Project 11

- Ran the original-source ingestion, audit, product/value summaries, Pareto calculation and saved figure export end to end on Windows/Python 3.12.
- Downloaded the official no-login UCI archive to ignored temporary storage. Verified original ZIP and XLSX checksums recorded in `data/manifest.json`. Read 50,001 rows only to check the boundary; bundled exactly the first 50,000 data rows and all eight source fields, plus source_row.
- Decompressed subset SHA-256: `a236999d5fd3429de9a2726aa69bdf73ca83256cf9ed5284db9fe35756e0715a`. Gzip bundle size: **842,474 bytes**. Full source workbook and archive are not project deliverables.
- Source row 50,000 belongs to invoice 540541; source row 50,001 starts invoice 540542. The cutoff does not split an invoice; the final observed date is partial.
- Reconciled **50,000 raw rows = 48,931 included + 537 suspect duplicate extras + 237 non-product-format + 295 nonpositive-price exclusions**. Reasons are exclusive and priority-dependent. Retained 17,489 eligible lines with missing customer IDs.
- Verified **48,058 positive sale lines + 873 cancellation lines = 48,931 eligible lines**. Cancellation line share is **1.784145%**; this is not an original-purchase cancellation probability.
- Independently summed original eligible quantity × price with Python Decimal, separately from the production integer-penny aggregation: **£903,965.73** gross; **£22,311.89** cancellation value; **£881,653.84** difference. Product and daily sums reconcile.
- Computed **433,219 sale units**, **17,635 cancellation-marked units**, **2,826 products with positive sales**, and **623 products covering at least 80% of sale units (22.0453% of those products)**. Top-ten unit share: **8.6619%**.
- Six unittest checks passed in **1.274 seconds**: hand-counted signed quantities/penny totals/line denominator, inclusive dates/country filtering, empty/cancellation-only results, Pareto 80% equality/SKU case separation, source partition/reconciliation, and real Streamlit default/France/empty-selection interactions.
- Streamlit's Windows AppTest runner required localhost sockets. The sandbox blocked that socket initialization; rerunning with local-network access completed successfully. This is a test-environment requirement, not an application exception.
- Launched the server bound to **127.0.0.1** only, with usage collection disabled, and reviewed the rendered dashboard in the browser. Confirmed all-country KPIs, actual product/cancellation charts, Pareto view and empty-country message.
- Manually selected France and independently reconciled **583 eligible lines**, **6,771 sale units**, **£11,593.60** gross, **£11,530.75** net recorded value, and **7 cancellation lines (1.20069%)**. Restored all-country defaults after the check.
- Visually inspected the static three-panel PNG and dashboard rendering, including the narrow viewport. Saved the Pareto dashboard screenshot; adjusted the 80% reference line for dark-background contrast.
- Reran exports from the portfolio root: all **seven structured outputs** (four CSVs, two JSONs, one text recommendation file) had identical SHA-256 hashes. Final measured analysis/export runtime: **0.823 seconds**, excluding interpreter startup/imports; runtimes vary.
- Results apply only to the disclosed prefix and analytical rules. No physical returns, original-purchase outcomes, complete year, stock levels, profit, causal demand, forecast or savings were inferred.
````
