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
