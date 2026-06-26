import logging
from typing import List, Dict, Any, Optional
import chromadb

from app.config import settings

logger = logging.getLogger(__name__)

class VectorStoreService:
    """
    Production-grade ChromaDB vector storage service.
    Handles persistent database connections, collections, indexing, similarity searches, and filter metadata.
    """
    def __init__(self):
        # Setup HTTP client for distributed storage connection
        logger.info(f"Connecting to ChromaDB HttpClient at {settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}...")
        self.client = chromadb.HttpClient(host=settings.CHROMADB_HOST, port=settings.CHROMADB_PORT)
        logger.info("ChromaDB Client successfully connected.")

    def get_or_create_collection(self, collection_name: str) -> chromadb.Collection:
        """
        Fetch an existing collection or initialize a new one.
        We bypass ChromaDB's default embedding function since we feed custom embeddings manually.
        """
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:search_ef": 100,
                "hnsw:M": 16
            }
        )

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: List[List[float]]
    ) -> None:
        """
        Stores document texts, metadata, and custom embeddings to the collection.
        Executes as an asynchronous operation.
        """
        if not documents:
            return

        try:
            collection = self.get_or_create_collection(collection_name)
            
            # ChromaDB handles bulk ingestion safely
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings
            )
            logger.info(f"Successfully added {len(documents)} chunks to ChromaDB collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to ingest documents to ChromaDB: {e}")
            raise RuntimeError(f"Vector storage ingestion error: {str(e)}")

    async def similarity_search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs high-performance cosine similarity vector matching in ChromaDB.
        
        :param where_filter: Optional metadata dictionary filter (e.g. {"user_id": "..."})
        :return: List of matches formatted with scores, text, and metadata
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            
            # Run vector query search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter
            )

            # Restructure query outputs into uniform Python structures
            formatted_matches = []
            
            # Check if any documents match
            if results and results["documents"] and len(results["documents"][0]) > 0:
                docs = results["documents"][0]
                metas = results["metadatas"][0]
                ids = results["ids"][0]
                distances = results["distances"][0]

                for i in range(len(docs)):
                    # Cosine distance to cosine similarity confidence score (1 - distance)
                    dist = distances[i]
                    similarity_score = max(0.0, min(1.0, 1.0 - dist))
                    
                    formatted_matches.append({
                        "id": ids[i],
                        "text": docs[i],
                        "metadata": metas[i],
                        "score": similarity_score
                    })
                    
            return formatted_matches

        except Exception as e:
            logger.error(f"Error performing similarity search in ChromaDB: {e}")
            raise RuntimeError(f"Vector search failure: {str(e)}")

    async def delete_by_metadata(self, collection_name: str, where_filter: Dict[str, Any]) -> None:
        """
        Deletes vector records from collection matching specified metadata filter.
        Extremely useful for stripping chunks belonging to a deleted document.
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            collection.delete(where=where_filter)
            logger.info(f"Successfully deleted chunks matching filter {where_filter} in ChromaDB.")
        except Exception as e:
            logger.error(f"Error deleting chunks by metadata filter: {e}")
            raise RuntimeError(f"Vector deletion failure: {str(e)}")

    async def get_document_chunks(self, collection_name: str, document_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all text chunks and metadata belonging to a specific document_id from ChromaDB.
        Sorts the chunks by their original chunk index to reconstruct readable structure.
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            results = collection.get(where={"document_id": document_id})
            
            chunks = []
            if results and results["documents"]:
                docs = results["documents"]
                metas = results["metadatas"]
                ids = results["ids"]
                
                for i in range(len(docs)):
                    chunks.append({
                        "id": ids[i],
                        "text": docs[i],
                        "metadata": metas[i]
                    })
                
                # Re-sort chunks to reconstruct the original linear document reading flow
                chunks.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
                
            return chunks
        except Exception as e:
            logger.error(f"Error fetching document chunks from ChromaDB: {e}")
            raise RuntimeError(f"Failed to load document text blocks: {str(e)}")

# Instantiate as a singleton
vector_store_service = VectorStoreService()
