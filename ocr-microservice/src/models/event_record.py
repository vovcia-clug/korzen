"""Event-related data models for genealogical records."""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from .person_record import PersonRecord, ParentRecord, WitnessRecord


class EventRecord(BaseModel):
    """Represents a genealogical event (baptism, marriage, death)"""
    record_type: Literal["baptism", "marriage", "death"]
    event_date: Optional[str] = None  # Date of event
    event_place: Optional[str] = None  # Place of event
    
    # Primary person(s)
    person: PersonRecord
    spouse: Optional[PersonRecord] = None  # For marriages
    
    # Relationships
    parents: List[ParentRecord] = Field(default_factory=list)
    witnesses: List[WitnessRecord] = Field(default_factory=list)
    
    # Metadata
    source_text: Optional[str] = None  # Original Latin text
    transcription: Optional[str] = None
    translation: Optional[str] = None
    notes: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ChurchRecordsDocument(BaseModel):
    """Complete document with all extracted records"""
    records: List[EventRecord]
    document_metadata: Optional[dict] = None
