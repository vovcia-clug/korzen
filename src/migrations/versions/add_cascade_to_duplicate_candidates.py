"""add cascade delete to duplicate_candidates

Revision ID: add_cascade_duplicates
Revises: ce299e9dbdee
Create Date: 2026-05-22 11:52:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_cascade_duplicates'
down_revision = 'ce299e9dbdee'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add foreign key constraints with CASCADE delete to duplicate_candidates table.
    This ensures that when a record is deleted, all associated duplicate candidates are also deleted.
    
    Note: We cannot add actual FK constraints because record1_id and record2_id can reference
    different tables (persons, baptism_records, marriage_records, death_records) based on record_type.
    
    Instead, we'll:
    1. Clean up orphaned entries first
    2. Add a database trigger to handle cascade deletes
    3. Update the application code to handle this properly
    """
    
    # First, clean up any orphaned duplicate candidates
    # This SQL will delete candidates where the referenced records don't exist
    
    # Clean up orphaned person duplicates
    op.execute("""
        DELETE FROM duplicate_candidates dc
        WHERE dc.record_type = 'person'
        AND (
            NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = dc.record1_id)
            OR NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = dc.record2_id)
        )
    """)
    
    # Clean up orphaned baptism duplicates
    op.execute("""
        DELETE FROM duplicate_candidates dc
        WHERE dc.record_type = 'baptism'
        AND (
            NOT EXISTS (SELECT 1 FROM baptism_records b WHERE b.id = dc.record1_id)
            OR NOT EXISTS (SELECT 1 FROM baptism_records b WHERE b.id = dc.record2_id)
        )
    """)
    
    # Clean up orphaned marriage duplicates
    op.execute("""
        DELETE FROM duplicate_candidates dc
        WHERE dc.record_type = 'marriage'
        AND (
            NOT EXISTS (SELECT 1 FROM marriage_records m WHERE m.id = dc.record1_id)
            OR NOT EXISTS (SELECT 1 FROM marriage_records m WHERE m.id = dc.record2_id)
        )
    """)
    
    # Clean up orphaned death duplicates
    op.execute("""
        DELETE FROM duplicate_candidates dc
        WHERE dc.record_type = 'death'
        AND (
            NOT EXISTS (SELECT 1 FROM death_records d WHERE d.id = dc.record1_id)
            OR NOT EXISTS (SELECT 1 FROM death_records d WHERE d.id = dc.record2_id)
        )
    """)
    
    # Create a function to clean up duplicate candidates when records are deleted
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_duplicate_candidates()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Delete duplicate candidates that reference the deleted record
            DELETE FROM duplicate_candidates
            WHERE (record1_id = OLD.id OR record2_id = OLD.id)
            AND record_type = TG_ARGV[0];
            
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create triggers for each table
    op.execute("""
        CREATE TRIGGER cleanup_person_duplicates
        BEFORE DELETE ON persons
        FOR EACH ROW
        EXECUTE FUNCTION cleanup_duplicate_candidates('person');
    """)
    
    op.execute("""
        CREATE TRIGGER cleanup_baptism_duplicates
        BEFORE DELETE ON baptism_records
        FOR EACH ROW
        EXECUTE FUNCTION cleanup_duplicate_candidates('baptism');
    """)
    
    op.execute("""
        CREATE TRIGGER cleanup_marriage_duplicates
        BEFORE DELETE ON marriage_records
        FOR EACH ROW
        EXECUTE FUNCTION cleanup_duplicate_candidates('marriage');
    """)
    
    op.execute("""
        CREATE TRIGGER cleanup_death_duplicates
        BEFORE DELETE ON death_records
        FOR EACH ROW
        EXECUTE FUNCTION cleanup_duplicate_candidates('death');
    """)


def downgrade():
    """Remove the triggers and function."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS cleanup_person_duplicates ON persons")
    op.execute("DROP TRIGGER IF EXISTS cleanup_baptism_duplicates ON baptism_records")
    op.execute("DROP TRIGGER IF EXISTS cleanup_marriage_duplicates ON marriage_records")
    op.execute("DROP TRIGGER IF EXISTS cleanup_death_duplicates ON death_records")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS cleanup_duplicate_candidates()")
