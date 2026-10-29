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
