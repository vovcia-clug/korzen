import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import UploadedFile

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
    uploaded_files = get_uploaded_files()
    return render_template("index.html", files=uploaded_files)


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
