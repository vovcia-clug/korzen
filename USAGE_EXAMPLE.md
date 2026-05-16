# GEDCOM Parser Usage Example

## Quick Start Guide

### 1. Start the Application

```bash
# Start the Docker containers
docker-compose up -d

# Or run Flask directly
cd src
flask run
```

### 2. Upload a GEDCOM File

#### Via Web Interface:
1. Open your browser to `http://localhost:5000`
2. Drag and drop your `.ged` file or click to select
3. Click "Upload File"
4. Wait for the success message

#### Via cURL:
```bash
curl -X POST \
  -F "file=@Habsburg.ged" \
  http://localhost:5000/upload
```

**Response:**
```json
{
  "message": "File uploaded successfully",
  "filename": "Habsburg.ged",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 3. Parse the GEDCOM File

#### Via Web Interface:
1. Find your uploaded file in the "Uploaded Files" section
2. Click the green "Parse GEDCOM" button
3. Wait for processing (button shows "Parsing...")
4. View the statistics in the success message

#### Via cURL:
```bash
# Use the file_id from the upload response
curl -X POST \
  http://localhost:5000/parse/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response:**
```json
{
  "message": "GEDCOM file parsed successfully",
  "statistics": {
    "persons": 245,
    "baptisms": 198,
    "marriages": 87,
    "deaths": 156,
    "errors": []
  }
}
```

### 4. View Uploaded Files

#### Via Web Interface:
Files are automatically displayed on the main page with status badges.

#### Via cURL:
```bash
curl http://localhost:5000/files
```

**Response:**
```json
{
  "files": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "filename": "Habsburg.ged",
      "original_filename": "Habsburg.ged",
      "file_size": 524288,
      "uploaded_at": "2026-05-16T16:00:00.000000",
      "processing_status": "completed",
      "batch_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    }
  ]
}
```

## Processing Status

Files go through the following statuses:

1. **uploaded** - File uploaded, ready to parse
2. **processing** - Currently being parsed
3. **completed** - Successfully parsed and imported
4. **failed** - Parsing encountered a fatal error

## Example: Complete Workflow

```bash
# 1. Upload a file
RESPONSE=$(curl -s -X POST -F "file=@test_sample.ged" http://localhost:5000/upload)
echo $RESPONSE

# 2. Extract the file_id
FILE_ID=$(echo $RESPONSE | jq -r '.file_id')
echo "File ID: $FILE_ID"

# 3. Parse the file
curl -X POST http://localhost:5000/parse/$FILE_ID

# 4. Check all files
curl http://localhost:5000/files | jq
```

## Querying the Database

After parsing, you can query the database directly:

```bash
# Connect to the database
docker exec -it db psql -U postgres -d korzen

# View persons
SELECT id, first_name, last_name, birth_date, death_date 
FROM persons 
LIMIT 10;

# View baptism records
SELECT br.baptism_date, p.first_name, p.last_name, br.parish
FROM baptism_records br
JOIN persons p ON br.child_id = p.id
LIMIT 10;

# View marriage records
SELECT mr.marriage_date, 
       p1.first_name || ' ' || p1.last_name as spouse1,
       p2.first_name || ' ' || p2.last_name as spouse2
FROM marriage_records mr
LEFT JOIN persons p1 ON mr.spouse1_id = p1.id
LEFT JOIN persons p2 ON mr.spouse2_id = p2.id
LIMIT 10;

# View record batches
SELECT rb.id, rb.source, rb.ingested_at, 
       COUNT(gr.id) as record_count
FROM record_batches rb
LEFT JOIN genealogical_records gr ON rb.id = gr.batch_id
GROUP BY rb.id, rb.source, rb.ingested_at;
```

## Python API Usage

You can also use the parser programmatically:

```python
from app import create_app, db
from app.gedcom_parser import GedcomParser
from app.models import UploadedFile

# Create Flask app context
app = create_app()

with app.app_context():
    # Create an uploaded file record
    uploaded_file = UploadedFile(
        filename='example.ged',
        original_filename='example.ged',
        filepath='uploads/example.ged',
        file_size=102400,
        processing_status='uploaded'
    )
    db.session.add(uploaded_file)
    db.session.commit()
    
    # Parse the file
    parser = GedcomParser('uploads/example.ged', str(uploaded_file.id))
    stats = parser.parse_and_import()
    
    print(f"Imported {stats['persons']} persons")
    print(f"Imported {stats['baptisms']} baptisms")
    print(f"Imported {stats['marriages']} marriages")
    print(f"Imported {stats['deaths']} deaths")
    
    if stats['errors']:
        print(f"Encountered {len(stats['errors'])} errors:")
        for error in stats['errors']:
            print(f"  - {error}")
```

## Troubleshooting

### File Upload Fails
- Check file extension is `.ged` or `.gedcom`
- Verify file size is within limits
- Check upload directory permissions

### Parsing Fails
- Check GEDCOM file is valid UTF-8
- Review error messages in response
- Check database connection
- View application logs

### No Data Appears
- Verify parsing completed successfully
- Check database tables exist
- Query `genealogical_records` for raw data
- Check `record_batches` for import records

## Sample GEDCOM Files

The repository includes sample files for testing:

- **test_sample.ged** - Minimal test file with 1 person
- **Habsburg.ged** - Larger genealogical dataset

## Next Steps

After importing your GEDCOM data:

1. Query the database to explore your genealogical data
2. Build custom reports and visualizations
3. Export data in different formats
4. Merge multiple GEDCOM files
5. Add additional genealogical records manually
