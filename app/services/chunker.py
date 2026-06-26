import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ChunkerService:
    """
    High-performance chunking service offering Fixed-Size and Sentence-Aware splitting pipelines.
    Extracts, structures, overlaps, and tracks page metadata for downstream vector indexes.
    """
    
    def fixed_size_chunking(
        self,
        pages: List[Dict[str, Any]],
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Splits raw text from pages into fixed-size character blocks with a configurable overlap.
        Traces and aggregates overlapping page ranges for structural citation metadata.
        """
        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than zero.")
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size.")

        chunks = []
        
        # 1. Compile continuous stream of characters while preserving page indices
        full_text = ""
        char_to_page = []  # Map each character index to its page number
        
        for p in pages:
            page_text = p["text"]
            page_num = p["page_number"]
            
            # Pad page boundaries slightly to prevent words fusing
            if full_text:
                full_text += " "
                char_to_page.append(page_num)
                
            start_idx = len(full_text)
            full_text += page_text
            char_to_page.extend([page_num] * len(page_text))

        # 2. Slice text based on fixed-size sliding window
        text_len = len(full_text)
        if text_len == 0:
            return []

        start = 0
        chunk_idx = 0
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk_text = full_text[start:end].strip()
            
            if chunk_text:
                # Resolve pages spanned by the current slice
                spanned_pages = sorted(list(set(char_to_page[start:end])))
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "page_numbers": spanned_pages,
                        "chunk_index": chunk_idx,
                        "chunk_method": "fixed",
                        "char_count": len(chunk_text)
                    }
                })
                chunk_idx += 1
                
            # Slide window forward by (chunk_size - overlap)
            start += (chunk_size - chunk_overlap)
            
            # Avoid infinite loop if slide step becomes 0
            if (chunk_size - chunk_overlap) <= 0:
                break
                
        return chunks

    def sentence_aware_chunking(
        self,
        pages: List[Dict[str, Any]],
        max_chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Splits text along semantic sentence boundaries.
        Aggregates sentences until the next one would exceed max_chunk_size.
        Applies sentence-level overlap to ensure semantic continuity between blocks.
        """
        if max_chunk_size <= 0:
            raise ValueError("Max chunk size must be greater than zero.")
        if chunk_overlap >= max_chunk_size:
            raise ValueError("Chunk overlap must be less than max chunk size.")

        chunks = []
        
        # 1. Parse individual sentences along with page numbers
        sentences_with_metadata = []
        sentence_end_regex = re.compile(r'(?<=[.!?])\s+')
        
        for p in pages:
            page_text = p["text"]
            page_num = p["page_number"]
            
            # Split page into sentences
            splits = sentence_end_regex.split(page_text)
            for split in splits:
                clean_sent = split.strip()
                if clean_sent:
                    sentences_with_metadata.append({
                        "text": clean_sent,
                        "page_number": page_num
                    })

        # 2. Build semantic chunks with overlapping sentence memory
        num_sentences = len(sentences_with_metadata)
        if num_sentences == 0:
            return []

        chunk_idx = 0
        sent_idx = 0
        
        while sent_idx < num_sentences:
            current_chunk_sentences = []
            current_chunk_chars = 0
            
            # Compile sentences for current chunk
            temp_idx = sent_idx
            while temp_idx < num_sentences:
                sent = sentences_with_metadata[temp_idx]
                sent_len = len(sent["text"])
                
                # Check character threshold. If it's the first sentence, we must include it
                # even if it exceeds max_chunk_size to prevent deadlocks.
                if current_chunk_chars + sent_len > max_chunk_size and current_chunk_chars > 0:
                    break
                    
                current_chunk_sentences.append(sent)
                current_chunk_chars += sent_len + 1  # Add 1 for spacing
                temp_idx += 1
                
            if not current_chunk_sentences:
                break
                
            # Build text and extract metadata
            chunk_text = " ".join([s["text"] for s in current_chunk_sentences])
            spanned_pages = sorted(list(set([s["page_number"] for s in current_chunk_sentences])))
            
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "page_numbers": spanned_pages,
                    "chunk_index": chunk_idx,
                    "chunk_method": "sentence_aware",
                    "char_count": len(chunk_text)
                }
            })
            chunk_idx += 1
            
            # Calculate overlapping step back index
            # We want to overlap by ~chunk_overlap characters
            overlap_chars = 0
            step_back_count = 0
            
            # Trace backwards from where this chunk ended to see how many sentences fit inside overlap boundary
            for back_sent in reversed(current_chunk_sentences):
                overlap_chars += len(back_sent["text"]) + 1
                if overlap_chars > chunk_overlap:
                    break
                step_back_count += 1
                
            # Advance sent_idx. Ensure we move forward by at least 1 sentence to prevent infinite loops
            actual_advance = len(current_chunk_sentences) - step_back_count
            if actual_advance <= 0:
                actual_advance = 1
                
            sent_idx += actual_advance
            
        return chunks

# Instantiate as a singleton
chunker_service = ChunkerService()
