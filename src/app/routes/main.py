import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text

from ..extensions import db
from ..models import UploadedFile, Person
from ..gedcom_parser import GedcomParser

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
    """Reset the database by deleting all data from all tables."""
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
        
        return jsonify({
            "message": "Database reset successfully. All data has been deleted."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to reset database: {str(e)}"}), 500
