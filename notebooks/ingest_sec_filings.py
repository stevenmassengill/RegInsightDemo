
"""Ingest latest SEC filings from EDGAR and store in OneLake / local folder.

Requirements:
    pip install requests azure-storage-blob beautifulsoup4
"""

import os, requests, time, datetime, zipfile, io, re, json
from bs4 import BeautifulSoup

# ---- Config ----------------------------------------------------------------
FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=10-K&count=40&output=atom"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data/sec_filings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_feed():
    r = requests.get(FEED_URL, headers={"User-Agent": "RegInsightDemo/1.0"})
    r.raise_for_status()
    return r.text

def parse_entries(xml_text):
    soup = BeautifulSoup(xml_text, "lxml-xml")
    entries = []
    for entry in soup.find_all("entry"):
        accession = entry.accessionnumber.text.strip()
        cik = entry.ciknumber.text.strip()
        title = entry.title.text
        filing_href = entry.filinghref.text.strip()
        entries.append({"accession": accession, "cik": cik,
                        "title": title, "href": filing_href})
    return entries

def download_and_extract(entry):
    r = requests.get(entry["href"], headers={"User-Agent": "RegInsightDemo/1.0"})
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    # Find the 10-K/10-Q html file
    for name in z.namelist():
        if re.search(r"\.htm[l]?$", name, re.I):
            content = z.read(name)
            out_path = os.path.join(OUTPUT_DIR, f"{entry['accession']}.html")
            with open(out_path, "wb") as f:
                f.write(content)
            print(f"Saved {out_path}")
            return out_path
    return None

def main():
    feed_xml = fetch_feed()
    entries = parse_entries(feed_xml)
    for e in entries:
        outfile = os.path.join(OUTPUT_DIR, f"{e['accession']}.html")
        if not os.path.exists(outfile):
            try:
                download_and_extract(e)
            except Exception as ex:
                print("Error:", ex)

if __name__ == "__main__":
    main()
