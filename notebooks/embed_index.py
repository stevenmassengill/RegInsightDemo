
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
    # First check SDK version and try to determine vector field parameters
    print(f"Azure Search SDK version: {sdk_version}")
    
    # Parameters that should work across versions
    dimensions_param = None
    dimension_param_name = None
    
    # Try to find the right way to specify dimensions based on SDK version
    try:
        from azure.search.documents.indexes.models import SearchField
        field = SearchField(name="test", type="Edm.String")
        
        # Check what parameters would work
        for param in ["vector_search_dimensions", "vector_dimensions", "dimensions"]:
            try:
                # Try setting this parameter and see if it works
                setattr(field, param, 1536)
                dimensions_param = 1536
                dimension_param_name = param
                print(f"Successfully used {param} parameter")
                break
            except (AttributeError, TypeError):
                continue
    except Exception as e:
        print(f"Field parameter check error: {e}")
        
    print(f"Will use dimension parameter: {dimension_param_name}")
        
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
            
            # First see if VectorField supports profile name
            try:
                vector_field = VectorField(
                    name="vector", 
                    vector_dimensions=1536,
                    vector_search_configuration="myHnsw",
                    vector_search_profile_name="myHnsw"  # Add profile name
                )
                print("Created VectorField with profile_name")
            except TypeError:
                # Fall back to basic constructor
                vector_field = VectorField(
                    name="vector", 
                    vector_dimensions=1536,
                    vector_search_configuration="myHnsw"
                )
                
                # Try to set profile name after construction
                try:
                    vector_field.vector_search_profile_name = "myHnsw"
                    print("Set vector_search_profile_name after construction")
                except AttributeError:
                    if hasattr(vector_field, 'additional_properties'):
                        vector_field.additional_properties["vectorSearchProfile"] = "myHnsw"
                        print("Set vectorSearchProfile via additional_properties") 
            
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String"),
                vector_field
            ]
            
            # Debug vector field properties
            vector_field = fields[2]
            print(f"Vector field type: {type(vector_field)}")
            
            # Display all properties
            if hasattr(vector_field, '__dict__'):
                print(f"Vector field properties: {vector_field.__dict__}")
            
            # Ensure vector dimensions and config are set
            try:
                print(f"Vector dimensions: {vector_field.vector_dimensions}")
                print(f"Vector search config: {vector_field.vector_search_configuration}")
            except AttributeError as e:
                print(f"Cannot access vector field attributes: {e}")
            
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
            # Create vector field with proper parameters
            from azure.search.documents.indexes.models import SearchIndex, SearchField, SearchFieldDataType
            
            # Create a vector field with parameters that work for our SDK version
            if dimension_param_name:
                # Create initial field
                vector_field = SearchField(
                    name="vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single)
                )
                
                # Set the proper dimension parameter based on what we detected
                setattr(vector_field, dimension_param_name, 1536)
                
                # Set needed vector search properties
                try:
                    # The "profile name" is what determines how the vector field is used in search
                    # Set vector_search_profile_name first (newer API requirement)
                    if hasattr(vector_field, "vector_search_profile_name"):
                        vector_field.vector_search_profile_name = "myHnsw"
                        print("Set vector_search_profile_name property")
                    
                    # Then set configuration
                    if hasattr(vector_field, "vector_search_configuration"):
                        vector_field.vector_search_configuration = "myHnsw"
                        print("Set vector_search_configuration property")
                except AttributeError as e:
                    print(f"Error setting vector properties: {e}")
                    # Try alternate approach with additional_properties
                    if hasattr(vector_field, 'additional_properties'):
                        vector_field.additional_properties["vectorSearchProfile"] = "myHnsw"
                        vector_field.additional_properties["vectorSearchConfiguration"] = "myHnsw"
                        print("Set vector search properties via additional_properties")
            else:
                # Fallback - create with best guess parameters
                vector_field = SearchField(
                    name="vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single)
                )
                
                # Add key properties via direct assignment if possible
                try:
                    if hasattr(vector_field, "vector_search_dimensions"):
                        vector_field.vector_search_dimensions = 1536
                    if hasattr(vector_field, "vector_search_profile_name"):
                        vector_field.vector_search_profile_name = "myHnsw"
                    if hasattr(vector_field, "vector_search_configuration"):
                        vector_field.vector_search_configuration = "myHnsw"
                    print("Set vector field properties via direct assignment")
                except AttributeError:
                    # Fall back to additional_properties
                    if hasattr(vector_field, 'additional_properties'):
                        vector_field.additional_properties["dimensions"] = 1536
                        vector_field.additional_properties["vectorSearchProfile"] = "myHnsw"
                        vector_field.additional_properties["vectorSearchConfiguration"] = "myHnsw"
                        print("Set vector field properties via additional_properties")
            
            fields = [
                SimpleField(name="id", type="Edm.String", key=True),
                SearchableField(name="content", type="Edm.String"),
                vector_field
            ]
            
            # Print debug info about the field
            print(f"Vector field details - Type: {type(vector_field)}")
            if hasattr(vector_field, "__dict__"):
                print(f"Vector field __dict__: {vector_field.__dict__}")
            if hasattr(vector_field, "additional_properties"):
                print(f"Vector field additional_properties: {vector_field.additional_properties}")
            
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
        
        # Make sure field properties are properly set for vector search
        for i, field in enumerate(fields):
            if field.name == "vector":
                print(f"Re-checking vector field at index {i}")
                
                # Try different approaches based on SDK version
                try:
                    # Verify parameters are set via direct access
                    if hasattr(field, "vector_search_dimensions"):
                        # Newer SDK uses vector_search_dimensions
                        if not field.vector_search_dimensions:
                            field.vector_search_dimensions = 1536
                            print("Set vector_search_dimensions directly")
                    elif hasattr(field, "dimensions"):
                        # Some SDKs use dimensions
                        if not field.dimensions:
                            field.dimensions = 1536
                            print("Set dimensions directly")
                    
                    # Similar for configuration
                    if hasattr(field, "vector_search_configuration"):
                        if not field.vector_search_configuration:
                            field.vector_search_configuration = "myHnsw"
                            print("Set vector_search_configuration directly")
                    
                    # Let's also try adding these to additional_properties
                    if hasattr(field, "additional_properties"):
                        field.additional_properties["vectorSearchDimensions"] = 1536
                        field.additional_properties["vectorSearchConfiguration"] = "myHnsw"
                        print("Added to additional_properties as well")
                
                except Exception as e:
                    print(f"Error setting vector field properties: {e}")
        
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
            
        # Last resort - try using raw JSON approach with SDK client
        if dimension_param_name is None:
            print("Trying raw JSON approach as last resort")
            try:
                # Create a minimal raw JSON definition that works with any SDK version
                raw_index = {
                    "name": INDEX_NAME,
                    "fields": [
                        {
                            "name": "id",
                            "type": "Edm.String",
                            "key": True,
                            "searchable": False
                        },
                        {
                            "name": "content",
                            "type": "Edm.String",
                            "searchable": True
                        },
                        {
                            "name": "vector",
                            "type": "Collection(Edm.Single)",
                            "searchable": False,
                            "dimensions": 1536,
                            "vectorSearchProfile": "myHnsw",
                            "vectorSearchConfiguration": "myHnsw"
                        }
                    ],
                    "vectorSearch": {
                        "algorithms": [
                            {
                                "name": "myHnsw",
                                "kind": "hnsw",
                                "parameters": {
                                    "m": 4,
                                    "efConstruction": 400
                                }
                            }
                        ]
                    }
                }
                
                print("Created raw JSON index definition")
                print(json.dumps(raw_index, indent=2))
                
                # Try alternate 'create_index' method if needed
                try:
                    import requests
                    
                    print(f"Will try direct REST API call as last resort")
                    # For debugging only - don't try this in production
                    api_version = "2023-11-01"
                    url = f"{SEARCH_ENDPOINT}/indexes?api-version={api_version}"
                    headers = {
                        "Content-Type": "application/json",
                        "api-key": SEARCH_KEY
                    }
                    
                    # Only print this for debugging 
                    print(f"Would make POST to: {url}")
                    
                    # Don't actually make the REST call within these changes
                    # response = requests.post(url, headers=headers, json=raw_index)
                    # print(f"REST API response: {response.status_code}, {response.text}")
                
                except Exception as e:
                    print(f"REST API attempt failed: {e}")
                    
            except Exception as e:
                print(f"Raw JSON approach failed: {e}")
            
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
