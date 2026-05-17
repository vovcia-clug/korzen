cimport os
import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text

from ..extensions import db
from ..models import UploadedFile, Person, BaptismRecord, MarriageRecord, DeathRecord
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
    try:
        # Get files from database instead of filesystem
        db_files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
        return render_template("index.html", files=db_files)
    except Exception as e:
        logger.error(f"Error loading index page: {e}")
        db.session.rollback()
        return render_template("index.html", files=[], error=str(e))


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
        # Eagerly load parent relationships to avoid N+1 queries
        from sqlalchemy.orm import joinedload
        
        # Get all persons ordered by last name, first name
        persons = Person.query.options(
            joinedload(Person.father),
            joinedload(Person.mother)
        ).order_by(
            Person.last_name.asc().nullslast(),
            Person.first_name.asc().nullslast()
        ).all()
        
        return render_template("persons.html", persons=persons, now=datetime.now)
        
    except Exception as e:
        return render_template("persons.html", persons=[], error=str(e), now=datetime.now)


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
        
        return jsonify({"persons": persons_data, "count": len(persons_data)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list persons: {str(e)}"}), 500


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
            # Query for descendants: start from root and get connected people
            # We'll get people within depth levels and show family relationships
            query = text(f"""
                SELECT * FROM cypher('genealogy', $$
                    MATCH (root:Person {{uuid: '{root_id}'}})
                    OPTIONAL MATCH path = (root)-[*0..{depth}]-(connected:Person)
                    WITH DISTINCT connected AS p
                    LIMIT {limit}
                    OPTIONAL MATCH (p)-[r]->(related)
                    OPTIONAL MATCH (p)-[fs]->(source:Source)
                    OPTIONAL MATCH (related)-[rfs]->(related_source:Source)
                    RETURN p, r, related, source, related_source
                $$) AS (person agtype, relationship agtype, related agtype, source agtype, related_source agtype);
            """)
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
        # Get all baptisms ordered by baptism date (most recent first)
        baptisms = BaptismRecord.query.order_by(
            BaptismRecord.baptism_date.desc().nullslast()
        ).all()
        
        return render_template("baptisms.html", baptisms=baptisms)
        
    except Exception as e:
        return render_template("baptisms.html", baptisms=[], error=str(e))


@bp.route("/api/baptisms", methods=["GET"])
def api_list_baptisms():
    """API endpoint to get list of all baptism records."""
    try:
        baptisms = BaptismRecord.query.order_by(
            BaptismRecord.baptism_date.desc().nullslast()
        ).all()
        
        baptisms_data = []
        for baptism in baptisms:
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
        
        return jsonify({"baptisms": baptisms_data, "count": len(baptisms_data)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list baptisms: {str(e)}"}), 500


@bp.route("/marriages")
def list_marriages():
    """Display list of all marriage records."""
    try:
        # Get all marriages ordered by marriage date (most recent first)
        # Eagerly load spouse relationships to avoid N+1 queries
        from sqlalchemy.orm import joinedload
        
        marriages = MarriageRecord.query.options(
            joinedload(MarriageRecord.spouse1),
            joinedload(MarriageRecord.spouse2)
        ).order_by(
            MarriageRecord.marriage_date.desc().nullslast()
        ).all()
        
        return render_template("marriages.html", marriages=marriages)
        
    except Exception as e:
        return render_template("marriages.html", marriages=[], error=str(e))


@bp.route("/api/marriages", methods=["GET"])
def api_list_marriages():
    """API endpoint to get list of all marriage records."""
    try:
        marriages = MarriageRecord.query.order_by(
            MarriageRecord.marriage_date.desc().nullslast()
        ).all()
        
        marriages_data = []
        for marriage in marriages:
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
        
        return jsonify({"marriages": marriages_data, "count": len(marriages_data)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list marriages: {str(e)}"}), 500


@bp.route("/deaths")
def list_deaths():
    """Display list of all death records."""
    try:
        # Get all deaths ordered by death date (most recent first)
        deaths = DeathRecord.query.order_by(
            DeathRecord.death_date.desc().nullslast()
        ).all()
        
        return render_template("deaths.html", deaths=deaths)
        
    except Exception as e:
        return render_template("deaths.html", deaths=[], error=str(e))


@bp.route("/api/deaths", methods=["GET"])
def api_list_deaths():
    """API endpoint to get list of all death records."""
    try:
        deaths = DeathRecord.query.order_by(
            DeathRecord.death_date.desc().nullslast()
        ).all()
        
        deaths_data = []
        for death in deaths:
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
        
        return jsonify({"deaths": deaths_data, "count": len(deaths_data)}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to list deaths: {str(e)}"}), 500
