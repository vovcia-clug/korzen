import os
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import UploadedFile, Person, BaptismRecord, MarriageRecord, DeathRecord, SocialStatus, DuplicateCandidate, DuplicateResolution
from ..gedcom_parser import GedcomParser
from ..services.age_graph_importer import AgeGraphImporter

logger = logging.getLogger(__name__)

bp = Blueprint("main", __name__)


def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'ged', 'gedcom'}


def get_uploaded_files():
    """Get list of uploaded files with metadata."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    files_list = []
    
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            
            # Only include files (not directories) and only GEDCOM files
            if os.path.isfile(filepath) and allowed_file(filename):
                file_stat = os.stat(filepath)
                files_list.append({
                    'name': filename,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime)
                })
    
    # Sort by modified date, newest first
    files_list.sort(key=lambda x: x['modified'], reverse=True)
    return files_list


def get_sort_column(model, sort_by, default_column):
    """Get the sort column for a model, with fallback to default."""
    if sort_by and hasattr(model, sort_by):
        return getattr(model, sort_by)
    return default_column


@bp.route("/")
def index():
    """Main page with upload form."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'uploaded_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = UploadedFile.query
        sort_column = get_sort_column(UploadedFile, sort_by, UploadedFile.uploaded_at)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template("index.html", files=pagination.items, pagination=pagination)
    except Exception as e:
        logger.error(f"Error loading index page: {e}")
        db.session.rollback()
        return render_template("index.html", files=[], error=str(e), pagination=None)


@bp.route("/upload", methods=["POST"])
def upload_file():
    """Handle GEDCOM file upload and processing."""
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files["file"]
    
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400
    
    # Store filename for type safety (ensures it's not None)
    original_filename = file.filename
    
    if not allowed_file(original_filename):
        return jsonify({"error": "Invalid file type. Please upload a .ged or .gedcom file"}), 400
    
    try:
        # Ensure upload directory exists
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save file with secure filename
        filename = secure_filename(original_filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Calculate file size
        file_size = os.path.getsize(filepath)
        
        # Get relative path from project root
        relative_filepath = os.path.relpath(filepath, start=os.getcwd())
        
        # Create database record for uploaded file
        uploaded_file = UploadedFile(
            filename=filename,
            original_filename=original_filename,
            filepath=relative_filepath,
            file_size=file_size,
            mime_type=file.content_type,
            processing_status='uploaded'
        )
        
        db.session.add(uploaded_file)
        db.session.commit()
        
        return jsonify({
            "message": "File uploaded successfully",
            "filename": filename,
            "file_id": str(uploaded_file.id)
        }), 201
    
    except Exception as e:
        # Rollback any database changes on error
        db.session.rollback()
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@bp.route("/parse/<file_id>", methods=["POST"])
def parse_gedcom(file_id):
    """Parse an uploaded GEDCOM file and import data into the database."""
    try:
        # Get the uploaded file record
        uploaded_file = db.session.get(UploadedFile, file_id)
        
        if not uploaded_file:
            return jsonify({"error": "File not found"}), 404
        
        # Check if file exists on disk
        if not os.path.exists(uploaded_file.filepath):
            return jsonify({"error": "File not found on disk"}), 404
        
        # Check if already processing or completed
        if uploaded_file.processing_status == 'processing':
            return jsonify({"error": "File is already being processed"}), 409
        
        if uploaded_file.processing_status == 'completed':
            return jsonify({"message": "File has already been processed"}), 200
        
        # Create parser and import data
        parser = GedcomParser(uploaded_file.filepath, file_id)
        stats = parser.parse_and_import()
        
        return jsonify({
            "message": "GEDCOM file parsed successfully",
            "statistics": stats
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Parsing failed: {str(e)}"}), 500


@bp.route("/files", methods=["GET"])
def list_uploaded_files():
    """Get list of all uploaded files with their processing status."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'uploaded_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = UploadedFile.query
        sort_column = get_sort_column(UploadedFile, sort_by, UploadedFile.uploaded_at)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        files_data = []
        for file in pagination.items:
            files_data.append({
                'id': str(file.id),
                'filename': file.filename,
                'original_filename': file.original_filename,
                'file_size': file.file_size,
                'uploaded_at': file.uploaded_at.isoformat(),
                'processing_status': file.processing_status,
                'batch_id': str(file.batch_id) if file.batch_id else None
            })
        
        return jsonify({
            "data": files_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list files: {str(e)}"}), 500


@bp.route("/persons")
def list_persons():
    """Display list of all persons in the database."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'last_name')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Eagerly load parent relationships to avoid N+1 queries
        from sqlalchemy.orm import joinedload
        
        # Build query with sorting
        query = Person.query.options(
            joinedload(Person.father),
            joinedload(Person.mother)
        )
        
        # Apply sorting based on sort_by parameter
        if sort_by == 'last_name':
            if sort_order == 'asc':
                query = query.order_by(Person.last_name.asc().nullslast(), Person.first_name.asc().nullslast())
            else:
                query = query.order_by(Person.last_name.desc().nullslast(), Person.first_name.desc().nullslast())
        elif sort_by == 'first_name':
            if sort_order == 'asc':
                query = query.order_by(Person.first_name.asc().nullslast(), Person.last_name.asc().nullslast())
            else:
                query = query.order_by(Person.first_name.desc().nullslast(), Person.last_name.desc().nullslast())
        elif sort_by == 'birth_date':
            if sort_order == 'asc':
                query = query.order_by(Person.birth_date.asc().nullslast())
            else:
                query = query.order_by(Person.birth_date.desc().nullslast())
        elif sort_by == 'birth_place':
            if sort_order == 'asc':
                query = query.order_by(Person.birth_place.asc().nullslast())
            else:
                query = query.order_by(Person.birth_place.desc().nullslast())
        else:
            sort_column = get_sort_column(Person, sort_by, Person.last_name)
            if sort_order == 'asc':
                query = query.order_by(sort_column.asc().nullslast())
            else:
                query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template("persons.html", persons=pagination.items, pagination=pagination, now=datetime.now)
        
    except Exception as e:
        return render_template("persons.html", persons=[], error=str(e), pagination=None, now=datetime.now)


@bp.route("/api/persons", methods=["GET"])
def api_list_persons():
    """API endpoint to get list of all persons with their details."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'last_name')
        sort_order = request.args.get('sort_order', 'asc')
        
        # Build query with sorting
        query = Person.query
        
        # Apply sorting based on sort_by parameter with special handling for name and date fields
        if sort_by == 'last_name':
            if sort_order == 'asc':
                query = query.order_by(Person.last_name.asc().nullslast(), Person.first_name.asc().nullslast())
            else:
                query = query.order_by(Person.last_name.desc().nullslast(), Person.first_name.desc().nullslast())
        elif sort_by == 'first_name':
            if sort_order == 'asc':
                query = query.order_by(Person.first_name.asc().nullslast(), Person.last_name.asc().nullslast())
            else:
                query = query.order_by(Person.first_name.desc().nullslast(), Person.last_name.desc().nullslast())
        elif sort_by == 'birth_date':
            if sort_order == 'asc':
                query = query.order_by(Person.birth_date.asc().nullslast())
            else:
                query = query.order_by(Person.birth_date.desc().nullslast())
        elif sort_by == 'birth_place':
            if sort_order == 'asc':
                query = query.order_by(Person.birth_place.asc().nullslast())
            else:
                query = query.order_by(Person.birth_place.desc().nullslast())
        else:
            sort_column = get_sort_column(Person, sort_by, Person.last_name)
            if sort_order == 'asc':
                query = query.order_by(sort_column.asc().nullslast())
            else:
                query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        persons_data = []
        for person in pagination.items:
            persons_data.append({
                'id': str(person.id),
                'first_name': person.first_name,
                'last_name': person.last_name,
                'father': person.father,
                'mother': person.mother,
                'maiden_name': person.maiden_name,
                'gender': person.gender,
                'birth_date': person.birth_date.isoformat() if person.birth_date else None,
                'birth_place': person.birth_place,
                'death_date': person.death_date.isoformat() if person.death_date else None,
                'death_place': person.death_place,
                'occupation': person.occupation,
                'residence': person.residence,
                'parish': person.parish
            })
        
        return jsonify({
            "data": persons_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list persons: {str(e)}"}), 500


@bp.route("/api/persons/<person_id>/details", methods=["GET"])
def get_person_details(person_id):
    """
    API endpoint to fetch complete person details with all relationships.
    
    Returns comprehensive information about a person including:
    - All basic fields (30+ fields)
    - Parent relationships (father, mother)
    - Children relationships
    - Social status
    - Marriage records (with spouse info, dates, locations, witnesses)
    - Baptism records (as child, father, or mother)
    - Death records (with all details)
    """
    try:
        # Build query with eager loading for all relationships
        query = Person.query.options(
            # Parent relationships
            joinedload(Person.father),
            joinedload(Person.mother),
            # Social status
            joinedload(Person.social_status),
            # Children relationships (both as father and mother)
            selectinload(Person.children_as_father),
            selectinload(Person.children_as_mother),
            # Marriage records with spouse relationships
            selectinload(Person.marriages_as_spouse1).joinedload(MarriageRecord.spouse2),
            selectinload(Person.marriages_as_spouse2).joinedload(MarriageRecord.spouse1),
            # Baptism records in all roles
            selectinload(Person.baptism_as_child),
            selectinload(Person.baptism_as_father).joinedload(BaptismRecord.child),
            selectinload(Person.baptism_as_mother).joinedload(BaptismRecord.child),
            # Death records
            selectinload(Person.death_records)
        )
        
        # Fetch person by ID
        person = query.filter(Person.id == person_id).first()
        
        if not person:
            return jsonify({"error": "Person not found"}), 404
        
        # Helper function to format date with estimated flag
        def format_date(date_value, estimated_flag):
            if not date_value:
                return None
            return {
                "date": date_value.isoformat(),
                "estimated": estimated_flag if estimated_flag is not None else False
            }
        
        # Helper function to format person reference
        def format_person_ref(person_obj):
            if not person_obj:
                return None
            return {
                "id": str(person_obj.id),
                "name": f"{person_obj.first_name or ''} {person_obj.last_name or ''}".strip() or "Unknown"
            }
        
        # Build basic information
        basic_info = {
            "first_name": person.first_name,
            "last_name": person.last_name,
            "maiden_name": person.maiden_name,
            "gender": person.gender,
            "birth_date": format_date(person.birth_date, person.birth_date_estimated),
            "death_date": format_date(person.death_date, person.death_date_estimated),
            "birth_place": person.birth_place,
            "death_place": person.death_place,
            "residence": person.residence,
            "house_number": person.house_number,
            "parish": person.parish,
            "occupation": person.occupation,
            "notes": person.notes,
            "gedcom_id": person.gedcom_id,
            "social_status": {
                "latin_name": person.social_status.latin_name,
                "polish_name": person.social_status.polish_name
            } if person.social_status else None
        }
        
        # Build parents information
        parents = {
            "father": format_person_ref(person.father),
            "mother": format_person_ref(person.mother)
        }
        
        # Build children list (combine children as father and as mother, removing duplicates)
        children_dict = {}
        for child in person.children_as_father:
            children_dict[str(child.id)] = {
                "id": str(child.id),
                "name": f"{child.first_name or ''} {child.last_name or ''}".strip() or "Unknown",
                "birth_date": child.birth_date.isoformat() if child.birth_date else None
            }
        for child in person.children_as_mother:
            if str(child.id) not in children_dict:
                children_dict[str(child.id)] = {
                    "id": str(child.id),
                    "name": f"{child.first_name or ''} {child.last_name or ''}".strip() or "Unknown",
                    "birth_date": child.birth_date.isoformat() if child.birth_date else None
                }
        children = list(children_dict.values())
        
        # Build marriages list (combine marriages as spouse1 and spouse2)
        marriages = []
        
        for marriage in person.marriages_as_spouse1:
            marriages.append({
                "id": str(marriage.id),
                "marriage_date": marriage.marriage_date.isoformat() if marriage.marriage_date else None,
                "spouse": format_person_ref(marriage.spouse2),
                "parish": marriage.parish,
                "village": marriage.village,
                "spouse_status": marriage.spouse2_status,
                "spouse_age": marriage.spouse2_age,
                "spouse_residence": marriage.spouse2_residence,
                "banns_count": marriage.banns_count,
                "banns_dates": marriage.banns_dates if marriage.banns_dates else [],
                "witnesses": marriage.witnesses if marriage.witnesses else [],
                "priest_name": marriage.priest_name,
                "notes": marriage.notes
            })
        
        for marriage in person.marriages_as_spouse2:
            marriages.append({
                "id": str(marriage.id),
                "marriage_date": marriage.marriage_date.isoformat() if marriage.marriage_date else None,
                "spouse": format_person_ref(marriage.spouse1),
                "parish": marriage.parish,
                "village": marriage.village,
                "spouse_status": marriage.spouse1_status,
                "spouse_age": marriage.spouse1_age,
                "spouse_residence": marriage.spouse1_residence,
                "banns_count": marriage.banns_count,
                "banns_dates": marriage.banns_dates if marriage.banns_dates else [],
                "witnesses": marriage.witnesses if marriage.witnesses else [],
                "priest_name": marriage.priest_name,
                "notes": marriage.notes
            })
        
        # Build baptism records
        baptisms = []
        
        # Baptism as child
        for baptism in person.baptism_as_child:
            baptisms.append({
                "id": str(baptism.id),
                "role": "child",
                "baptism_date": baptism.baptism_date.isoformat() if baptism.baptism_date else None,
                "birth_date": baptism.birth_date.isoformat() if baptism.birth_date else None,
                "parish": baptism.parish,
                "village": baptism.village,
                "house_number": baptism.house_number,
                "child_name": baptism.child_name,
                "child_gender": baptism.child_gender,
                "father_name": f"{baptism.father_name or ''} {baptism.father_surname or ''}".strip() if baptism.father_name or baptism.father_surname else None,
                "mother_name": f"{baptism.mother_name or ''} {baptism.mother_maiden_name or ''}".strip() if baptism.mother_name or baptism.mother_maiden_name else None,
                "legitimate": baptism.legitimate,
                "godfather_name": baptism.godfather_name,
                "godmother_name": baptism.godmother_name,
                "godparents_location": baptism.godparents_location,
                "priest_name": baptism.priest_name,
                "notes": baptism.notes
            })
        
        # Baptism as father
        for baptism in person.baptism_as_father:
            baptisms.append({
                "id": str(baptism.id),
                "role": "father",
                "baptism_date": baptism.baptism_date.isoformat() if baptism.baptism_date else None,
                "birth_date": baptism.birth_date.isoformat() if baptism.birth_date else None,
                "parish": baptism.parish,
                "village": baptism.village,
                "child": format_person_ref(baptism.child),
                "child_name": baptism.child_name,
                "child_gender": baptism.child_gender,
                "mother_name": f"{baptism.mother_name or ''} {baptism.mother_maiden_name or ''}".strip() if baptism.mother_name or baptism.mother_maiden_name else None,
                "legitimate": baptism.legitimate,
                "godfather_name": baptism.godfather_name,
                "godmother_name": baptism.godmother_name,
                "priest_name": baptism.priest_name
            })
        
        # Baptism as mother
        for baptism in person.baptism_as_mother:
            baptisms.append({
                "id": str(baptism.id),
                "role": "mother",
                "baptism_date": baptism.baptism_date.isoformat() if baptism.baptism_date else None,
                "birth_date": baptism.birth_date.isoformat() if baptism.birth_date else None,
                "parish": baptism.parish,
                "village": baptism.village,
                "child": format_person_ref(baptism.child),
                "child_name": baptism.child_name,
                "child_gender": baptism.child_gender,
                "father_name": f"{baptism.father_name or ''} {baptism.father_surname or ''}".strip() if baptism.father_name or baptism.father_surname else None,
                "legitimate": baptism.legitimate,
                "godfather_name": baptism.godfather_name,
                "godmother_name": baptism.godmother_name,
                "priest_name": baptism.priest_name
            })
        
        # Build death records
        deaths = []
        for death in person.death_records:
            deaths.append({
                "id": str(death.id),
                "death_date": death.death_date.isoformat() if death.death_date else None,
                "burial_date": death.burial_date.isoformat() if death.burial_date else None,
                "parish": death.parish,
                "village": death.village,
                "cemetery": death.cemetery,
                "marital_status": death.marital_status,
                "age_years": death.age_years,
                "age_description": death.age_description,
                "cause_of_death": death.cause_of_death,
                "sacraments_received": death.sacraments_received,
                "sacraments_details": death.sacraments_details,
                "spouse_name": death.spouse_name,
                "father_name": death.father_name,
                "mother_name": death.mother_name,
                "priest_name": death.priest_name,
                "notes": death.notes
            })
        
        # Build complete response
        response = {
            "id": str(person.id),
            "basic_info": basic_info,
            "parents": parents,
            "children": children,
            "marriages": marriages,
            "baptisms": baptisms,
            "deaths": deaths
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error fetching person details: {e}")
        return jsonify({"error": f"Failed to fetch person details: {str(e)}"}), 500


@bp.route("/reset-database", methods=["POST"])
def reset_database():
    """Reset the database by deleting all data from all tables and clearing AGE graph."""
    try:
        # Delete all records from tables (in correct order to respect foreign keys)
        # Using CASCADE to handle foreign key constraints automatically
        db.session.execute(text("TRUNCATE TABLE godparent_relationships CASCADE"))
        db.session.execute(text("TRUNCATE TABLE witness_relationships CASCADE"))
        db.session.execute(text("TRUNCATE TABLE baptism_records CASCADE"))
        db.session.execute(text("TRUNCATE TABLE marriage_records CASCADE"))
        db.session.execute(text("TRUNCATE TABLE death_records CASCADE"))
        db.session.execute(text("TRUNCATE TABLE persons CASCADE"))
        db.session.execute(text("TRUNCATE TABLE social_statuses CASCADE"))
        db.session.execute(text("TRUNCATE TABLE uploaded_files CASCADE"))
        db.session.execute(text("TRUNCATE TABLE genealogical_records CASCADE"))
        db.session.execute(text("TRUNCATE TABLE record_batches CASCADE"))
        db.session.commit()
        
        # Reset AGE graph - clear all vertices and edges
        graph_cleared = False
        graph_warning = None
        
        try:
            # Set search path for AGE
            db.session.execute(text("SET search_path = ag_catalog, '$user', public"))
            
            # Method 1: Try to drop and recreate the graph (cleanest approach)
            try:
                db.session.execute(text("SELECT drop_graph('genealogy', true)"))
                db.session.execute(text("SELECT create_graph('genealogy')"))
                db.session.commit()
                graph_cleared = True
            except Exception as drop_error:
                # If drop/create fails, try to clear all data using Cypher
                db.session.rollback()
                
                # Method 2: Delete all edges and vertices using Cypher
                try:
                    # Delete all edges first
                    db.session.execute(text("""
                        SELECT * FROM cypher('genealogy', $$
                            MATCH ()-[r]->()
                            DELETE r
                        $$) as (result agtype)
                    """))
                    
                    # Delete all vertices
                    db.session.execute(text("""
                        SELECT * FROM cypher('genealogy', $$
                            MATCH (n)
                            DELETE n
                        $$) as (result agtype)
                    """))
                    
                    db.session.commit()
                    graph_cleared = True
                except Exception as cypher_error:
                    db.session.rollback()
                    graph_warning = f"Failed to clear graph: {str(drop_error)}; Cypher delete also failed: {str(cypher_error)}"
            
            if graph_cleared:
                return jsonify({
                    "message": "Database and AGE graph reset successfully. All data has been deleted."
                }), 200
            else:
                return jsonify({
                    "message": "Database reset successfully. All relational data has been deleted.",
                    "warning": graph_warning or "AGE graph could not be cleared"
                }), 200
            
        except Exception as age_error:
            # If AGE operations fail completely, still report success for relational tables
            db.session.rollback()
            
            return jsonify({
                "message": "Database reset successfully. All relational data has been deleted.",
                "warning": f"AGE graph operations failed: {str(age_error)}"
            }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to reset database: {str(e)}"}), 500


@bp.route("/graph")
def graph_visualizer():
    """Display the graph visualizer page."""
    return render_template("graph.html")


@bp.route("/api/graph/data", methods=["GET"])
def get_graph_data():
    """
    API endpoint to fetch graph data for family tree visualization.
    Returns nodes and edges in a format suitable for visualization libraries.
    Supports optional root_id parameter to start from a specific ancestor.
    Focuses on PARENT_OF and MARRIED_TO relationships for genealogy tree.
    """
    try:
        # Get optional parameters
        limit = request.args.get('limit', 100, type=int)
        root_id = request.args.get('root_id', None, type=str)
        depth = request.args.get('depth', 3, type=int)  # How many generations to show
        
        # Set search path for AGE
        db.session.execute(text("SET search_path = ag_catalog, '$user', public;"))
        
        # Execute Cypher query to get persons and family relationships
        # If root_id is provided, start from that ancestor and show descendants
        # Focus on PARENT_OF (parent to child) and MARRIED_TO relationships
        if root_id:
            # Query for descendants: start from root and follow PARENT_OF relationships
            # PARENT_OF goes from parent to child, so we follow outgoing edges
            # Use text() with bindparams to avoid SQLAlchemy treating :PARENT_OF as a bind parameter
            query_str = f"""
                SELECT * FROM cypher('genealogy', $$
                    MATCH (root:Person {{uuid: '{root_id}'}})
                    OPTIONAL MATCH path = (root)-[r_parent:PARENT_OF*0..{depth}]->(descendant:Person)
                    WITH DISTINCT descendant AS p
                    LIMIT {limit}
                    OPTIONAL MATCH (p)-[r]->(related)
                    OPTIONAL MATCH (p)-[fs]->(source:Source)
                    OPTIONAL MATCH (related)-[rfs]->(related_source:Source)
                    RETURN p, r, related, source, related_source
                $$) AS (person agtype, relationship agtype, related agtype, source agtype, related_source agtype);
            """
            query = text(query_str)
        else:
            # Default query - get persons with all relationships
            query = text(f"""
                SELECT * FROM cypher('genealogy', $$
                    MATCH (p:Person)
                    WITH p LIMIT {limit}
                    OPTIONAL MATCH (p)-[r]->(related)
                    OPTIONAL MATCH (p)-[fs]->(source:Source)
                    OPTIONAL MATCH (related)-[rfs]->(related_source:Source)
                    RETURN p, r, related, source, related_source
                $$) AS (person agtype, relationship agtype, related agtype, source agtype, related_source agtype);
            """)
        
        result = db.session.execute(query)
        
        nodes = {}
        edges = []
        
        for row in result:
            person_data = row[0]
            relationship_data = row[1]
            related_data = row[2]
            source_data = row[3]
            related_source_data = row[4]
            
            # Parse person node - AGE returns agtype which needs special handling
            if person_data and str(person_data) != 'null':
                try:
                    # AGE returns data in a special format, extract the JSON part
                    person_str = str(person_data)
                    # Remove AGE wrapper if present
                    if '::vertex' in person_str:
                        person_str = person_str.split('::')[0].strip()
                    
                    person = json.loads(person_str)
                    if isinstance(person, dict):
                        # Extract properties - AGE format has properties nested
                        props = person.get('properties', person)
                        node_id = props.get('uuid')
                        
                        if node_id and node_id not in nodes:
                            # Parse source information
                            source_name = None
                            if source_data and str(source_data) != 'null':
                                try:
                                    source_str = str(source_data)
                                    if '::vertex' in source_str:
                                        source_str = source_str.split('::')[0].strip()
                                    source = json.loads(source_str)
                                    if isinstance(source, dict):
                                        source_props = source.get('properties', source)
                                        source_name = source_props.get('source_name')
                                except (json.JSONDecodeError, ValueError) as e:
                                    logger.warning(f"Could not parse source data: {e}")
                            
                            nodes[node_id] = {
                                'id': node_id,
                                'label': f"{props.get('first_name', '')} {props.get('last_name', '')}".strip() or 'Unknown',
                                'type': 'Person',
                                'gender': props.get('gender'),
                                'birth_date': props.get('birth_date'),
                                'death_date': props.get('death_date'),
                                'birth_place': props.get('birth_place'),
                                'occupation': props.get('occupation'),
                                'source': source_name
                            }
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Could not parse person data: {e}")
            
            # Parse related node
            if related_data and str(related_data) != 'null':
                try:
                    related_str = str(related_data)
                    if '::vertex' in related_str:
                        related_str = related_str.split('::')[0].strip()
                    
                    related = json.loads(related_str)
                    if isinstance(related, dict):
                        props = related.get('properties', related)
                        node_id = props.get('uuid')
                        
                        if node_id and node_id not in nodes:
                            # Determine node type and label
                            node_type = 'Person'
                            label = 'Unknown'
                            source_name = None
                            
                            # Parse related source information
                            if related_source_data and str(related_source_data) != 'null':
                                try:
                                    related_source_str = str(related_source_data)
                                    if '::vertex' in related_source_str:
                                        related_source_str = related_source_str.split('::')[0].strip()
                                    related_source = json.loads(related_source_str)
                                    if isinstance(related_source, dict):
                                        related_source_props = related_source.get('properties', related_source)
                                        source_name = related_source_props.get('source_name')
                                except (json.JSONDecodeError, ValueError) as e:
                                    logger.warning(f"Could not parse related source data: {e}")
                            
                            if 'event_type' in props:
                                node_type = 'Event'
                                label = f"{props.get('event_type', 'Event')} - {props.get('date', '')}"
                            elif 'first_name' in props or 'last_name' in props:
                                node_type = 'Person'
                                label = f"{props.get('first_name', '')} {props.get('last_name', '')}".strip() or 'Unknown'
                            elif 'source_name' in props:
                                node_type = 'Source'
                                label = props.get('source_name', 'Unknown Source')
                                source_name = props.get('source_name')
                            
                            nodes[node_id] = {
                                'id': node_id,
                                'label': label,
                                'type': node_type,
                                'gender': props.get('gender'),
                                'birth_date': props.get('birth_date'),
                                'death_date': props.get('death_date'),
                                'event_type': props.get('event_type'),
                                'date': props.get('date'),
                                'place': props.get('place'),
                                'source': source_name
                            }
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Could not parse related data: {e}")
            
            # Parse relationship
            if relationship_data and str(relationship_data) != 'null' and person_data and related_data:
                try:
                    rel_str = str(relationship_data)
                    if '::edge' in rel_str:
                        rel_str = rel_str.split('::')[0].strip()
                    
                    relationship = json.loads(rel_str)
                    if isinstance(relationship, dict):
                        # Re-parse person and related for edge creation
                        person_str = str(person_data)
                        if '::vertex' in person_str:
                            person_str = person_str.split('::')[0].strip()
                        person = json.loads(person_str)
                        
                        related_str = str(related_data)
                        if '::vertex' in related_str:
                            related_str = related_str.split('::')[0].strip()
                        related = json.loads(related_str)
                        
                        person_props = person.get('properties', person)
                        related_props = related.get('properties', related)
                        rel_props = relationship.get('properties', {})
                        
                        from_id = person_props.get('uuid')
                        to_id = related_props.get('uuid')
                        rel_type = relationship.get('label', 'RELATED_TO')
                        
                        if from_id and to_id:
                            edge = {
                                'from': from_id,
                                'to': to_id,
                                'type': rel_type,
                                'label': rel_type.replace('_', ' '),
                                'properties': rel_props
                            }
                            edges.append(edge)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Could not parse relationship data: {e}")
        
        return jsonify({
            'nodes': list(nodes.values()),
            'edges': edges,
            'count': len(nodes)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching graph data: {e}")
        return jsonify({
            'error': f"Failed to fetch graph data: {str(e)}",
            'nodes': [],
            'edges': [],
            'count': 0
        }), 500


@bp.route("/baptisms")
def list_baptisms():
    """Display list of all baptism records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'baptism_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = BaptismRecord.query
        sort_column = get_sort_column(BaptismRecord, sort_by, BaptismRecord.baptism_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template("baptisms.html", baptisms=pagination.items, pagination=pagination)
        
    except Exception as e:
        return render_template("baptisms.html", baptisms=[], error=str(e), pagination=None)


@bp.route("/api/baptisms", methods=["GET"])
def api_list_baptisms():
    """API endpoint to get list of all baptism records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'baptism_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = BaptismRecord.query
        sort_column = get_sort_column(BaptismRecord, sort_by, BaptismRecord.baptism_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        baptisms_data = []
        for baptism in pagination.items:
            baptisms_data.append({
                'id': str(baptism.id),
                'baptism_date': baptism.baptism_date.isoformat() if baptism.baptism_date else None,
                'birth_date': baptism.birth_date.isoformat() if baptism.birth_date else None,
                'child_name': baptism.child_name,
                'child_gender': baptism.child_gender,
                'father_name': f"{baptism.father_name or ''} {baptism.father_surname or ''}".strip(),
                'mother_name': f"{baptism.mother_name or ''} {baptism.mother_maiden_name or ''}".strip(),
                'parish': baptism.parish,
                'village': baptism.village,
                'legitimate': baptism.legitimate,
                'godfather_name': baptism.godfather_name,
                'godmother_name': baptism.godmother_name
            })
        
        return jsonify({
            "data": baptisms_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list baptisms: {str(e)}"}), 500


@bp.route("/marriages")
def list_marriages():
    """Display list of all marriage records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'marriage_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Eagerly load spouse relationships to avoid N+1 queries
        from sqlalchemy.orm import joinedload
        
        # Build query with sorting
        query = MarriageRecord.query.options(
            joinedload(MarriageRecord.spouse1),
            joinedload(MarriageRecord.spouse2)
        )
        
        sort_column = get_sort_column(MarriageRecord, sort_by, MarriageRecord.marriage_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template("marriages.html", marriages=pagination.items, pagination=pagination)
        
    except Exception as e:
        return render_template("marriages.html", marriages=[], error=str(e), pagination=None)


@bp.route("/api/marriages", methods=["GET"])
def api_list_marriages():
    """API endpoint to get list of all marriage records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'marriage_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = MarriageRecord.query
        sort_column = get_sort_column(MarriageRecord, sort_by, MarriageRecord.marriage_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        marriages_data = []
        for marriage in pagination.items:
            marriages_data.append({
                'id': str(marriage.id),
                'marriage_date': marriage.marriage_date.isoformat() if marriage.marriage_date else None,
                'spouse1_name': f"{marriage.spouse1_name or ''} {marriage.spouse1_surname or ''}".strip(),
                'spouse1_status': marriage.spouse1_status,
                'spouse1_age': marriage.spouse1_age,
                'spouse2_name': f"{marriage.spouse2_name or ''} {marriage.spouse2_surname or ''}".strip(),
                'spouse2_maiden_name': marriage.spouse2_maiden_name,
                'spouse2_status': marriage.spouse2_status,
                'spouse2_age': marriage.spouse2_age,
                'parish': marriage.parish,
                'village': marriage.village,
                'banns_count': marriage.banns_count,
                'witnesses': marriage.witnesses
            })
        
        return jsonify({
            "data": marriages_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list marriages: {str(e)}"}), 500


@bp.route("/deaths")
def list_deaths():
    """Display list of all death records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'death_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = DeathRecord.query
        sort_column = get_sort_column(DeathRecord, sort_by, DeathRecord.death_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template("deaths.html", deaths=pagination.items, pagination=pagination)
        
    except Exception as e:
        return render_template("deaths.html", deaths=[], error=str(e), pagination=None)


@bp.route("/api/deaths", methods=["GET"])
def api_list_deaths():
    """API endpoint to get list of all death records."""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        sort_by = request.args.get('sort_by', 'death_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query with sorting
        query = DeathRecord.query
        sort_column = get_sort_column(DeathRecord, sort_by, DeathRecord.death_date)
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        deaths_data = []
        for death in pagination.items:
            deaths_data.append({
                'id': str(death.id),
                'death_date': death.death_date.isoformat() if death.death_date else None,
                'burial_date': death.burial_date.isoformat() if death.burial_date else None,
                'deceased_name': f"{death.deceased_name or ''} {death.deceased_surname or ''}".strip(),
                'deceased_maiden_name': death.deceased_maiden_name,
                'marital_status': death.marital_status,
                'age_years': death.age_years,
                'age_description': death.age_description,
                'parish': death.parish,
                'village': death.village,
                'cemetery': death.cemetery,
                'cause_of_death': death.cause_of_death,
                'sacraments_received': death.sacraments_received,
                'spouse_name': death.spouse_name
            })
        
        return jsonify({
            "data": deaths_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "total_pages": pagination.pages
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list deaths: {str(e)}"}), 500


@bp.route("/duplicates")
def duplicates():
    """View duplicate candidates for review."""
    try:
        # Get filter parameters
        record_type = request.args.get('record_type', 'all')
        status = request.args.get('status', 'pending')
        min_score = request.args.get('min_score', 0.0, type=float)
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        sort_by = request.args.get('sort_by', 'composite_score')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query
        query = DuplicateCandidate.query
        
        # Apply filters
        if record_type != 'all':
            query = query.filter(DuplicateCandidate.record_type == record_type)
        
        if status != 'all':
            query = query.filter(DuplicateCandidate.status == status)
        
        if min_score > 0:
            query = query.filter(DuplicateCandidate.composite_score >= min_score)
        
        # Apply sorting
        sort_column = get_sort_column(DuplicateCandidate, sort_by, DuplicateCandidate.composite_score)
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
        
        # Paginate results
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Enrich candidates with actual record data
        enriched_candidates = []
        for candidate in pagination.items:
            enriched = {
                'id': str(candidate.id),
                'record_type': candidate.record_type,
                'composite_score': candidate.composite_score,
                'vector_similarity': candidate.vector_similarity,
                'phonetic_similarity': candidate.phonetic_similarity,
                'date_similarity': candidate.date_similarity,
                'location_similarity': candidate.location_similarity,
                'status': candidate.status,
                'detected_at': candidate.detected_at,
                'detection_method': candidate.detection_method,
                'reviewed_by': candidate.reviewed_by,
                'reviewed_at': candidate.reviewed_at,
                'review_notes': candidate.review_notes,
                'record1': None,
                'record2': None
            }
            
            # Fetch actual records based on type
            if candidate.record_type == 'person':
                record1 = db.session.get(Person, candidate.record1_id)
                record2 = db.session.get(Person, candidate.record2_id)
                if record1:
                    enriched['record1'] = {
                        'id': str(record1.id),
                        'name': f"{record1.first_name or ''} {record1.last_name or ''}".strip(),
                        'birth_date': record1.birth_date.isoformat() if record1.birth_date else None,
                        'death_date': record1.death_date.isoformat() if record1.death_date else None,
                        'birth_place': record1.birth_place,
                        'death_place': record1.death_place,
                        'gender': record1.gender
                    }
                if record2:
                    enriched['record2'] = {
                        'id': str(record2.id),
                        'name': f"{record2.first_name or ''} {record2.last_name or ''}".strip(),
                        'birth_date': record2.birth_date.isoformat() if record2.birth_date else None,
                        'death_date': record2.death_date.isoformat() if record2.death_date else None,
                        'birth_place': record2.birth_place,
                        'death_place': record2.death_place,
                        'gender': record2.gender
                    }
            
            elif candidate.record_type == 'baptism':
                record1 = db.session.get(BaptismRecord, candidate.record1_id)
                record2 = db.session.get(BaptismRecord, candidate.record2_id)
                if record1:
                    enriched['record1'] = {
                        'id': str(record1.id),
                        'child_name': record1.child_name,
                        'baptism_date': record1.baptism_date.isoformat() if record1.baptism_date else None,
                        'parish': record1.parish,
                        'father_surname': record1.father_surname,
                        'mother_maiden_name': record1.mother_maiden_name
                    }
                if record2:
                    enriched['record2'] = {
                        'id': str(record2.id),
                        'child_name': record2.child_name,
                        'baptism_date': record2.baptism_date.isoformat() if record2.baptism_date else None,
                        'parish': record2.parish,
                        'father_surname': record2.father_surname,
                        'mother_maiden_name': record2.mother_maiden_name
                    }
            
            elif candidate.record_type == 'marriage':
                record1 = db.session.get(MarriageRecord, candidate.record1_id)
                record2 = db.session.get(MarriageRecord, candidate.record2_id)
                if record1:
                    enriched['record1'] = {
                        'id': str(record1.id),
                        'spouse1_name': f"{record1.spouse1_name or ''} {record1.spouse1_surname or ''}".strip(),
                        'spouse2_name': f"{record1.spouse2_name or ''} {record1.spouse2_surname or ''}".strip(),
                        'marriage_date': record1.marriage_date.isoformat() if record1.marriage_date else None,
                        'parish': record1.parish
                    }
                if record2:
                    enriched['record2'] = {
                        'id': str(record2.id),
                        'spouse1_name': f"{record2.spouse1_name or ''} {record2.spouse1_surname or ''}".strip(),
                        'spouse2_name': f"{record2.spouse2_name or ''} {record2.spouse2_surname or ''}".strip(),
                        'marriage_date': record2.marriage_date.isoformat() if record2.marriage_date else None,
                        'parish': record2.parish
                    }
            
            elif candidate.record_type == 'death':
                record1 = db.session.get(DeathRecord, candidate.record1_id)
                record2 = db.session.get(DeathRecord, candidate.record2_id)
                if record1:
                    enriched['record1'] = {
                        'id': str(record1.id),
                        'deceased_name': f"{record1.deceased_name or ''} {record1.deceased_surname or ''}".strip(),
                        'death_date': record1.death_date.isoformat() if record1.death_date else None,
                        'parish': record1.parish,
                        'age_years': record1.age_years
                    }
                if record2:
                    enriched['record2'] = {
                        'id': str(record2.id),
                        'deceased_name': f"{record2.deceased_name or ''} {record2.deceased_surname or ''}".strip(),
                        'death_date': record2.death_date.isoformat() if record2.death_date else None,
                        'parish': record2.parish,
                        'age_years': record2.age_years
                    }
            
            enriched_candidates.append(enriched)
        
        # Get statistics
        stats = {
            'total_pending': DuplicateCandidate.query.filter_by(status='pending').count(),
            'total_confirmed': DuplicateCandidate.query.filter_by(status='confirmed').count(),
            'total_rejected': DuplicateCandidate.query.filter_by(status='rejected').count(),
            'by_type': {
                'person': DuplicateCandidate.query.filter_by(record_type='person', status='pending').count(),
                'baptism': DuplicateCandidate.query.filter_by(record_type='baptism', status='pending').count(),
                'marriage': DuplicateCandidate.query.filter_by(record_type='marriage', status='pending').count(),
                'death': DuplicateCandidate.query.filter_by(record_type='death', status='pending').count()
            }
        }
        
        return render_template(
            "duplicates.html",
            candidates=enriched_candidates,
            pagination=pagination,
            stats=stats,
            filters={
                'record_type': record_type,
                'status': status,
                'min_score': min_score
            }
        )
    except Exception as e:
        logger.error(f"Error loading duplicates page: {e}", exc_info=True)
        db.session.rollback()
        return render_template("duplicates.html", candidates=[], error=str(e), pagination=None, stats={})


@bp.route("/api/duplicates/<candidate_id>/review", methods=["POST"])
def review_duplicate(candidate_id):
    """Review a duplicate candidate (confirm or reject)."""
    try:
        candidate = db.session.get(DuplicateCandidate, candidate_id)
        if not candidate:
            return jsonify({"error": "Duplicate candidate not found"}), 404
        
        data = request.get_json()
        action = data.get('action')  # 'confirm' or 'reject'
        notes = data.get('notes', '')
        reviewer = data.get('reviewer', 'system')
        
        if action not in ['confirm', 'reject']:
            return jsonify({"error": "Invalid action. Must be 'confirm' or 'reject'"}), 400
        
        # Update candidate status
        candidate.status = 'confirmed' if action == 'confirm' else 'rejected'
        candidate.reviewed_by = reviewer
        candidate.reviewed_at = datetime.utcnow()
        candidate.review_notes = notes
        
        # If confirming, delete the duplicate record (record2_id is the duplicate)
        if action == 'confirm':
            # Get the duplicate record based on record type
            duplicate_record = None
            kept_record = None
            record_data = None
            
            if candidate.record_type == 'person':
                duplicate_record = db.session.get(Person, candidate.record2_id)
                kept_record = db.session.get(Person, candidate.record1_id)
            elif candidate.record_type == 'baptism':
                duplicate_record = db.session.get(BaptismRecord, candidate.record2_id)
                kept_record = db.session.get(BaptismRecord, candidate.record1_id)
            elif candidate.record_type == 'marriage':
                duplicate_record = db.session.get(MarriageRecord, candidate.record2_id)
                kept_record = db.session.get(MarriageRecord, candidate.record1_id)
            elif candidate.record_type == 'death':
                duplicate_record = db.session.get(DeathRecord, candidate.record2_id)
                kept_record = db.session.get(DeathRecord, candidate.record1_id)
            
            if duplicate_record:
                # Store record data for audit trail
                if candidate.record_type == 'person':
                    record_data = {
                        'id': str(duplicate_record.id),
                        'first_name': duplicate_record.first_name,
                        'last_name': duplicate_record.last_name,
                        'maiden_name': duplicate_record.maiden_name,
                        'gender': duplicate_record.gender,
                        'birth_date': duplicate_record.birth_date.isoformat() if duplicate_record.birth_date else None,
                        'death_date': duplicate_record.death_date.isoformat() if duplicate_record.death_date else None,
                        'birth_place': duplicate_record.birth_place,
                        'death_place': duplicate_record.death_place,
                        'gedcom_id': duplicate_record.gedcom_id
                    }
                elif candidate.record_type == 'baptism':
                    record_data = {
                        'id': str(duplicate_record.id),
                        'baptism_date': duplicate_record.baptism_date.isoformat() if duplicate_record.baptism_date else None,
                        'birth_date': duplicate_record.birth_date.isoformat() if duplicate_record.birth_date else None,
                        'child_name': duplicate_record.child_name,
                        'father_name': duplicate_record.father_name,
                        'father_surname': duplicate_record.father_surname,
                        'mother_name': duplicate_record.mother_name,
                        'mother_maiden_name': duplicate_record.mother_maiden_name,
                        'parish': duplicate_record.parish,
                        'gedcom_id': duplicate_record.gedcom_id
                    }
                elif candidate.record_type == 'marriage':
                    record_data = {
                        'id': str(duplicate_record.id),
                        'marriage_date': duplicate_record.marriage_date.isoformat() if duplicate_record.marriage_date else None,
                        'spouse1_name': duplicate_record.spouse1_name,
                        'spouse1_surname': duplicate_record.spouse1_surname,
                        'spouse2_name': duplicate_record.spouse2_name,
                        'spouse2_surname': duplicate_record.spouse2_surname,
                        'spouse2_maiden_name': duplicate_record.spouse2_maiden_name,
                        'parish': duplicate_record.parish,
                        'gedcom_id': duplicate_record.gedcom_id
                    }
                elif candidate.record_type == 'death':
                    record_data = {
                        'id': str(duplicate_record.id),
                        'death_date': duplicate_record.death_date.isoformat() if duplicate_record.death_date else None,
                        'deceased_name': duplicate_record.deceased_name,
                        'deceased_surname': duplicate_record.deceased_surname,
                        'deceased_maiden_name': duplicate_record.deceased_maiden_name,
                        'age_years': duplicate_record.age_years,
                        'parish': duplicate_record.parish,
                        'gedcom_id': duplicate_record.gedcom_id
                    }
                
                # Create resolution record for audit trail
                resolution = DuplicateResolution(
                    candidate_id=candidate.id,
                    action='merge',
                    kept_record_id=candidate.record1_id,
                    merged_record_id=candidate.record2_id,
                    resolved_by=reviewer,
                    resolved_at=datetime.utcnow(),
                    resolution_notes=notes,
                    merged_data=record_data
                )
                db.session.add(resolution)
                
                # Delete from graph database first (before PostgreSQL deletion)
                # This ensures consistency between graph and relational storage
                try:
                    raw_conn = db.session.connection().connection
                    graph_importer = AgeGraphImporter(raw_conn)
                    
                    record_uuid = str(duplicate_record.id)
                    graph_deleted = graph_importer.delete_record_from_graph(
                        candidate.record_type,
                        record_uuid
                    )
                    
                    if graph_deleted:
                        logger.info(f"Deleted {candidate.record_type} from graph: {record_uuid}")
                    else:
                        logger.warning(f"Graph deletion returned False for {candidate.record_type}: {record_uuid} (may not exist in graph)")
                except Exception as graph_error:
                    logger.error(f"Error deleting from graph: {graph_error}", exc_info=True)
                    # Continue with PostgreSQL deletion even if graph deletion fails
                    # This prevents blocking duplicate resolution if graph is unavailable
                
                # Delete the duplicate record from PostgreSQL
                # Note: Foreign key relationships should be handled by ON DELETE CASCADE or SET NULL
                db.session.delete(duplicate_record)
                
                logger.info(f"Deleted duplicate {candidate.record_type} record {candidate.record2_id}, kept {candidate.record1_id}")
            else:
                logger.warning(f"Duplicate record not found: {candidate.record_type} {candidate.record2_id}")
        
        db.session.commit()
        
        logger.info(f"Duplicate candidate {candidate_id} {action}ed by {reviewer}")
        
        return jsonify({
            "success": True,
            "message": f"Duplicate {action}ed successfully" + (" and duplicate record deleted" if action == 'confirm' else ""),
            "candidate": {
                "id": str(candidate.id),
                "status": candidate.status,
                "reviewed_by": candidate.reviewed_by,
                "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error reviewing duplicate {candidate_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
