from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .extensions import db


class RecordBatch(db.Model):
    __tablename__ = "record_batches"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source = db.Column(String(120), nullable=False)
    description = db.Column(Text, nullable=True)
    ingested_at = db.Column(DateTime(timezone=True), default=datetime.utcnow)


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
