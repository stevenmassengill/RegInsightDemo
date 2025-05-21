
"""Chunk filings, create embeddings with Azure OpenAI, and push to Azure AI Search."""

import os, glob, json, re
from pathlib import Path
import openai
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
try:
    # Use importlib.metadata (modern approach) instead of deprecated pkg_resources
    import importlib.metadata
    get_version = lambda pkg: importlib.metadata.version(pkg)
    from packaging.version import parse as parse_version
except ImportError:
    # Fallback to pkg_resources for older Python versions
    from pkg_resources import get_distribution, parse_version
    get_version = lambda pkg: get_distribution(pkg).version

try:
    sdk_version = get_version("azure-search-documents")
except Exception:
    sdk_version = "unknown"

MIN_VERSION = "11.4.0"
if sdk_version == "unknown" or parse_version(sdk_version) < parse_version(MIN_VERSION):
    raise RuntimeError(
        f"azure-search-documents>={MIN_VERSION} is required for vector search (found {sdk_version}). "
        "Run 'pip install --upgrade azure-search-documents' and retry."
    )
# VectorField is only available in newer versions of the Azure Search SDK. When
# running against an older version, fall back to using `SearchField` with the
# appropriate vector search parameters.
try:
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        VectorSearch,
        VectorSearchAlgorithmConfiguration,
        VectorField,
    )
except ImportError:  # pragma: no cover - support older SDKs
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        VectorSearch,
        VectorSearchAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        HnswParameters,
    )

    def VectorField(name, vector_dimensions, vector_search_configuration):
        return SearchField(
            name=name,
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=vector_dimensions,
            vector_search_configuration=vector_search_configuration,
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
    
    try:
        # Import all necessary models directly here to ensure we get the right ones
        # for the SDK version we're actually using
        try:
            from azure.search.documents.indexes.models import (
                SearchIndex,
                SimpleField,
                SearchableField,
                VectorSearch,
                VectorSearchAlgorithmConfiguration,
                VectorField,
            )
            
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String"),
                VectorField(
                    name="vector", 
                    vector_dimensions=1536,
                    vector_search_configuration="myHnsw"
                )
            ]
            
            vector_search = VectorSearch(
                algorithms=[
                    VectorSearchAlgorithmConfiguration(
                        name="myHnsw",
                        kind="hnsw",
                    )
                ]
            )
            # Try to set parameters in a way that works with this SDK version
            try:
                vector_search.algorithms[0].hnsw_parameters.m = 4
                vector_search.algorithms[0].hnsw_parameters.ef_construction = 400
            except (AttributeError, TypeError):
                # Different SDK versions have different parameter structures
                print("Using alternative parameter approach")
                
        except (ImportError, AttributeError):
            # Older SDK version
            from azure.search.documents.indexes.models import (
                SearchIndex,
                SimpleField,
                SearchableField,
                VectorSearch,
                VectorSearchAlgorithmConfiguration,
                SearchField,
                SearchFieldDataType,
            )
            
            print("Using SearchField-based approach")
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String"),
                SearchField(
                    name="vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    dimensions=1536,
                    vector_search_configuration="myHnsw"
                )
            ]
            
            vector_search = VectorSearch(
                algorithms=[
                    VectorSearchAlgorithmConfiguration(
                        name="myHnsw",
                        kind="hnsw"
                    )
                ]
            )
            # Only set attributes that are known to exist
            algo = vector_search.algorithms[0]
            try:
                if hasattr(algo, 'hnsw_parameters'):
                    algo.hnsw_parameters.m = 4
                    algo.hnsw_parameters.ef_construction = 400
            except (AttributeError, TypeError):
                print("Warning: Could not set HNSW parameters")

        index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
        
        # Print detailed information about our configuration
        print(f"Creating index with fields: {[f.name for f in fields]}")
        print(f"Vector search configuration: {vector_search.algorithms[0].name}, Kind: {vector_search.algorithms[0].kind}")
        
        index_client.create_or_update_index(index)
        print(f"Successfully created index '{INDEX_NAME}'")
    except Exception as e:
        print(f"Error creating index: {str(e)}")
        import traceback
        traceback.print_exc()

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
