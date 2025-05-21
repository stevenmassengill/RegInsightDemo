
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
            
            # Create algorithm configuration with mandatory kind attribute
            algo_config = VectorSearchAlgorithmConfiguration(name="myHnsw")
            
            # Explicitly set kind using dictionary approach to avoid attribute access issues
            algo_config.__dict__["kind"] = "hnsw"
            
            vector_search = VectorSearch(algorithms=[algo_config])
            
            # Try to print all available attributes and their values
            print("Available algorithm attributes:", dir(algo_config))
            
            # For debugging only
            if hasattr(algo_config, "__dict__"):
                print("Algorithm config dict:", algo_config.__dict__)
                
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
            
            # Create algorithm configuration with mandatory kind attribute
            algo_config = VectorSearchAlgorithmConfiguration(name="myHnsw")
            
            # Explicitly set kind using dictionary approach to avoid attribute access issues
            algo_config.__dict__["kind"] = "hnsw"
            
            vector_search = VectorSearch(algorithms=[algo_config])
            
            # Try to print all available attributes and their values
            print("Available algorithm attributes:", dir(algo_config))
            
            # For debugging only
            if hasattr(algo_config, "__dict__"):
                print("Algorithm config dict:", algo_config.__dict__)

        # Create a minimal, simplified vector search configuration that works with most SDK versions
        from azure.search.documents.indexes.models import VectorSearch, VectorSearchAlgorithmConfiguration
        
        # Create a fresh, minimal configuration
        simplified_algo = VectorSearchAlgorithmConfiguration(name="myHnsw")
        
        # Force the kind property to be set directly in the _attribute_map
        if hasattr(simplified_algo, '_attribute_map') and isinstance(simplified_algo._attribute_map, dict):
            print("Using _attribute_map approach")
            if 'kind' in simplified_algo._attribute_map:
                simplified_algo.kind = "hnsw"
        # Direct dict assignment as backup
        elif hasattr(simplified_algo, '__dict__'):
            simplified_algo.__dict__["kind"] = "hnsw"
        
        simplified_vector_search = VectorSearch(algorithms=[simplified_algo])
        
        # Create the index with simplified vector search
        index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=simplified_vector_search)
        
        # Try to serialize the configuration to see what's actually being sent
        try:
            import json
            from msrest.serialization import Model
            if isinstance(index, Model) and hasattr(index, "serialize"):
                serialized = index.serialize()
                print("\nSerialized index configuration:")
                print(json.dumps(serialized, indent=2))
        except Exception as e:
            print(f"Serialization error: {e}")
            
        # Print detailed information about our configuration
        print(f"Creating index with fields: {[f.name for f in fields]}")
        
        # Debug vector search configuration
        print(f"Vector search configuration name: {vector_search.algorithms[0].name}")
        
        # Use try/except for getting kind as it might be accessed differently
        try:
            kind = vector_search.algorithms[0].kind
            print(f"Kind attribute value: {kind}")
        except Exception:
            try:
                # Try dictionary access if attribute access fails
                kind = vector_search.algorithms[0].__dict__.get("kind")
                print(f"Kind via __dict__: {kind}")
            except Exception as e:
                print(f"Cannot access kind: {e}")
        
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
