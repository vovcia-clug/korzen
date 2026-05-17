"""Add vector embeddings and duplicate detection

Revision ID: 002
Revises: 001
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Use raw SQL with IF NOT EXISTS to make migration idempotent
    conn = op.get_bind()
    
    # Add vector embedding and phonetic columns to persons table
    conn.execute(sa.text('ALTER TABLE persons ADD COLUMN IF NOT EXISTS embedding VECTOR(128)'))
    conn.execute(sa.text('ALTER TABLE persons ADD COLUMN IF NOT EXISTS first_name_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE persons ADD COLUMN IF NOT EXISTS last_name_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE persons ADD COLUMN IF NOT EXISTS maiden_name_phonetic JSONB'))
    
    # Add vector embedding and phonetic columns to baptism_records table
    conn.execute(sa.text('ALTER TABLE baptism_records ADD COLUMN IF NOT EXISTS embedding VECTOR(128)'))
    conn.execute(sa.text('ALTER TABLE baptism_records ADD COLUMN IF NOT EXISTS child_name_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE baptism_records ADD COLUMN IF NOT EXISTS father_surname_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE baptism_records ADD COLUMN IF NOT EXISTS mother_maiden_name_phonetic JSONB'))
    
    # Add vector embedding and phonetic columns to marriage_records table
    conn.execute(sa.text('ALTER TABLE marriage_records ADD COLUMN IF NOT EXISTS embedding VECTOR(128)'))
    conn.execute(sa.text('ALTER TABLE marriage_records ADD COLUMN IF NOT EXISTS spouse1_surname_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE marriage_records ADD COLUMN IF NOT EXISTS spouse2_surname_phonetic JSONB'))
    
    # Add vector embedding and phonetic columns to death_records table
    conn.execute(sa.text('ALTER TABLE death_records ADD COLUMN IF NOT EXISTS embedding VECTOR(128)'))
    conn.execute(sa.text('ALTER TABLE death_records ADD COLUMN IF NOT EXISTS deceased_surname_phonetic JSONB'))
    conn.execute(sa.text('ALTER TABLE death_records ADD COLUMN IF NOT EXISTS deceased_maiden_name_phonetic JSONB'))
    
    # Create duplicate_candidates table (if not exists)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS duplicate_candidates (
            id UUID NOT NULL PRIMARY KEY,
            record_type VARCHAR(50) NOT NULL,
            record1_id UUID NOT NULL,
            record2_id UUID NOT NULL,
            vector_similarity FLOAT NOT NULL,
            phonetic_similarity FLOAT,
            date_similarity FLOAT,
            location_similarity FLOAT,
            composite_score FLOAT NOT NULL,
            status VARCHAR(20) NOT NULL,
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP WITH TIME ZONE,
            review_notes TEXT,
            detected_at TIMESTAMP WITH TIME ZONE,
            detection_method VARCHAR(50)
        )
    """))
    
    # Create duplicate_resolutions table (if not exists)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS duplicate_resolutions (
            id UUID NOT NULL PRIMARY KEY,
            candidate_id UUID NOT NULL REFERENCES duplicate_candidates(id),
            action VARCHAR(20) NOT NULL,
            kept_record_id UUID,
            merged_record_id UUID,
            resolved_by VARCHAR(100) NOT NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            resolution_notes TEXT,
            merged_data JSONB
        )
    """))
    
    # Create indexes on duplicate_candidates (if not exists)
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_duplicate_candidates_record1 ON duplicate_candidates (record_type, record1_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_duplicate_candidates_record2 ON duplicate_candidates (record_type, record2_id)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_duplicate_candidates_status ON duplicate_candidates (status)'))
    conn.execute(sa.text('CREATE INDEX IF NOT EXISTS ix_duplicate_candidates_score ON duplicate_candidates (composite_score)'))
    
    # Create HNSW indexes for vector similarity search (with IF NOT EXISTS)
    op.execute('CREATE INDEX IF NOT EXISTS ix_persons_embedding_hnsw ON persons USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_baptism_records_embedding_hnsw ON baptism_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_marriage_records_embedding_hnsw ON marriage_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_death_records_embedding_hnsw ON death_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')


def downgrade():
    # Drop HNSW indexes
    op.execute('DROP INDEX IF EXISTS ix_death_records_embedding_hnsw')
    op.execute('DROP INDEX IF EXISTS ix_marriage_records_embedding_hnsw')
    op.execute('DROP INDEX IF EXISTS ix_baptism_records_embedding_hnsw')
    op.execute('DROP INDEX IF EXISTS ix_persons_embedding_hnsw')
    
    # Drop indexes on duplicate_candidates
    op.drop_index('ix_duplicate_candidates_score', table_name='duplicate_candidates')
    op.drop_index('ix_duplicate_candidates_status', table_name='duplicate_candidates')
    op.drop_index('ix_duplicate_candidates_record2', table_name='duplicate_candidates')
    op.drop_index('ix_duplicate_candidates_record1', table_name='duplicate_candidates')
    
    # Drop duplicate_resolutions table
    op.drop_table('duplicate_resolutions')
    
    # Drop duplicate_candidates table
    op.drop_table('duplicate_candidates')
    
    # Drop columns from death_records table
    op.drop_column('death_records', 'deceased_maiden_name_phonetic')
    op.drop_column('death_records', 'deceased_surname_phonetic')
    op.drop_column('death_records', 'embedding')
    
    # Drop columns from marriage_records table
    op.drop_column('marriage_records', 'spouse2_surname_phonetic')
    op.drop_column('marriage_records', 'spouse1_surname_phonetic')
    op.drop_column('marriage_records', 'embedding')
    
    # Drop columns from baptism_records table
    op.drop_column('baptism_records', 'mother_maiden_name_phonetic')
    op.drop_column('baptism_records', 'father_surname_phonetic')
    op.drop_column('baptism_records', 'child_name_phonetic')
    op.drop_column('baptism_records', 'embedding')
    
    # Drop columns from persons table
    op.drop_column('persons', 'maiden_name_phonetic')
    op.drop_column('persons', 'last_name_phonetic')
    op.drop_column('persons', 'first_name_phonetic')
    op.drop_column('persons', 'embedding')
    
    # Drop vector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
