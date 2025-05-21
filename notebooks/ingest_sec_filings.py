
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
    r = requests.get(FEED_URL, headers={"User-Agent": "RegInsightDemo/1.0 (your.email@example.com)"})
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
    print(f"Warning: No matching HTML file found in the zip for accession {entry['accession']}")
    return None

def fetch_sample_filings():
    """Fallback function to get sample 10-K filings if SEC API fails"""
    print("Using fallback method to download sample filings...")
    
    # Sample 10-K filings (Apple and Microsoft)
    samples = [
        {"accession": "0000320193-23-000077", "cik": "0000320193", 
         "href": "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/0000320193-23-000077-index.htm",
         "title": "APPLE INC (0000320193) 10-K"},
        {"accession": "0001564590-23-024301", "cik": "0000789019", 
         "href": "https://www.sec.gov/Archives/edgar/data/789019/000156459023024301/0001564590-23-024301-index.htm",
         "title": "MICROSOFT CORP (0000789019) 10-K"}
    ]
    
    for e in samples:
        outfile = os.path.join(OUTPUT_DIR, f"{e['accession']}.html")
        if not os.path.exists(outfile):
            try:
                # Get the filing page
                r = requests.get(e["href"], headers={"User-Agent": "RegInsightDemo/1.0 (your.email@example.com)"})
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                
                # Find the actual 10-K document link
                for link in soup.find_all("a"):
                    if link.text and ("10-K" in link.text or ".htm" in link.text.lower()) and "10-K" in link.get("href", ""):
                        doc_url = "https://www.sec.gov" + link.get("href")
                        print(f"Found 10-K link: {doc_url}")
                        
                        # Download the actual 10-K HTML
                        doc_resp = requests.get(doc_url, headers={"User-Agent": "RegInsightDemo/1.0 (your.email@example.com)"})
                        doc_resp.raise_for_status()
                        
                        # Save the HTML content
                        with open(outfile, "wb") as f:
                            f.write(doc_resp.content)
                        print(f"Saved {outfile}")
                        break
            except Exception as ex:
                print(f"Error with sample {e['accession']}: {ex}")

def main():
    try:
        feed_xml = fetch_feed()
        entries = parse_entries(feed_xml)
        for e in entries:
            outfile = os.path.join(OUTPUT_DIR, f"{e['accession']}.html")
            if not os.path.exists(outfile):
                try:
                    download_and_extract(e)
                except Exception as ex:
                    print("Error:", ex)
    except Exception as ex:
        print(f"Error fetching from SEC API: {ex}")
        print("Falling back to sample filings...")
        fetch_sample_filings()

if __name__ == "__main__":
    main()
