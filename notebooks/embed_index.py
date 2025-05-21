
"""Chunk filings, create embeddings with Azure OpenAI, and push to Azure AI Search."""

import os, glob, json, re
from pathlib import Path
import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient, SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, VectorSearch, HnswVectorSearchAlgorithmConfiguration,
    VectorField
)
from tenacity import retry, wait_random_exponential, stop_after_attempt
import tiktoken

# ---- Config ----
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]
OPENAI_KEY = os.environ["OPENAI_KEY"]
DEPLOYMENT = os.getenv("EMBED_DEPLOYMENT", "text-embedding-3-large")
SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
SEARCH_KEY = os.environ["SEARCH_KEY"]
INDEX_NAME = os.getenv("SEARCH_INDEX", "sec-filings-index")
DATA_DIR = os.getenv("DATA_DIR", "./data/sec_filings")

# ---- Helpers ----
openai.api_type    = "azure"
openai.api_base    = OPENAI_ENDPOINT
openai.api_key     = OPENAI_KEY
openai.api_version = "2024-02-15-preview"   # or the API version you deployed
tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")

@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(6))
def embed(text):
    resp = openai.Embedding.create(
        engine=DEPLOYMENT,
        input=[text]
    )
    return resp["data"][0]["embedding"]

def chunk_text(text, max_tokens=800):
    words = text.split()
    chunk, chunks, tokens = [], [], 0
    for w in words:
        tokens += 1
        chunk.append(w)
        if tokens >= max_tokens:
            chunks.append(" ".join(chunk))
            chunk, tokens = [], 0
    if chunk:
        chunks.append(" ".join(chunk))
    return chunks

def build_index():
    index_client = SearchIndexClient(
        SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))
    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SearchableField(name="content", type="Edm.String"),
        VectorField(name="vector", vector_dimensions=1536,
                    vector_search_configuration="myHnsw")
    ]
    vector_search = VectorSearch(
        algorithms=[HnswVectorSearchAlgorithmConfiguration(
            name="myHnsw", parameters={"m":4, "efConstruction":400})]
    )
    index = SearchIndex(name=INDEX_NAME, fields=fields,
                        vector_search=vector_search)
    index_client.create_or_update_index(index)

def main():
    build_index()
    search_client = SearchClient(
        SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY)
    )
    docs = glob.glob(os.path.join(DATA_DIR, "*.html"))
    for html in docs:
        with open(html, "r", encoding="utf-8", errors="ignore") as f:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(f.read(), "html.parser")
            text = soup.get_text()  # extract text content
        for i, chunk in enumerate(chunk_text(text)):
            vector = embed(chunk)
            doc = {"id": f"{Path(html).stem}_{i}", "content": chunk,
                   "vector": vector}
            search_client.upload_documents([doc])
        print(f"Indexed {html}")

if __name__ == "__main__":
    main()
