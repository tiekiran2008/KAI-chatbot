import asyncio
import hashlib
import logging
from typing import List, Dict
import anyio.to_thread

logger = logging.getLogger(__name__)

class EmbeddingsService:
    """
    Asynchronous, cache-enabled HuggingFace SentenceTransformers embeddings generation pipeline.
    Runs CPU/GPU-intensive model execution in separate thread pools to avoid blocking the event loop.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None  # Lazy loaded to speed up startup sequence
        self._cache: Dict[str, List[float]] = {}  # In-memory deduplication cache

    def _get_model(self):
        """Lazy load the SentenceTransformer model to memory."""
        if self._model is None:
            # We import sentence-transformers here to prevent initial startup load delays
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence-transformer model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully.")
        return self._model

    def _get_text_hash(self, text: str) -> str:
        """Helper to generate cache key from text content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _generate_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous encoder call executing on HuggingFace model."""
        model = self._get_model()
        # encode returns numpy arrays; convert to nested python list of floats for ChromaDB compatibility
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Asynchronously fetches embeddings for a batch of strings.
        Checks cache for hits, and dispatches cache misses to a background thread pool.
        """
        if not texts:
            return []

        results: List[List[float] | None] = [None] * len(texts)
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []

        # 1. Resolve cache hits and isolate misses
        for idx, text in enumerate(texts):
            text_hash = self._get_text_hash(text)
            if text_hash in self._cache:
                results[idx] = self._cache[text_hash]
            else:
                uncached_texts.append(text)
                uncached_indices.append(idx)

        # 2. Generate embeddings for cache misses on background threads
        if uncached_texts:
            logger.info(f"Embedding Cache Miss: generating {len(uncached_texts)} new embeddings...")
            
            # Executed inside thread pool using anyio to prevent event-loop block
            generated = await anyio.to_thread.run_sync(
                self._generate_embeddings_sync,
                uncached_texts
            )

            # 3. Store hits in memory cache and map to results array
            for idx, text, emb in zip(uncached_indices, uncached_texts, generated):
                text_hash = self._get_text_hash(text)
                self._cache[text_hash] = emb
                results[idx] = emb

        return results

# Instantiate as a singleton
embeddings_service = EmbeddingsService()
