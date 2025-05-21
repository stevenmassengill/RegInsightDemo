
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
    soup = BeautifulSoup(xml_text, "xml")  # Use built-in xml parser instead of lxml-xml
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
    # Proper headers for SEC.gov
    headers = {
        "User-Agent": "RegInsightDemo/1.0 (your.email@example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml",
        "Host": "www.sec.gov"
    }
    
    # Add a slight delay to avoid rate limiting
    import time, random
    time.sleep(random.uniform(1.0, 3.0))
    
    r = requests.get(entry["href"], headers=headers)
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
    import random
    import time
    
    # Sample 10-K filings - added more to increase chances of success
    samples = [
        {"accession": "0000320193-23-000077", "cik": "0000320193", 
         "title": "APPLE INC (0000320193) 10-K", 
         "content": """<html><head><title>Apple Inc. Form 10-K</title></head>
         <body><h1>Apple Inc. 10-K Sample Document</h1>
         <p>This is a sample 10-K filing for Apple Inc. The actual filing would contain detailed financial information,
         business description, risk factors, management discussion, and other required disclosures. This sample is provided
         for demonstration purposes only.</p>
         <h2>Business Overview</h2>
         <p>Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories,
         and sells a variety of related services. The Company's products include iPhone, Mac, iPad, AirPods, Apple TV, Apple Watch,
         and HomePod. Its services include Apple Music, Apple Pay, and iCloud.</p>
         </body></html>"""
        },
        {"accession": "0001326801-23-000022", "cik": "0001326801", 
         "title": "META PLATFORMS INC (0001326801) 10-K",
         "content": """<html><head><title>Meta Platforms Inc. Form 10-K</title></head>
         <body><h1>Meta Platforms Inc. 10-K Sample Document</h1>
         <p>This is a sample 10-K filing for Meta Platforms Inc. The actual filing would contain detailed financial information,
         business description, risk factors, management discussion, and other required disclosures. This sample is provided
         for demonstration purposes only.</p>
         <h2>Business Overview</h2>
         <p>Meta Platforms, Inc. builds technologies that help people connect, find communities, and grow businesses. The company's
         apps and services include Facebook, Instagram, Messenger, WhatsApp, and Meta Quest. Meta is moving beyond 2D screens toward
         immersive experiences like augmented and virtual reality to help build the metaverse.</p>
         </body></html>"""
        },
        {"accession": "0001652044-23-000071", "cik": "0001652044", 
         "title": "ALPHABET INC (0001652044) 10-K",
         "content": """<html><head><title>Alphabet Inc. Form 10-K</title></head>
         <body><h1>Alphabet Inc. 10-K Sample Document</h1>
         <p>This is a sample 10-K filing for Alphabet Inc. The actual filing would contain detailed financial information,
         business description, risk factors, management discussion, and other required disclosures. This sample is provided
         for demonstration purposes only.</p>
         <h2>Business Overview</h2>
         <p>Alphabet Inc. is a holding company, with Google as its largest subsidiary. Google was founded in 1998 by Larry Page
         and Sergey Brin. The company is known for its search engine Google Search, as well as products like Gmail, Google Maps,
         Google Chrome, and YouTube. Alphabet's Other Bets portfolio includes companies like Waymo, Verily, and Wing.</p>
         </body></html>"""
        }
    ]
    
    # Create some local sample files directly instead of fetching from SEC
    for e in samples:
        outfile = os.path.join(OUTPUT_DIR, f"{e['accession']}.html")
        if not os.path.exists(outfile):
            try:
                if "content" in e:
                    # Use provided sample content
                    with open(outfile, "w", encoding="utf-8") as f:
                        f.write(e["content"])
                    print(f"Created sample file {outfile}")
                else:
                    # Try to fetch from SEC with retry logic
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # Add random delay to avoid rate limiting
                            delay = random.uniform(2.0, 5.0)
                            print(f"Waiting {delay:.1f} seconds before request...")
                            time.sleep(delay)
                            
                            # Construct URL for index page
                            url = f"https://www.sec.gov/Archives/edgar/data/{e['cik']}/{e['accession'].replace('-', '')}/{e['accession']}-index.htm"
                            print(f"Fetching: {url}")
                            
                            # Get the filing page with proper headers
                            headers = {
                                "User-Agent": "RegInsightDemo/1.0 (your.email@example.com)",
                                "Accept": "text/html,application/xhtml+xml,application/xml",
                                "Host": "www.sec.gov"
                            }
                            r = requests.get(url, headers=headers)
                            r.raise_for_status()
                            
                            soup = BeautifulSoup(r.text, "html.parser")
                            
                            # Find the actual 10-K document link
                            doc_url = None
                            for link in soup.find_all("a"):
                                href = link.get("href", "")
                                if ".htm" in href.lower() and "/Archives/" in href:
                                    if any(x in link.text for x in ["10-K", "10K"]):
                                        doc_url = "https://www.sec.gov" + href
                                        break
                            
                            if not doc_url:
                                print("No 10-K link found, trying alternate approach...")
                                for table in soup.find_all("table"):
                                    for row in table.find_all("tr"):
                                        cols = row.find_all("td")
                                        if len(cols) >= 2:
                                            if "10-K" in cols[0].text:
                                                link = cols[1].find("a")
                                                if link and link.get("href"):
                                                    doc_url = "https://www.sec.gov" + link.get("href")
                                                    break
                            
                            if doc_url:
                                print(f"Found 10-K link: {doc_url}")
                                # Wait before next request
                                time.sleep(random.uniform(1.0, 3.0))
                                
                                # Download the actual 10-K HTML
                                doc_resp = requests.get(doc_url, headers=headers)
                                doc_resp.raise_for_status()
                                
                                # Save the HTML content
                                with open(outfile, "wb") as f:
                                    f.write(doc_resp.content)
                                print(f"Saved {outfile}")
                                break
                            else:
                                print("Could not find 10-K document link")
                                
                        except Exception as ex:
                            print(f"Attempt {attempt+1}/{max_retries} failed: {ex}")
                            if attempt == max_retries - 1:
                                raise
                            time.sleep(random.uniform(5.0, 10.0))  # Longer delay between retries
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
