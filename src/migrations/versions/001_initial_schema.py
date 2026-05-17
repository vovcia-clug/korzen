"""initial_schema

Revision ID: 001
Revises: 
Create Date: 2026-05-16 20:44:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension first
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Create record_batches table
    op.create_table('record_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create genealogical_records table
    op.create_table('genealogical_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('record_type', sa.String(length=80), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('external_id', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['record_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create uploaded_files table
    op.create_table('uploaded_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('filepath', sa.String(length=512), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('processing_status', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['record_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create social_statuses table
    op.create_table('social_statuses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('latin_name', sa.String(length=100), nullable=False),
        sa.Column('polish_name', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('latin_name')
    )

    # Create persons table
    op.create_table('persons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gedcom_id', sa.String(length=50), nullable=True),
        sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('maiden_name', sa.String(length=100), nullable=True),
        sa.Column('gender', sa.String(length=10), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('birth_date_estimated', sa.Boolean(), nullable=True),
        sa.Column('death_date', sa.Date(), nullable=True),
        sa.Column('death_date_estimated', sa.Boolean(), nullable=True),
        sa.Column('birth_place', sa.String(length=200), nullable=True),
        sa.Column('death_place', sa.String(length=200), nullable=True),
        sa.Column('residence', sa.String(length=200), nullable=True),
        sa.Column('house_number', sa.String(length=50), nullable=True),
        sa.Column('parish', sa.String(length=200), nullable=True),
        sa.Column('father_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('mother_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('social_status_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('occupation', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['father_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['mother_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['social_status_id'], ['social_statuses.id'], ),
        sa.ForeignKeyConstraint(['source_batch_id'], ['record_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_persons_gedcom_id'), 'persons', ['gedcom_id'], unique=False)

    # Create baptism_records table
    op.create_table('baptism_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gedcom_id', sa.String(length=50), nullable=True),
        sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('record_number', sa.String(length=50), nullable=True),
        sa.Column('page_number', sa.String(length=50), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('baptism_date', sa.Date(), nullable=False),
        sa.Column('parish', sa.String(length=200), nullable=True),
        sa.Column('village', sa.String(length=200), nullable=True),
        sa.Column('house_number', sa.String(length=50), nullable=True),
        sa.Column('child_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('child_name', sa.String(length=100), nullable=True),
        sa.Column('child_gender', sa.String(length=10), nullable=True),
        sa.Column('father_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('father_name', sa.String(length=100), nullable=True),
        sa.Column('father_surname', sa.String(length=100), nullable=True),
        sa.Column('mother_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('mother_name', sa.String(length=100), nullable=True),
        sa.Column('mother_maiden_name', sa.String(length=100), nullable=True),
        sa.Column('legitimate', sa.Boolean(), nullable=True),
        sa.Column('paternal_grandfather_name', sa.String(length=100), nullable=True),
        sa.Column('paternal_grandmother_name', sa.String(length=100), nullable=True),
        sa.Column('maternal_grandfather_name', sa.String(length=100), nullable=True),
        sa.Column('maternal_grandmother_name', sa.String(length=100), nullable=True),
        sa.Column('godfather_name', sa.String(length=100), nullable=True),
        sa.Column('godmother_name', sa.String(length=100), nullable=True),
        sa.Column('godparents_location', sa.String(length=200), nullable=True),
        sa.Column('priest_name', sa.String(length=200), nullable=True),
        sa.Column('original_text_latin', sa.Text(), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),
        sa.Column('translation', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['child_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['father_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['mother_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['source_batch_id'], ['record_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baptism_records_gedcom_id'), 'baptism_records', ['gedcom_id'], unique=False)

    # Create marriage_records table
    op.create_table('marriage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gedcom_id', sa.String(length=50), nullable=True),
        sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('record_number', sa.String(length=50), nullable=True),
        sa.Column('page_number', sa.String(length=50), nullable=True),
        sa.Column('marriage_date', sa.Date(), nullable=False),
        sa.Column('parish', sa.String(length=200), nullable=True),
        sa.Column('village', sa.String(length=200), nullable=True),
        sa.Column('spouse1_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('spouse1_name', sa.String(length=100), nullable=True),
        sa.Column('spouse1_surname', sa.String(length=100), nullable=True),
        sa.Column('spouse1_status', sa.String(length=50), nullable=True),
        sa.Column('spouse1_parish', sa.String(length=200), nullable=True),
        sa.Column('spouse1_residence', sa.String(length=200), nullable=True),
        sa.Column('spouse1_father_name', sa.String(length=100), nullable=True),
        sa.Column('spouse1_mother_name', sa.String(length=100), nullable=True),
        sa.Column('spouse1_age', sa.Integer(), nullable=True),
        sa.Column('spouse2_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('spouse2_name', sa.String(length=100), nullable=True),
        sa.Column('spouse2_surname', sa.String(length=100), nullable=True),
        sa.Column('spouse2_maiden_name', sa.String(length=100), nullable=True),
        sa.Column('spouse2_status', sa.String(length=50), nullable=True),
        sa.Column('spouse2_parish', sa.String(length=200), nullable=True),
        sa.Column('spouse2_residence', sa.String(length=200), nullable=True),
        sa.Column('spouse2_father_name', sa.String(length=100), nullable=True),
        sa.Column('spouse2_mother_name', sa.String(length=100), nullable=True),
        sa.Column('spouse2_age', sa.Integer(), nullable=True),
        sa.Column('banns_count', sa.Integer(), nullable=True),
        sa.Column('banns_dates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('witnesses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('priest_name', sa.String(length=200), nullable=True),
        sa.Column('original_text_latin', sa.Text(), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),
        sa.Column('translation', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_batch_id'], ['record_batches.id'], ),
        sa.ForeignKeyConstraint(['spouse1_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['spouse2_id'], ['persons.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_marriage_records_gedcom_id'), 'marriage_records', ['gedcom_id'], unique=False)

    # Create death_records table
    op.create_table('death_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gedcom_id', sa.String(length=50), nullable=True),
        sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('record_number', sa.String(length=50), nullable=True),
        sa.Column('page_number', sa.String(length=50), nullable=True),
        sa.Column('death_date', sa.Date(), nullable=False),
        sa.Column('burial_date', sa.Date(), nullable=True),
        sa.Column('parish', sa.String(length=200), nullable=True),
        sa.Column('village', sa.String(length=200), nullable=True),
        sa.Column('cemetery', sa.String(length=200), nullable=True),
        sa.Column('deceased_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deceased_name', sa.String(length=100), nullable=True),
        sa.Column('deceased_surname', sa.String(length=100), nullable=True),
        sa.Column('deceased_maiden_name', sa.String(length=100), nullable=True),
        sa.Column('marital_status', sa.String(length=50), nullable=True),
        sa.Column('age_years', sa.Integer(), nullable=True),
        sa.Column('age_description', sa.String(length=100), nullable=True),
        sa.Column('cause_of_death', sa.Text(), nullable=True),
        sa.Column('sacraments_received', sa.Boolean(), nullable=True),
        sa.Column('sacraments_details', sa.Text(), nullable=True),
        sa.Column('spouse_name', sa.String(length=100), nullable=True),
        sa.Column('father_name', sa.String(length=100), nullable=True),
        sa.Column('mother_name', sa.String(length=100), nullable=True),
        sa.Column('priest_name', sa.String(length=200), nullable=True),
        sa.Column('original_text_latin', sa.Text(), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),
        sa.Column('translation', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['deceased_id'], ['persons.id'], ),
        sa.ForeignKeyConstraint(['source_batch_id'], ['record_batches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_death_records_gedcom_id'), 'death_records', ['gedcom_id'], unique=False)

    # Create godparent_relationships table
    op.create_table('godparent_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('baptism_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('godparent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('godparent_type', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['baptism_record_id'], ['baptism_records.id'], ),
        sa.ForeignKeyConstraint(['godparent_id'], ['persons.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create witness_relationships table
    op.create_table('witness_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('marriage_record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('witness_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('witness_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['marriage_record_id'], ['marriage_records.id'], ),
        sa.ForeignKeyConstraint(['witness_id'], ['persons.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('witness_relationships')
    op.drop_table('godparent_relationships')
    op.drop_index(op.f('ix_death_records_gedcom_id'), table_name='death_records')
    op.drop_table('death_records')
    op.drop_index(op.f('ix_marriage_records_gedcom_id'), table_name='marriage_records')
    op.drop_table('marriage_records')
    op.drop_index(op.f('ix_baptism_records_gedcom_id'), table_name='baptism_records')
    op.drop_table('baptism_records')
    op.drop_index(op.f('ix_persons_gedcom_id'), table_name='persons')
    op.drop_table('persons')
    op.drop_table('social_statuses')
    op.drop_table('uploaded_files')
    op.drop_table('genealogical_records')
    op.drop_table('record_batches')
