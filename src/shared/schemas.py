
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, List, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

# --- ENUMS ---
class IngestStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"

class SourceType(str, Enum):
    PDF_UPLOAD = "knowledge_base"  # Coincide con tu legacy
    WEB_SCRAPE = "web_scrape"
    TEXT_INPUT = "text_input"

# --- API REQUEST MODELS (Lo que manda el SUID) ---

class DocumentUploadMetadata(BaseModel):
    client_id: UUID
    category: Optional[str] = "knowledge_base"
    # source: opcional, inferido si es upload

# --- INTERNAL MODELS (Lo que procesamos) ---

class CanonicalDocument(BaseModel):
    """
    Representación unificada de un documento antes de vectorizar.
    Alineado con 'canonical_document.json' legacy.
    """
    content_id: str = Field(..., description="ID único estable del documento (ej: 'doc_uuid')")
    client_id: UUID
    source: SourceType
    title: str
    body_content: str
    hash: str = Field(..., description="SHA-256 del body_content")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "content_id": "doc_12345",
                "client_id": "019b4872-51f6-72d3-84c9-45183ff700d0",
                "source": "knowledge_base",
                "title": "Manual de Ventas.pdf",
                "body_content": "Texto extraído del PDF...",
                "hash": "a4b3c2...",
                "metadata": {"filename": "original.pdf"}
            }
        }

class SemanticItem(BaseModel):
    """
    Modelo directo a la tabla 'semantic_items' en Postgres.
    """
    id: Optional[UUID] = None # Generado por DB
    content_id: str
    client_id: UUID
    source: str
    title: str
    body_content: str
    metadata: Dict[str, Any]
    hash: str
    embedding: Optional[List[float]] = None # Vector de pgvector

# --- RAG MODELS (Futuro) ---
class RAGQuery(BaseModel):
    query_text: str
    client_id: UUID
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None

class RAGResult(BaseModel):
    content_id: str
    title: str
    body_content: str
    score: float
    metadata: Dict[str, Any]


# --- PROPERTY MODELS (ETL-PROPERTIES) ---

class PropertyBase(BaseModel):
    client_id: UUID
    property_type_id: int
    title: str
    description: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_zip: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    area_sqm: Optional[float] = None
    features: Dict[str, Any] = Field(default_factory=dict)
    price: float
    currency_id: str = "USD"
    status: str = "available"
    external_ref: Optional[str] = None
    public_url: Optional[str] = None

class PropertyCreate(PropertyBase):
    pass

class Property(PropertyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
