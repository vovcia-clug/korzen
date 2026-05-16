# GEDCOM Parser Implementation

## Overview

This document describes the implementation of GEDCOM file parsing using the `ged4py` library to extract genealogical data and insert it into the PostgreSQL database.

## Components

### 1. GEDCOM Parser Module (`src/app/gedcom_parser.py`)

The main parser class that handles GEDCOM file parsing and database insertion.

#### Key Features:
- **Person Extraction**: Extracts individuals from GEDCOM INDI records
- **Family Relationships**: Processes FAM records for marriages
- **Event Records**: Creates baptism, marriage, and death records
- **Batch Tracking**: Groups imported data into batches for traceability
- **Error Handling**: Comprehensive error handling with detailed logging

#### Main Methods:

##### `parse_and_import()`
Main entry point that orchestrates the entire import process:
1. Creates a `RecordBatch` to track the import
2. First pass: Creates all `Person` records from INDI records
3. Second pass: Creates `BaptismRecord` and `DeathRecord` entries
4. Third pass: Creates `MarriageRecord` entries from FAM records
5. Updates file processing status

##### `create_person_from_individual(individual: Individual)`
Extracts person data from GEDCOM Individual records:
- Name parsing (first name, last name)
- Gender
- Birth date and place
- Death date and place
- Occupation

##### `create_baptism_record(individual: Individual, person: Person)`
Creates baptism records from GEDCOM baptism events.

##### `create_marriage_record(family: Record)`
Creates marriage records from GEDCOM family records.

##### `create_death_record(individual: Individual, person: Person)`
Creates death records from GEDCOM death events.

##### `parse_date(date_str: str)`
Parses GEDCOM date strings (handles modifiers like ABT, CAL, EST, BEF, AFT).

##### `extract_name_parts(name: str)`
Extracts first and last names from GEDCOM name format: "FirstName /LastName/".

### 2. API Routes (`src/app/routes/main.py`)

#### Endpoints:

##### `POST /upload`
Uploads a GEDCOM file and creates a database record.

**Request**: Multipart form data with file
**Response**:
```json
{
  "message": "File uploaded successfully",
  "filename": "example.ged",
  "file_id": "uuid-here"
}
```

##### `POST /parse/<file_id>`
Parses an uploaded GEDCOM file and imports data into the database.

**Response**:
```json
{
  "message": "GEDCOM file parsed successfully",
  "statistics": {
    "persons": 150,
    "baptisms": 120,
    "marriages": 45,
    "deaths": 80,
    "errors": []
  }
}
```

##### `GET /files`
Lists all uploaded files with their processing status.

**Response**:
```json
{
  "files": [
    {
      "id": "uuid",
      "filename": "example.ged",
      "original_filename": "example.ged",
      "file_size": 102400,
      "uploaded_at": "2026-05-16T16:00:00",
      "processing_status": "completed",
      "batch_id": "batch-uuid"
    }
  ]
}
```

### 3. Web Interface (`src/app/templates/index.html`)

Enhanced UI with:
- Drag-and-drop file upload
- File list with processing status badges
- Parse button for uploaded files
- Real-time status updates
- Statistics display after parsing

#### Status Badges:
- **uploaded**: File uploaded, ready to parse
- **processing**: Currently being parsed
- **completed**: Successfully parsed
- **failed**: Parsing failed

## Database Schema

### Tables Used:

#### `uploaded_files`
Tracks uploaded GEDCOM files:
- `id`: UUID primary key
- `filename`: Secure filename
- `original_filename`: Original upload name
- `filepath`: Path to file on disk
- `file_size`: Size in bytes
- `processing_status`: Current status
- `batch_id`: Link to record batch

#### `record_batches`
Groups imported records:
- `id`: UUID primary key
- `source`: Import source description
- `description`: Additional details
- `ingested_at`: Import timestamp

#### `genealogical_records`
Stores raw GEDCOM data:
- `id`: UUID primary key
- `batch_id`: Link to batch
- `record_type`: INDIVIDUAL or FAMILY
- `raw_payload`: JSONB with original data
- `external_id`: GEDCOM xref_id

#### `persons`
Individual person records:
- `id`: UUID primary key
- `first_name`, `last_name`, `maiden_name`
- `gender`: M, F, or Unknown
- `birth_date`, `birth_place`
- `death_date`, `death_place`
- `occupation`
- Various other fields

#### `baptism_records`
Baptism event records:
- Links to child, father, mother persons
- Baptism and birth dates
- Parish and location information
- Godparent information

#### `marriage_records`
Marriage event records:
- Links to both spouses
- Marriage date and location
- Witness information
- Banns details

#### `death_records`
Death event records:
- Link to deceased person
- Death and burial dates
- Cause of death
- Sacraments received

## Usage

### 1. Upload a GEDCOM File

Via Web Interface:
1. Navigate to the main page
2. Click or drag-and-drop a .ged file
3. Click "Upload File"

Via API:
```bash
curl -X POST -F "file=@example.ged" http://localhost:5000/upload
```

### 2. Parse the GEDCOM File

Via Web Interface:
1. Find the uploaded file in the list
2. Click "Parse GEDCOM" button
3. Wait for processing to complete

Via API:
```bash
curl -X POST http://localhost:5000/parse/<file_id>
```

### 3. View Results

The parser returns statistics showing:
- Number of persons created
- Number of baptism records
- Number of marriage records
- Number of death records
- Any errors encountered

## Data Flow

```
GEDCOM File Upload
    ↓
UploadedFile Record Created (status: uploaded)
    ↓
User Triggers Parse
    ↓
GedcomParser.parse_and_import()
    ↓
RecordBatch Created
    ↓
Pass 1: Create Person records from INDI
    ↓
Pass 2: Create Baptism & Death records
    ↓
Pass 3: Create Marriage records from FAM
    ↓
Update UploadedFile (status: completed)
    ↓
Return Statistics
```

## Error Handling

The parser includes comprehensive error handling:

1. **File-level errors**: Caught and reported, processing stops
2. **Record-level errors**: Logged but processing continues
3. **Status tracking**: File status updated to 'failed' on fatal errors
4. **Error collection**: All errors collected in statistics response

## Supported GEDCOM Features

### Currently Supported:
- ✅ Individual records (INDI)
- ✅ Family records (FAM)
- ✅ Names (NAME)
- ✅ Sex/Gender (SEX)
- ✅ Birth events (BIRT)
- ✅ Death events (DEAT)
- ✅ Baptism events (BAPM/CHR)
- ✅ Marriage events (MARR)
- ✅ Dates (DATE) with modifiers
- ✅ Places (PLAC)
- ✅ Occupation (OCCU)

### Future Enhancements:
- ⏳ Burial events (BURI)
- ⏳ Residence (RESI)
- ⏳ Notes (NOTE)
- ⏳ Sources (SOUR)
- ⏳ Media objects (OBJE)
- ⏳ Parent-child relationships
- ⏳ Godparent relationships
- ⏳ Witness relationships

## Testing

A test script is provided: `test_gedcom_parser.py`

Run tests:
```bash
source /home/user/GitHub/venv/bin/activate
python test_gedcom_parser.py
```

## Dependencies

- **ged4py**: GEDCOM file parsing library
- **Flask**: Web framework
- **SQLAlchemy**: ORM for database operations
- **PostgreSQL**: Database backend

## Configuration

The parser uses the following configuration from Flask app:
- `UPLOAD_FOLDER`: Directory for uploaded files
- Database connection via SQLAlchemy

## Logging

The parser uses Python's logging module:
```python
import logging
logger = logging.getLogger(__name__)
```

Logs include:
- Info: Progress updates
- Warning: Non-fatal issues (e.g., unparseable dates)
- Error: Record-level errors
- Critical: Fatal errors

## Performance Considerations

1. **Multiple passes**: The parser makes 3 passes through the GEDCOM file to handle relationships correctly
2. **Batch commits**: Database commits are done in batches for efficiency
3. **Memory usage**: Large GEDCOM files are processed iteratively
4. **Person mapping**: In-memory dictionary maps GEDCOM IDs to database UUIDs

## Security

- Filenames are sanitized using `secure_filename()`
- File extensions are validated (.ged, .gedcom only)
- File size limits enforced by Flask configuration
- SQL injection prevented by SQLAlchemy ORM
- UUID-based file IDs prevent enumeration attacks

## Future Improvements

1. **Async Processing**: Move parsing to background task queue (Celery)
2. **Progress Updates**: WebSocket for real-time progress
3. **Duplicate Detection**: Check for existing persons before creating
4. **Relationship Linking**: Link parent-child relationships
5. **Data Validation**: More robust date and place validation
6. **Export**: Export data back to GEDCOM format
7. **Merge**: Merge multiple GEDCOM files
8. **Search**: Full-text search across genealogical data
