import os
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text

from ..extensions import db
from ..models import UploadedFile, Person
from ..gedcom_parser import GedcomParser

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


@bp.route("/")
def index():
    """Main page with upload form."""
    # Get files from database instead of filesystem
    db_files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
    return render_template("index.html", files=db_files)


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
        return jsonify({"error": f"Parsing failed: {str(e)}"}), 500


@bp.route("/files", methods=["GET"])
def list_uploaded_files():
    """Get list of all uploaded files with their processing status."""
    try:
        files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
        
        files_data = []
        for file in files:
            files_data.append({
                'id': str(file.id),
                'filename': file.filename,
                'original_filename': file.original_filename,
                'file_size': file.file_size,
                'uploaded_at': file.uploaded_at.isoformat(),
                'processing_status': file.processing_status,
                'batch_id': str(file.batch_id) if file.batch_id else None
            })
        
        return jsonify({"files": files_data}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list files: {str(e)}"}), 500


@bp.route("/persons")
def list_persons():
    """Display list of all persons in the database."""
    try:
        # Get all persons ordered by last name, first name
        persons = Person.query.order_by(
            Person.last_name.asc().nullslast(),
            Person.first_name.asc().nullslast()
        ).all()
        
        return render_template("persons.html", persons=persons)
        
    except Exception as e:
        return render_template("persons.html", persons=[], error=str(e))


@bp.route("/api/persons", methods=["GET"])
def api_list_persons():
    """API endpoint to get list of all persons with their details."""
    try:
        persons = Person.query.order_by(
            Person.last_name.asc().nullslast(),
            Person.first_name.asc().nullslast()
        ).all()
        
        persons_data = []
        for person in persons:
            persons_data.append({
                'id': str(person.id),
                'first_name': person.first_name,
                'last_name': person.last_name,
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
        
        return jsonify({"persons": persons_data, "count": len(persons_data)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list persons: {str(e)}"}), 500


@bp.route("/reset-database", methods=["POST"])
def reset_database():
    """Reset the database by deleting all data from all tables and recreating AGE graph."""
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
        
        # Reset AGE graph - drop and recreate
        try:
            # Set search path for AGE
            db.session.execute(text("SET search_path = ag_catalog, '$user', public"))
            
            # Drop the graph if it exists (this removes all vertices and edges)
            db.session.execute(text("SELECT drop_graph('genealogy', true)"))
            
            # Recreate the graph
            db.session.execute(text("SELECT create_graph('genealogy')"))
            
            db.session.commit()
            
            return jsonify({
                "message": "Database and AGE graph reset successfully. All data has been deleted."
            }), 200
            
        except Exception as age_error:
            # If AGE operations fail, still report success for relational tables
            # but include warning about graph
            db.session.rollback()
            db.session.commit()  # Commit the table truncations
            
            return jsonify({
                "message": "Database reset successfully. All relational data has been deleted.",
                "warning": f"AGE graph reset failed: {str(age_error)}"
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
    API endpoint to fetch graph data for visualization.
    Returns nodes and edges in a format suitable for visualization libraries.
    """
    try:
        # Get optional limit parameter (default to 100 nodes)
        limit = request.args.get('limit', 100, type=int)
        
        # Set search path for AGE
        db.session.execute(text("SET search_path = ag_catalog, '$user', public;"))
        
        # Execute Cypher query to get persons and relationships
        # Note: AGE doesn't support | for multiple relationship types, so we query separately
        query = text(f"""
            SELECT * FROM cypher('genealogy', $$
                MATCH (p:Person)
                WITH p LIMIT {limit}
                OPTIONAL MATCH (p)-[r]->(related)
                RETURN p, r, related
            $$) AS (person agtype, relationship agtype, related agtype);
        """)
        
        result = db.session.execute(query)
        
        nodes = {}
        edges = []
        
        for row in result:
            person_data = row[0]
            relationship_data = row[1]
            related_data = row[2]
            
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
                            nodes[node_id] = {
                                'id': node_id,
                                'label': f"{props.get('first_name', '')} {props.get('last_name', '')}".strip() or 'Unknown',
                                'type': 'Person',
                                'gender': props.get('gender'),
                                'birth_date': props.get('birth_date'),
                                'death_date': props.get('death_date'),
                                'birth_place': props.get('birth_place'),
                                'occupation': props.get('occupation')
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
                            
                            if 'event_type' in props:
                                node_type = 'Event'
                                label = f"{props.get('event_type', 'Event')} - {props.get('date', '')}"
                            elif 'first_name' in props or 'last_name' in props:
                                node_type = 'Person'
                                label = f"{props.get('first_name', '')} {props.get('last_name', '')}".strip() or 'Unknown'
                            
                            nodes[node_id] = {
                                'id': node_id,
                                'label': label,
                                'type': node_type,
                                'gender': props.get('gender'),
                                'birth_date': props.get('birth_date'),
                                'death_date': props.get('death_date'),
                                'event_type': props.get('event_type'),
                                'date': props.get('date'),
                                'place': props.get('place')
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
