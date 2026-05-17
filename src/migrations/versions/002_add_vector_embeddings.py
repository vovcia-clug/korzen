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
    
    # Add vector embedding and phonetic columns to persons table
    op.add_column('persons', sa.Column('embedding', Vector(128), nullable=True))
    op.add_column('persons', sa.Column('first_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('persons', sa.Column('last_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('persons', sa.Column('maiden_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add vector embedding and phonetic columns to baptism_records table
    op.add_column('baptism_records', sa.Column('embedding', Vector(128), nullable=True))
    op.add_column('baptism_records', sa.Column('child_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('baptism_records', sa.Column('father_surname_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('baptism_records', sa.Column('mother_maiden_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add vector embedding and phonetic columns to marriage_records table
    op.add_column('marriage_records', sa.Column('embedding', Vector(128), nullable=True))
    op.add_column('marriage_records', sa.Column('spouse1_surname_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('marriage_records', sa.Column('spouse2_surname_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add vector embedding and phonetic columns to death_records table
    op.add_column('death_records', sa.Column('embedding', Vector(128), nullable=True))
    op.add_column('death_records', sa.Column('deceased_surname_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('death_records', sa.Column('deceased_maiden_name_phonetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create duplicate_candidates table
    op.create_table('duplicate_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_type', sa.String(length=50), nullable=False),
        sa.Column('record1_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record2_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vector_similarity', sa.Float(), nullable=False),
        sa.Column('phonetic_similarity', sa.Float(), nullable=True),
        sa.Column('date_similarity', sa.Float(), nullable=True),
        sa.Column('location_similarity', sa.Float(), nullable=True),
        sa.Column('composite_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('detection_method', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create duplicate_resolutions table
    op.create_table('duplicate_resolutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('kept_record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('merged_record_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=100), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('merged_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['duplicate_candidates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes on duplicate_candidates
    op.create_index('ix_duplicate_candidates_record1', 'duplicate_candidates', ['record_type', 'record1_id'], unique=False)
    op.create_index('ix_duplicate_candidates_record2', 'duplicate_candidates', ['record_type', 'record2_id'], unique=False)
    op.create_index('ix_duplicate_candidates_status', 'duplicate_candidates', ['status'], unique=False)
    op.create_index('ix_duplicate_candidates_score', 'duplicate_candidates', ['composite_score'], unique=False)
    
    # Create HNSW indexes for vector similarity search
    op.execute('CREATE INDEX ix_persons_embedding_hnsw ON persons USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX ix_baptism_records_embedding_hnsw ON baptism_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX ix_marriage_records_embedding_hnsw ON marriage_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')
    op.execute('CREATE INDEX ix_death_records_embedding_hnsw ON death_records USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)')


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
