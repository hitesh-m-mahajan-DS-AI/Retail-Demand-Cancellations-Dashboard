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
