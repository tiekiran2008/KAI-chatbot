import uuid
import logging
import json
from typing import List, Dict, Any, Optional

from app.models.document import UploadedDocument
from app.services.chunker import chunker_service
from app.services.embeddings import embeddings_service
from app.services.vectorstore import vector_store_service
from app.services.gemini import gemini_service

logger = logging.getLogger(__name__)

# Standard RAG settings
COLLECTION_NAME = "user_documents"

class RAGService:
    """
    Complete end-to-end RAG retrieval, document indexing, and augmented prompt orchestration pipeline.
    """
    def __init__(self):
        self._retrieval_cache = {}  # In-memory vector retrieval cache

    async def index_document(
        self,
        user_id: uuid.UUID,
        doc_id: uuid.UUID,
        filename: str,
        parsed_pages: List[Dict[str, Any]]
    ) -> None:
        """
        Chunks parsed PDF pages, generates async embeddings, compiles metadata,
        and indexes chunks into the persistent ChromaDB collection.
        """
        if not parsed_pages:
            logger.warning(f"No pages found to index for file {filename}")
            return

        # 1. Chunk document using the high-performance sentence-aware chunker
        logger.info(f"Chunking document: {filename}...")
        chunks = chunker_service.sentence_aware_chunking(
            pages=parsed_pages,
            max_chunk_size=800,  # Optimal size for semantic richness and prompt economy
            chunk_overlap=150
        )
        
        if not chunks:
            logger.warning(f"No text chunks generated for document {filename}")
            return

        # 2. Extract texts and generate batch embeddings asynchronously
        chunk_texts = [c["text"] for c in chunks]
        logger.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
        embeddings = await embeddings_service.get_embeddings(chunk_texts)

        # 3. Compile structural metadata for search filters and citations
        ids = []
        metadatas = []
        
        for idx, chunk in enumerate(chunks):
            # ChromaDB only supports primitive types in metadata, so convert page numbers to string
            page_str = ",".join(map(str, chunk["metadata"]["page_numbers"]))
            
            metadatas.append({
                "document_id": str(doc_id),
                "user_id": str(user_id),
                "filename": filename,
                "page_numbers": page_str,
                "chunk_index": chunk["metadata"]["chunk_index"],
                "chunk_method": chunk["metadata"]["chunk_method"]
            })
            # Generate a globally unique ID for this vector block
            ids.append(f"doc_{doc_id}_chunk_{idx}")

        # 4. Ingest into persistent vector storage
        logger.info(f"Ingesting chunks to ChromaDB persistent index...")
        await vector_store_service.add_documents(
            collection_name=COLLECTION_NAME,
            documents=chunk_texts,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        logger.info(f"Index complete for document: {filename}.")

    def deduplicate_contexts(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicates overlapping or near-identical text chunks to reduce token overhead.
        """
        seen_texts = set()
        unique_contexts = []
        for ctx in contexts:
            # Normalize whitespace and casing
            text_norm = " ".join(ctx.get("text", "").lower().split())
            if not text_norm:
                continue
            
            # Identify exact or substring duplicates
            is_duplicate = False
            for seen in seen_texts:
                if text_norm in seen or seen in text_norm:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_texts.add(text_norm)
                unique_contexts.append(ctx)
                
        return unique_contexts

    async def retrieve_context(
        self,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generates query embedding and retrieves top-k relevant document chunks.
        Applies a user security filter to ensure cross-user data isolation.
        Caches results dynamically to minimize latency for repeated queries.
        """
        import hashlib
        # Calculate secure cache key
        cache_str = f"{user_id}:{query.strip()}:{top_k}"
        cache_key = hashlib.sha256(cache_str.encode("utf-8")).hexdigest()

        # Check Cache Hit
        if cache_key in self._retrieval_cache:
            logger.info("RAG Vector Retrieval: Cache Hit! Skipping embedding/similarity searches.")
            return self._retrieval_cache[cache_key]

        # Generate query embedding
        query_embs = await embeddings_service.get_embeddings([query])
        query_emb = query_embs[0]

        # Query vector store with strict user filtering
        raw_matches = await vector_store_service.similarity_search(
            collection_name=COLLECTION_NAME,
            query_embedding=query_emb,
            top_k=top_k,
            where_filter={"user_id": str(user_id)}
        )

        # Optimize: Apply Semantic Context Compression/De-duplication
        matches = self.deduplicate_contexts(raw_matches)

        # Evict oldest key if cache is too large to bound memory usage
        if len(self._retrieval_cache) > 200:
            first_key = next(iter(self._retrieval_cache))
            self._retrieval_cache.pop(first_key, None)

        # Cache Miss Store
        self._retrieval_cache[cache_key] = matches
        return matches

    def build_augmented_prompt(self, query: str, contexts: List[Dict[str, Any]]) -> str:
        """
        Injects matching contexts and formats augmented prompts with clear source citations.
        """
        if not contexts:
            return query

        context_blocks = []
        for idx, ctx in enumerate(contexts):
            filename = ctx["metadata"].get("filename", "Unknown Document")
            pages = ctx["metadata"].get("page_numbers", "Unknown Page")
            score = ctx.get("score", 0.0)
            
            context_blocks.append(
                f"[Context Reference #{idx+1}]\n"
                f"Source File: {filename}\n"
                f"Page Reference: {pages}\n"
                f"Matching Confidence: {score:.2%}\n"
                f"Content: {ctx['text']}\n"
            )

        context_str = "\n---\n".join(context_blocks)
        
        augmented = (
            "You are a production-grade AI assistant with deep analytical RAG retrieval capabilities.\n"
            "Analyze the retrieved context below to accurately answer the User's query.\n"
            "Adhere strictly to these instruction guidelines:\n"
            "1. Ground your answers ONLY on the provided Context References.\n"
            "2. If the context does not contain sufficient data to answer, state clearly that you cannot answer based on the document.\n"
            "3. Cite your sources directly in your response text (e.g. using format '[DocumentName.pdf, Page X]').\n"
            "4. Be objective, accurate, and direct.\n\n"
            "=== RETRIEVED CONTEXT ===\n"
            f"{context_str}\n"
            "=== USER QUERY ===\n"
            f"{query}\n"
        )
        return augmented

# Instantiate as a singleton
rag_service = RAGService()
