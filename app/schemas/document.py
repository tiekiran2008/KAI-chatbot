import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class DocumentRead(BaseModel):
    """
    Serialized lightweight metadata representation of an uploaded document.
    """
    id: uuid.UUID
    filename: str
    file_size: int
    page_count: int
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
