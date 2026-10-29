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
