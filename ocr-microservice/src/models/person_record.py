"""Person-related data models for genealogical records."""

from pydantic import BaseModel
from typing import Optional


class PersonRecord(BaseModel):
    """Represents a person in genealogical records"""
    given_names: Optional[str] = None  # Nullable - OCR may fail to extract given names
    surname: Optional[str] = None  # Nullable - historical records often lack surnames
    full_name: str
    gender: Optional[str] = None
    birth_date: Optional[str] = None  # Can be partial: YYYY, YYYY-MM, or YYYY-MM-DD
    birth_place: Optional[str] = None
    death_date: Optional[str] = None
    death_place: Optional[str] = None
    notes: Optional[str] = None


class ParentRecord(BaseModel):
    """Parent information in a record"""
    given_names: Optional[str] = None  # Nullable - OCR may fail to extract given names
    surname: Optional[str] = None  # Nullable - historical records often lack surnames
    full_name: str
    role: str  # "father" or "mother"


class WitnessRecord(BaseModel):
    """Witness/godparent information"""
    given_names: Optional[str] = None  # Nullable - OCR may fail to extract given names
    surname: Optional[str] = None  # Nullable - historical records often lack surnames
    full_name: str
    role: Optional[str] = None  # "godfather", "godmother", "witness"
    residence: Optional[str] = None
