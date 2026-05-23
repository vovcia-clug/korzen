from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship

from .extensions import db


class RecordBatch(db.Model):
    __tablename__ = "record_batches"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source = db.Column(String(120), nullable=False)
    description = db.Column(Text, nullable=True)
    ingested_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    genealogical_records = relationship("GenealogicalRecord", back_populates="batch")
    uploaded_files = relationship("UploadedFile", back_populates="batch")


class GenealogicalRecord(db.Model):
    __tablename__ = "genealogical_records"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("record_batches.id"),
        nullable=True,
    )
    record_type = db.Column(String(80), nullable=False)
    raw_payload = db.Column(JSONB, nullable=False)
    external_id = db.Column(String(120), nullable=True)
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    batch = relationship("RecordBatch", back_populates="genealogical_records")


class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = db.Column(String(255), nullable=False)
    original_filename = db.Column(String(255), nullable=False)
    filepath = db.Column(String(512), nullable=False)
    file_size = db.Column(BigInteger, nullable=False)
    mime_type = db.Column(String(100), nullable=True)
    uploaded_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    batch_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("record_batches.id"),
        nullable=True,
    )
    processing_status = db.Column(String(50), nullable=True, default="uploaded")

    # Relationships
    batch = relationship("RecordBatch", back_populates="uploaded_files")


class SocialStatus(db.Model):
    """
    Social status/class definitions from Latin records.
    Examples: Civis, Honestus, Magnificus, Nobilis, Agricola, Cmetho, etc.
    """
    __tablename__ = "social_statuses"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    latin_name = db.Column(String(100), nullable=False, unique=True)
    polish_name = db.Column(String(100), nullable=True)
    description = db.Column(Text, nullable=True)
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    persons = relationship("Person", back_populates="social_status")


class Person(db.Model):
    """
    Core person entity representing individuals in genealogical records.
    """
    __tablename__ = "persons"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source tracking for GEDCOM imports
    gedcom_id = db.Column(String(50), nullable=True, index=True)
    source_batch_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("record_batches.id"),
        nullable=True,
    )
    
    # Basic information
    first_name = db.Column(String(100), nullable=True)
    last_name = db.Column(String(100), nullable=True)
    maiden_name = db.Column(String(100), nullable=True)
    gender = db.Column(String(10), nullable=True)  # M, F, Unknown
    
    # Dates
    birth_date = db.Column(Date, nullable=True)
    birth_date_estimated = db.Column(Boolean, default=False)
    death_date = db.Column(Date, nullable=True)
    death_date_estimated = db.Column(Boolean, default=False)
    
    # Location information
    birth_place = db.Column(String(200), nullable=True)
    death_place = db.Column(String(200), nullable=True)
    residence = db.Column(String(200), nullable=True)
    house_number = db.Column(String(50), nullable=True)
    parish = db.Column(String(200), nullable=True)
    
    # Parent relationships
    father_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    mother_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    
    # Social status
    social_status_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("social_statuses.id"),
        nullable=True,
    )
    
    # Additional information
    occupation = db.Column(String(200), nullable=True)
    notes = db.Column(Text, nullable=True)
    
    # Metadata
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vector embedding for duplicate detection (128 dimensions)
    embedding = db.Column(Vector(128), nullable=True)
    
    # Phonetic codes for name matching
    first_name_phonetic = db.Column(JSONB, nullable=True)  # List of D-M codes
    last_name_phonetic = db.Column(JSONB, nullable=True)   # List of D-M codes
    maiden_name_phonetic = db.Column(JSONB, nullable=True) # List of D-M codes
    
    # Relationships
    source_batch = relationship("RecordBatch")
    social_status = relationship("SocialStatus", back_populates="persons")
    
    # Parent relationships
    father = relationship(
        "Person",
        remote_side=[id],
        foreign_keys=[father_id],
        backref="children_as_father"
    )
    mother = relationship(
        "Person",
        remote_side=[id],
        foreign_keys=[mother_id],
        backref="children_as_mother"
    )
    
    # Baptism records where this person is the child
    baptism_as_child = relationship(
        "BaptismRecord",
        foreign_keys="BaptismRecord.child_id",
        back_populates="child"
    )
    
    # Baptism records where this person is the father
    baptism_as_father = relationship(
        "BaptismRecord",
        foreign_keys="BaptismRecord.father_id",
        back_populates="father"
    )
    
    # Baptism records where this person is the mother
    baptism_as_mother = relationship(
        "BaptismRecord",
        foreign_keys="BaptismRecord.mother_id",
        back_populates="mother"
    )
    
    # Marriage records as spouse 1
    marriages_as_spouse1 = relationship(
        "MarriageRecord",
        foreign_keys="MarriageRecord.spouse1_id",
        back_populates="spouse1"
    )
    
    # Marriage records as spouse 2
    marriages_as_spouse2 = relationship(
        "MarriageRecord",
        foreign_keys="MarriageRecord.spouse2_id",
        back_populates="spouse2"
    )
    
    # Death records
    death_records = relationship("DeathRecord", back_populates="deceased")


class BaptismRecord(db.Model):
    """
    Baptism records (Metryki chrztów) from parish registers.
    Based on Galician tabular records introduced around 1785.
    """
    __tablename__ = "baptism_records"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source tracking for GEDCOM imports
    gedcom_id = db.Column(String(50), nullable=True, index=True)
    source_batch_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("record_batches.id"),
        nullable=True,
    )
    
    # Record identification
    record_number = db.Column(String(50), nullable=True)
    page_number = db.Column(String(50), nullable=True)
    
    # Dates
    birth_date = db.Column(Date, nullable=True)
    baptism_date = db.Column(Date, nullable=False)
    
    # Location
    parish = db.Column(String(200), nullable=True)
    village = db.Column(String(200), nullable=True)
    house_number = db.Column(String(50), nullable=True)
    
    # Child information
    child_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    child_name = db.Column(String(100), nullable=True)
    child_gender = db.Column(String(10), nullable=True)
    
    # Parents
    father_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    father_name = db.Column(String(100), nullable=True)
    father_surname = db.Column(String(100), nullable=True)
    
    mother_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    mother_name = db.Column(String(100), nullable=True)
    mother_maiden_name = db.Column(String(100), nullable=True)
    
    # Legitimacy status (LLCC - legitimorum coniugum)
    legitimate = db.Column(Boolean, nullable=True)
    
    # Grandparents (added in later records)
    paternal_grandfather_name = db.Column(String(100), nullable=True)
    paternal_grandmother_name = db.Column(String(100), nullable=True)
    maternal_grandfather_name = db.Column(String(100), nullable=True)
    maternal_grandmother_name = db.Column(String(100), nullable=True)
    
    # Godparents (Patrini)
    godfather_name = db.Column(String(100), nullable=True)
    godmother_name = db.Column(String(100), nullable=True)
    godparents_location = db.Column(String(200), nullable=True)
    
    # Priest/Official
    priest_name = db.Column(String(200), nullable=True)
    
    # Original record
    original_text_latin = db.Column(Text, nullable=True)
    transcription = db.Column(Text, nullable=True)
    translation = db.Column(Text, nullable=True)
    
    # Notes
    notes = db.Column(Text, nullable=True)
    
    # Metadata
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vector embedding for duplicate detection
    embedding = db.Column(Vector(128), nullable=True)
    
    # Phonetic codes
    child_name_phonetic = db.Column(JSONB, nullable=True)
    father_surname_phonetic = db.Column(JSONB, nullable=True)
    mother_maiden_name_phonetic = db.Column(JSONB, nullable=True)
    
    # Relationships
    child = relationship("Person", foreign_keys=[child_id], back_populates="baptism_as_child")
    father = relationship("Person", foreign_keys=[father_id], back_populates="baptism_as_father")
    mother = relationship("Person", foreign_keys=[mother_id], back_populates="baptism_as_mother")


class MarriageRecord(db.Model):
    """
    Marriage records (Metryki ślubów) from parish registers.
    Records marriages with banns (denunciationibus) and witnesses.
    """
    __tablename__ = "marriage_records"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source tracking for GEDCOM imports
    gedcom_id = db.Column(String(50), nullable=True, index=True)
    source_batch_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("record_batches.id"),
        nullable=True,
    )
    
    # Record identification
    record_number = db.Column(String(50), nullable=True)
    page_number = db.Column(String(50), nullable=True)
    
    # Date and location
    marriage_date = db.Column(Date, nullable=False)
    parish = db.Column(String(200), nullable=True)
    village = db.Column(String(200), nullable=True)
    
    # Spouse 1 (traditionally groom)
    spouse1_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    spouse1_name = db.Column(String(100), nullable=True)
    spouse1_surname = db.Column(String(100), nullable=True)
    spouse1_status = db.Column(String(50), nullable=True)  # Juvenis (bachelor), Viduus (widower)
    spouse1_parish = db.Column(String(200), nullable=True)
    spouse1_residence = db.Column(String(200), nullable=True)
    spouse1_father_name = db.Column(String(100), nullable=True)
    spouse1_mother_name = db.Column(String(100), nullable=True)
    spouse1_age = db.Column(Integer, nullable=True)
    
    # Spouse 2 (traditionally bride)
    spouse2_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    spouse2_name = db.Column(String(100), nullable=True)
    spouse2_surname = db.Column(String(100), nullable=True)
    spouse2_maiden_name = db.Column(String(100), nullable=True)
    spouse2_status = db.Column(String(50), nullable=True)  # Virgo (spinster), Vidua (widow)
    spouse2_parish = db.Column(String(200), nullable=True)
    spouse2_residence = db.Column(String(200), nullable=True)
    spouse2_father_name = db.Column(String(100), nullable=True)
    spouse2_mother_name = db.Column(String(100), nullable=True)
    spouse2_age = db.Column(Integer, nullable=True)
    
    # Banns (denunciationes)
    banns_count = db.Column(Integer, nullable=True, default=3)
    banns_dates = db.Column(JSONB, nullable=True)  # Array of dates
    
    # Witnesses (testes)
    witnesses = db.Column(JSONB, nullable=True)  # Array of witness names and locations
    
    # Priest/Official
    priest_name = db.Column(String(200), nullable=True)
    
    # Original record
    original_text_latin = db.Column(Text, nullable=True)
    transcription = db.Column(Text, nullable=True)
    translation = db.Column(Text, nullable=True)
    
    # Notes
    notes = db.Column(Text, nullable=True)
    
    # Metadata
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vector embedding for duplicate detection
    embedding = db.Column(Vector(128), nullable=True)
    
    # Phonetic codes
    spouse1_surname_phonetic = db.Column(JSONB, nullable=True)
    spouse2_surname_phonetic = db.Column(JSONB, nullable=True)
    
    # Relationships
    spouse1 = relationship("Person", foreign_keys=[spouse1_id], back_populates="marriages_as_spouse1")
    spouse2 = relationship("Person", foreign_keys=[spouse2_id], back_populates="marriages_as_spouse2")


class DeathRecord(db.Model):
    """
    Death records (Metryki zgonów) from parish registers.
    Records deaths with sacraments and burial information.
    """
    __tablename__ = "death_records"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Source tracking for GEDCOM imports
    gedcom_id = db.Column(String(50), nullable=True, index=True)
    source_batch_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("record_batches.id"),
        nullable=True,
    )
    
    # Record identification
    record_number = db.Column(String(50), nullable=True)
    page_number = db.Column(String(50), nullable=True)
    
    # Dates
    death_date = db.Column(Date, nullable=False)
    burial_date = db.Column(Date, nullable=True)
    
    # Location
    parish = db.Column(String(200), nullable=True)
    village = db.Column(String(200), nullable=True)
    cemetery = db.Column(String(200), nullable=True)
    
    # Deceased person
    deceased_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=True,
    )
    deceased_name = db.Column(String(100), nullable=True)
    deceased_surname = db.Column(String(100), nullable=True)
    deceased_maiden_name = db.Column(String(100), nullable=True)
    
    # Status and age
    marital_status = db.Column(String(50), nullable=True)  # Virgo, Conjugatus, Viduus, etc.
    age_years = db.Column(Integer, nullable=True)
    age_description = db.Column(String(100), nullable=True)  # e.g., "Septuagenaria" (70-year-old)
    
    # Cause of death
    cause_of_death = db.Column(Text, nullable=True)
    
    # Sacraments
    sacraments_received = db.Column(Boolean, nullable=True)  # "Sacramentis munita"
    sacraments_details = db.Column(Text, nullable=True)
    
    # Family information
    spouse_name = db.Column(String(100), nullable=True)
    father_name = db.Column(String(100), nullable=True)
    mother_name = db.Column(String(100), nullable=True)
    
    # Priest/Official
    priest_name = db.Column(String(200), nullable=True)
    
    # Original record
    original_text_latin = db.Column(Text, nullable=True)
    transcription = db.Column(Text, nullable=True)
    translation = db.Column(Text, nullable=True)
    
    # Notes
    notes = db.Column(Text, nullable=True)
    
    # Metadata
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = db.Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vector embedding for duplicate detection
    embedding = db.Column(Vector(128), nullable=True)
    
    # Phonetic codes
    deceased_surname_phonetic = db.Column(JSONB, nullable=True)
    deceased_maiden_name_phonetic = db.Column(JSONB, nullable=True)
    
    # Relationships
    deceased = relationship("Person", back_populates="death_records")


class GodparentRelationship(db.Model):
    """
    Many-to-many relationship table for godparents in baptism records.
    Allows linking Person entities as godparents to baptism records.
    """
    __tablename__ = "godparent_relationships"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    baptism_record_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("baptism_records.id"),
        nullable=False,
    )
    godparent_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=False,
    )
    godparent_type = db.Column(String(20), nullable=True)  # 'godfather', 'godmother'
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)


class WitnessRelationship(db.Model):
    """
    Many-to-many relationship table for witnesses in marriage records.
    Allows linking Person entities as witnesses to marriage records.
    """
    __tablename__ = "witness_relationships"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    marriage_record_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("marriage_records.id"),
        nullable=False,
    )
    witness_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete='CASCADE'),
        nullable=False,
    )
    witness_order = db.Column(Integer, nullable=True)  # Order in which witness appears
    created_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)


class DuplicateCandidate(db.Model):
    """
    Stores potential duplicate pairs for review.
    Links two records that may be duplicates based on similarity analysis.
    """
    __tablename__ = "duplicate_candidates"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Record type and IDs
    record_type = db.Column(String(50), nullable=False)  # 'person', 'baptism', 'marriage', 'death'
    record1_id = db.Column(UUID(as_uuid=True), nullable=False)
    record2_id = db.Column(UUID(as_uuid=True), nullable=False)
    
    # Similarity scores
    vector_similarity = db.Column(db.Float, nullable=False)
    phonetic_similarity = db.Column(db.Float, nullable=True)
    date_similarity = db.Column(db.Float, nullable=True)
    location_similarity = db.Column(db.Float, nullable=True)
    composite_score = db.Column(db.Float, nullable=False)
    
    # Review status
    status = db.Column(String(20), nullable=False, default='pending')  # pending, confirmed, rejected
    reviewed_by = db.Column(String(100), nullable=True)
    reviewed_at = db.Column(DateTime(timezone=True), nullable=True)
    review_notes = db.Column(Text, nullable=True)
    
    # Metadata
    detected_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    detection_method = db.Column(String(50), nullable=True)  # 'import', 'batch', 'manual'
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('ix_duplicate_candidates_record1', 'record_type', 'record1_id'),
        db.Index('ix_duplicate_candidates_record2', 'record_type', 'record2_id'),
        db.Index('ix_duplicate_candidates_status', 'status'),
        db.Index('ix_duplicate_candidates_score', 'composite_score'),
    )


class DuplicateResolution(db.Model):
    """
    Tracks resolution actions taken on duplicate candidates.
    Records merge operations and maintains audit trail.
    """
    __tablename__ = "duplicate_resolutions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Link to candidate
    candidate_id = db.Column(
        UUID(as_uuid=True),
        ForeignKey("duplicate_candidates.id"),
        nullable=False,
    )
    
    # Resolution details
    action = db.Column(String(20), nullable=False)  # 'merge', 'reject', 'defer'
    kept_record_id = db.Column(UUID(as_uuid=True), nullable=True)  # Which record was kept in merge
    merged_record_id = db.Column(UUID(as_uuid=True), nullable=True)  # Which record was merged/deleted
    
    # Audit trail
    resolved_by = db.Column(String(100), nullable=False)
    resolved_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)
    resolution_notes = db.Column(Text, nullable=True)
    
    # Merged data snapshot (for potential rollback)
    merged_data = db.Column(JSONB, nullable=True)
