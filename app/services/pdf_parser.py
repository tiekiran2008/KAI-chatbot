import fitz  # PyMuPDF
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class PDFParserService:
    """
    High-performance, production-grade PDF parser service powered by PyMuPDF.
    """
    def parse_pdf(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Parses a PDF document from bytes, extracts metadata and text page by page.
        Handles encryption checks, empty files, and robust error trapping.
        """
        if len(file_bytes) == 0:
            raise ValueError("The uploaded file is empty.")

        try:
            # Load PDF from memory buffer
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            logger.error(f"Failed to open PDF file {filename}: {e}")
            raise ValueError("Invalid PDF format or corrupted file structure.")

        try:
            # 1. Validation - Encryption Check
            if doc.is_encrypted:
                raise ValueError("Password-protected or encrypted PDFs are not supported.")

            # 2. Validation - Page Count Check
            page_count = len(doc)
            if page_count == 0:
                raise ValueError("The PDF contains no pages.")

            # 3. Metadata Extraction
            meta = doc.metadata or {}
            
            # Format and clean metadata securely
            cleaned_metadata = {
                "title": str(meta.get("title") or filename).strip(),
                "author": str(meta.get("author") or "Unknown Author").strip(),
                "subject": str(meta.get("subject") or "").strip(),
                "page_count": page_count,
            }

            # 4. Page-by-Page Text Extraction
            pages_data = []
            is_scanned = True  # Flag to detect if document has no extractable text

            for idx in range(page_count):
                page = doc[idx]
                # Extract clean Unicode text
                text = page.get_text("text") or ""
                
                # Strip excessive spaces and clean text representation
                cleaned_text = " ".join(text.split())
                
                if cleaned_text:
                    is_scanned = False
                
                pages_data.append({
                    "page_number": idx + 1,  # 1-indexed for user readability
                    "text": cleaned_text
                })

            # Warn user if the PDF appears to contain only images (scanned documents)
            if is_scanned:
                logger.warning(f"File {filename} has no extractable text. May require OCR scanning.")

            return {
                "metadata": cleaned_metadata,
                "pages": pages_data,
                "is_scanned": is_scanned
            }

        finally:
            # Always close document to prevent memory leaks
            doc.close()

    async def parse_pdf_async(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Asynchronously parses a PDF document inside a thread pool to avoid blocking the event loop.
        """
        import anyio.to_thread
        return await anyio.to_thread.run_sync(self.parse_pdf, file_bytes, filename)

# Instantiate as a singleton
pdf_parser_service = PDFParserService()
