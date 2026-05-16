"""add_gedcom_id_tracking_to_persons

Revision ID: add_gedcom_id_001
Revises: 
Create Date: 2026-05-16 17:09:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_gedcom_id_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add gedcom_id and source_batch_id fields to persons table for duplicate detection."""
    # Add gedcom_id column with index for fast lookups
    op.add_column('persons', sa.Column('gedcom_id', sa.String(length=50), nullable=True))
    op.create_index('ix_persons_gedcom_id', 'persons', ['gedcom_id'], unique=False)
    
    # Add source_batch_id column to track which batch imported the person
    op.add_column('persons', sa.Column('source_batch_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign key constraint to record_batches table
    op.create_foreign_key(
        'fk_persons_source_batch_id',
        'persons',
        'record_batches',
        ['source_batch_id'],
        ['id']
    )


def downgrade():
    """Remove gedcom_id and source_batch_id fields from persons table."""
    # Drop foreign key constraint
    op.drop_constraint('fk_persons_source_batch_id', 'persons', type_='foreignkey')
    
    # Drop columns
    op.drop_index('ix_persons_gedcom_id', table_name='persons')
    op.drop_column('persons', 'source_batch_id')
    op.drop_column('persons', 'gedcom_id')
