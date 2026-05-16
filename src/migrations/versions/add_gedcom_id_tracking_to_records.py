"""add_gedcom_id_tracking_to_records

Revision ID: add_gedcom_id_002
Revises: add_gedcom_id_001
Create Date: 2026-05-16 17:27:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_gedcom_id_002'
down_revision = 'add_gedcom_id_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add gedcom_id and source_batch_id fields to baptism, marriage, and death record tables."""
    
    # Add fields to baptism_records table
    op.add_column('baptism_records', sa.Column('gedcom_id', sa.String(length=50), nullable=True))
    op.create_index('ix_baptism_records_gedcom_id', 'baptism_records', ['gedcom_id'], unique=False)
    op.add_column('baptism_records', sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_baptism_records_source_batch_id',
        'baptism_records',
        'record_batches',
        ['source_batch_id'],
        ['id']
    )
    
    # Add fields to marriage_records table
    op.add_column('marriage_records', sa.Column('gedcom_id', sa.String(length=50), nullable=True))
    op.create_index('ix_marriage_records_gedcom_id', 'marriage_records', ['gedcom_id'], unique=False)
    op.add_column('marriage_records', sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_marriage_records_source_batch_id',
        'marriage_records',
        'record_batches',
        ['source_batch_id'],
        ['id']
    )
    
    # Add fields to death_records table
    op.add_column('death_records', sa.Column('gedcom_id', sa.String(length=50), nullable=True))
    op.create_index('ix_death_records_gedcom_id', 'death_records', ['gedcom_id'], unique=False)
    op.add_column('death_records', sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_death_records_source_batch_id',
        'death_records',
        'record_batches',
        ['source_batch_id'],
        ['id']
    )


def downgrade():
    """Remove gedcom_id and source_batch_id fields from record tables."""
    
    # Drop from death_records
    op.drop_constraint('fk_death_records_source_batch_id', 'death_records', type_='foreignkey')
    op.drop_index('ix_death_records_gedcom_id', table_name='death_records')
    op.drop_column('death_records', 'source_batch_id')
    op.drop_column('death_records', 'gedcom_id')
    
    # Drop from marriage_records
    op.drop_constraint('fk_marriage_records_source_batch_id', 'marriage_records', type_='foreignkey')
    op.drop_index('ix_marriage_records_gedcom_id', table_name='marriage_records')
    op.drop_column('marriage_records', 'source_batch_id')
    op.drop_column('marriage_records', 'gedcom_id')
    
    # Drop from baptism_records
    op.drop_constraint('fk_baptism_records_source_batch_id', 'baptism_records', type_='foreignkey')
    op.drop_index('ix_baptism_records_gedcom_id', table_name='baptism_records')
    op.drop_column('baptism_records', 'source_batch_id')
    op.drop_column('baptism_records', 'gedcom_id')
