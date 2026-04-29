import qdrant_client
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from uuid import uuid4
from app.core.config import settings

class VectorDBService:
    def __init__(self):
        # Initialize Qdrant client
        # Handle both remote and local modes
        if settings.QDRANT_HOST.startswith("./") or settings.QDRANT_HOST.startswith("/") or settings.QDRANT_HOST == ":memory:":
            # Use local/in-memory mode
            if settings.QDRANT_HOST == ":memory:":
                self.client = qdrant_client.QdrantClient(location=":memory:")
            else:
                # Use local path for persistent storage
                self.client = qdrant_client.QdrantClient(path=settings.QDRANT_HOST)
        else:
            # Use remote mode (Qdrant Cloud)
            self.client = qdrant_client.QdrantClient(
                url=f"https://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
                api_key=settings.QDRANT_API_KEY
            )
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        # Create or recreate collection
        self.collection_name = settings.QDRANT_COLLECTION
        self._setup_collection()
    
    def _setup_collection(self):
        """Setup Qdrant collection"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [collection.name for collection in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection if it doesn't exist
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_model.get_embedding_dimension(),
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            print(f"Error setting up collection: {e}")
            try:
                # Recreate collection as fallback
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_model.get_embedding_dimension(),
                        distance=Distance.COSINE
                    )
                )
            except Exception as e2:
                print(f"Error recreating collection: {e2}")
                # If we can't recreate, we'll handle this in the methods that use the collection
    
    def upsert_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Upsert a document into the vector database"""
        try:
            # Generate embedding
            vector = self.embedding_model.encode(content).tolist()
            
            # Generate unique ID
            doc_id = str(uuid4())
            
            # Prepare payload
            payload = {
                "content": content,
                "metadata": metadata or {}
            }
            
            # Upsert point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            return doc_id
        except Exception as e:
            print(f"Error upserting document: {e}")
            return None
    
    def search(self, query: str, limit: int = 3, metadata_filter: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            # Generate query vector
            query_vector = self.embedding_model.encode(query).tolist()
            
            # Perform search
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=metadata_filter,
                score_threshold=score_threshold
            )
            
            # Format results
            formatted_results = []
            # Menangani perbedaan struktur respon pada berbagai versi qdrant-client
            points = response.points if hasattr(response, 'points') else response
            for result in points:
                formatted_results.append({
                    "id": result.id,
                    "content": result.payload.get("content", ""),
                    "metadata": result.payload.get("metadata", {}),
                    "score": result.score
                })
            
            return formatted_results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the vector database"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[doc_id]
            )
            return True
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False

# Initialize the vector database service with error handling
try:
    vector_db_service = VectorDBService()
except Exception as e:
    print(f"Error initializing VectorDBService: {e}")
    vector_db_service = None