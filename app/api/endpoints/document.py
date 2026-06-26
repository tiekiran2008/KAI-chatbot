import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.user import User
from app.models.document import UploadedDocument
from app.api.deps import get_current_user
from app.schemas.document import DocumentRead
from app.services.pdf_parser import pdf_parser_service
from app.services.rag import rag_service
from app.services.vectorstore import vector_store_service

router = APIRouter()

# Max allowed size in bytes (15 Megabytes)
MAX_FILE_SIZE = 15 * 1024 * 1024 

@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and parse a PDF document using PyMuPDF.
    Extracts structure, validates, stores metadata in PostgreSQL, and generates vector index in ChromaDB.
    """
    # 1. Validation - MIME Type Check
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF uploads are allowed."
        )

    # Read binary bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # 2. Validation - File Size Check
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE // (1024*1024)}MB."
        )

    # 3. Parse PDF asynchronously
    try:
        parsed_doc = await pdf_parser_service.parse_pdf_async(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during PDF text extraction: {str(e)}"
        )

    # 4. Save metadata to database
    meta = parsed_doc["metadata"]
    db_doc = UploadedDocument(
        user_id=current_user.id,
        filename=file.filename,
        file_size=file_size,
        page_count=meta["page_count"],
        title=meta["title"],
        author=meta["author"],
        subject=meta["subject"]
    )
    
    db.add(db_doc)
    await db.flush() # Yields the UUID of the newly inserted document

    # 5. Index chunks into vector database
    try:
        await rag_service.index_document(
            user_id=current_user.id,
            doc_id=db_doc.id,
            filename=file.filename,
            parsed_pages=parsed_doc["pages"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF parsed, but failed to index into vector database: {str(e)}"
        )

    # Return the metadata representation
    return db_doc

@router.get("/", response_model=List[DocumentRead])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve all uploaded documents belonging to the authenticated user.
    """
    result = await db.execute(
        select(UploadedDocument)
        .filter(UploadedDocument.user_id == current_user.id)
        .order_by(UploadedDocument.created_at.desc())
    )
    return list(result.scalars().all())

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete an uploaded document and purge its vector indexes.
    """
    result = await db.execute(
        select(UploadedDocument)
        .filter(UploadedDocument.id == document_id, UploadedDocument.user_id == current_user.id)
    )
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    # Delete from relational database
    await db.delete(doc)
    
    # Delete associated chunks from ChromaDB vector database
    try:
        await vector_store_service.delete_by_metadata(
            collection_name="user_documents",
            where_filter={"document_id": str(document_id)}
        )
    except Exception as e:
        # We log and swallow the exception here since database deletion was successful
        import logging
        logging.getLogger(__name__).error(f"Failed to clear vector store during file delete: {e}")

@router.get("/{document_id}/preview", response_model=List[Dict[str, Any]])
async def preview_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve text chunks of an uploaded document from ChromaDB for real-time previewing.
    Includes ownership verification.
    """
    # 1. Verify document ownership first
    result = await db.execute(
        select(UploadedDocument)
        .filter(UploadedDocument.id == document_id, UploadedDocument.user_id == current_user.id)
    )
    doc = result.scalars().first()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or access denied."
        )

    # 2. Retrieve sorted chunks from ChromaDB
    try:
        chunks = await vector_store_service.get_document_chunks(
            collection_name="user_documents",
            document_id=str(document_id)
        )
        return chunks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document text blocks: {str(e)}"
        )
