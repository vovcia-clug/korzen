# Vector Duplicate Detection Plan - Part 2

## Migration Strategy (continued)

### Phase 2: Backfill Existing Records

Create a management command to generate embeddings for existing records:

**File**: `src/app/cli/backfill_embeddings.py`

```python
import click
from flask.cli import with_appcontext
from ..models import Person, BaptismRecord, MarriageRecord, DeathRecord
from ..services.phonetic_encoder import PhoneticEncoder
from ..services.feature_extractor import FeatureExtractor
from ..services.embedding_generator import EmbeddingGenerator
from ..extensions import db

@click.command('backfill-embeddings')
@click.option('--record-type', default='all', help='Record type: person, baptism, marriage, death, or all')
@click.option('--batch-size', default=100, help='Batch size for processing')
@with_appcontext
def backfill_embeddings(record_type, batch_size):
    """Generate embeddings for existing records."""
    
    phonetic_encoder = PhoneticEncoder()
    feature_extractor = FeatureExtractor()
    embedding_generator = EmbeddingGenerator()
    
    if record_type in ['person', 'all']:
        click.echo('Processing persons...')
        process_persons(phonetic_encoder, feature_extractor, embedding_generator, batch_size)
    
    if record_type in ['baptism', 'all']:
        click.echo('Processing baptism records...')
        process_baptisms(feature_extractor, embedding_generator, batch_size)
    
    # Similar for marriage and death records
    
    click.echo('Backfill complete!')

def process_persons(encoder, extractor, generator, batch_size):
    """Process person records in batches."""
    total = Person.query.count()
    processed = 0
    
    for offset in range(0, total, batch_size):
        persons = Person.query.offset(offset).limit(batch_size).all()
        
        for person in persons:
            # Generate phonetic codes
            codes = encoder.encode_person(person)
            person.first_name_dm = codes.get('first_name_dm', [None])[0]
            person.last_name_dm = codes.get('last_name_dm', [None])[0]
            person.maiden_name_dm = codes.get('maiden_name_dm', [None])[0]
            
            # Generate embedding
            features = extractor.extract_person_features(person)
            embedding = generator.generate_person_embedding(features)
            person.embedding = embedding.tolist()
            
            processed += 1
            if processed % 100 == 0:
                click.echo(f'Processed {processed}/{total} persons')
        
        db.session.commit()
```

### Phase 3: Initial Duplicate Detection

Run batch duplicate detection after backfill:

```bash
# Backfill embeddings
flask backfill-embeddings --record-type=all

# Run duplicate detection
curl -X POST http://localhost:5000/api/duplicates/batch-detect \
  -H "Content-Type: application/json" \
  -d '{"record_type": "person"}'
```

---

## Testing Approach

### 1. Unit Tests

**Test Files Structure**:
```
tests/
├── test_phonetic_encoder.py
├── test_feature_extractor.py
├── test_embedding_generator.py
├── test_similarity_search.py
├── test_duplicate_detector.py
└── test_duplicate_resolver.py
```

**Example Test**: `tests/test_phonetic_encoder.py`

```python
import pytest
from src.app.services.phonetic_encoder import PhoneticEncoder
from src.app.models import Person

class TestPhoneticEncoder:
    def setup_method(self):
        self.encoder = PhoneticEncoder()
    
    def test_encode_slavic_name(self):
        """Test Daitch-Mokotoff encoding for Slavic names."""
        codes = self.encoder.encode_name("Kowalski")
        assert len(codes) > 0
        assert all(isinstance(code, str) for code in codes)
    
    def test_encode_person(self):
        """Test encoding all names for a person."""
        person = Person(
            first_name="Jan",
            last_name="Kowalski",
            maiden_name="Nowak"
        )
        codes = self.encoder.encode_person(person)
        
        assert 'first_name_dm' in codes
        assert 'last_name_dm' in codes
        assert 'maiden_name_dm' in codes
    
    def test_compare_similar_names(self):
        """Test comparison of phonetically similar names."""
        codes1 = self.encoder.encode_name("Jan")
        codes2 = self.encoder.encode_name("Johann")
        
        similarity = self.encoder.compare_codes(codes1, codes2)
        assert similarity > 0.7  # Should be similar
    
    def test_handle_empty_name(self):
        """Test handling of empty/None names."""
        codes = self.encoder.encode_name(None)
        assert codes == []
        
        codes = self.encoder.encode_name("")
        assert codes == []
```

### 2. Integration Tests

**Test File**: `tests/integration/test_duplicate_detection_pipeline.py`

```python
import pytest
from src.app import create_app
from src.app.extensions import db
from src.app.models import Person, DuplicateCandidate
from src.app.services.duplicate_detector import DuplicateDetectorService

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

class TestDuplicateDetectionPipeline:
    def test_detect_exact_duplicate(self, app):
        """Test detection of exact duplicate persons."""
        with app.app_context():
            # Create two identical persons
            person1 = Person(
                first_name="Jan",
                last_name="Kowalski",
                birth_date=date(1900, 1, 1),
                birth_place="Kraków"
            )
            person2 = Person(
                first_name="Jan",
                last_name="Kowalski",
                birth_date=date(1900, 1, 1),
                birth_place="Kraków"
            )
            
            db.session.add_all([person1, person2])
            db.session.commit()
            
            # Run duplicate detection
            detector = DuplicateDetectorService(...)
            candidates = detector.detect_person_duplicates(person2)
            
            assert len(candidates) > 0
            assert candidates[0].overall_similarity > 0.95
    
    def test_detect_phonetic_duplicate(self, app):
        """Test detection of phonetically similar names."""
        with app.app_context():
            person1 = Person(
                first_name="Jan",
                last_name="Kowalski",
                birth_date=date(1900, 1, 1)
            )
            person2 = Person(
                first_name="Johann",
                last_name="Kowalsky",
                birth_date=date(1900, 1, 2)
            )
            
            db.session.add_all([person1, person2])
            db.session.commit()
            
            detector = DuplicateDetectorService(...)
            candidates = detector.detect_person_duplicates(person2)
            
            assert len(candidates) > 0
            assert candidates[0].phonetic_similarity > 0.8
```

### 3. Performance Tests

**Test File**: `tests/performance/test_vector_search_performance.py`

```python
import pytest
import time
from src.app.services.similarity_search import SimilaritySearchService

class TestVectorSearchPerformance:
    def test_search_performance_1000_records(self, app, sample_persons):
        """Test vector search performance with 1000 records."""
        with app.app_context():
            search_service = SimilaritySearchService()
            
            start_time = time.time()
            results = search_service.find_similar_persons(
                sample_persons[0],
                limit=10
            )
            elapsed = time.time() - start_time
            
            assert elapsed < 0.5  # Should complete in < 500ms
            assert len(results) <= 10
    
    def test_batch_processing_performance(self, app):
        """Test batch duplicate detection performance."""
        with app.app_context():
            detector = DuplicateDetectorService(...)
            
            start_time = time.time()
            stats = detector.batch_detect_duplicates(
                record_type='person',
                batch_size=100
            )
            elapsed = time.time() - start_time
            
            # Should process at least 10 records per second
            assert stats['processed'] / elapsed > 10
```

### 4. Test Data

Create test fixtures with known duplicates:

**File**: `tests/fixtures/duplicate_test_data.py`

```python
from datetime import date

DUPLICATE_PERSON_PAIRS = [
    # Exact match
    {
        'person1': {
            'first_name': 'Jan',
            'last_name': 'Kowalski',
            'birth_date': date(1900, 1, 1),
            'birth_place': 'Kraków'
        },
        'person2': {
            'first_name': 'Jan',
            'last_name': 'Kowalski',
            'birth_date': date(1900, 1, 1),
            'birth_place': 'Kraków'
        },
        'expected_similarity': 0.99
    },
    # Phonetic match
    {
        'person1': {
            'first_name': 'Jan',
            'last_name': 'Kowalski',
            'birth_date': date(1900, 1, 1)
        },
        'person2': {
            'first_name': 'Johann',
            'last_name': 'Kowalsky',
            'birth_date': date(1900, 1, 2)
        },
        'expected_similarity': 0.85
    },
    # Date variation
    {
        'person1': {
            'first_name': 'Maria',
            'last_name': 'Nowak',
            'birth_date': date(1905, 6, 15)
        },
        'person2': {
            'first_name': 'Maria',
            'last_name': 'Nowak',
            'birth_date': date(1905, 6, 16)  # Off by one day
        },
        'expected_similarity': 0.95
    }
]
```

---

## Performance Considerations

### 1. Vector Index Optimization

**HNSW Index Parameters**:
```sql
-- Optimize HNSW index for search speed vs accuracy tradeoff
CREATE INDEX idx_person_embedding ON persons 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- m: Number of connections per layer (default 16)
-- ef_construction: Size of dynamic candidate list (default 64)
-- Higher values = better accuracy, slower build time
```

**Query Optimization**:
```python
# Use ef_search parameter for query-time accuracy control
def _stage1_vector_search(self, embedding, table, limit=50):
    """Stage 1: Fast vector similarity search."""
    query = text(f"""
        SET LOCAL hnsw.ef_search = 100;
        SELECT id, embedding <=> :embedding AS distance
        FROM {table}
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)
    
    result = db.session.execute(
        query,
        {'embedding': embedding.tolist(), 'limit': limit}
    )
    return [row.id for row in result]
```

### 2. Batch Processing Strategy

**Chunked Processing**:
```python
def batch_detect_duplicates(self, record_type, batch_size=100):
    """Process records in chunks to avoid memory issues."""
    total = Person.query.count()
    
    for offset in range(0, total, batch_size):
        # Process batch
        persons = Person.query.offset(offset).limit(batch_size).all()
        
        # Generate embeddings in batch
        features_list = [
            self.feature_extractor.extract_person_features(p)
            for p in persons
        ]
        embeddings = self.embedding_generator.batch_generate(features_list)
        
        # Update records
        for person, embedding in zip(persons, embeddings):
            person.embedding = embedding.tolist()
        
        db.session.commit()
        
        # Clear session to free memory
        db.session.expire_all()
```

### 3. Caching Strategy

**Phonetic Code Caching**:
```python
from functools import lru_cache

class PhoneticEncoder:
    @lru_cache(maxsize=10000)
    def encode_name(self, name: str) -> List[str]:
        """Encode name with LRU cache for performance."""
        if not name:
            return []
        
        # Daitch-Mokotoff encoding
        return jellyfish.dm_soundex(name)
```

### 4. Database Connection Pooling

**Configuration** (`src/app/config.py`):
```python
class Config:
    # ... existing config ...
    
    # Connection pool settings for high-volume operations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_pre_ping': True,
        'pool_recycle': 3600
    }
```

### 5. Performance Benchmarks

**Expected Performance**:
- Vector search (1000 records): < 50ms
- Phonetic encoding: < 1ms per name
- Embedding generation: < 10ms per record
- Full duplicate detection: < 100ms per record
- Batch processing: > 10 records/second

**Monitoring Queries**:
```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE indexname LIKE '%embedding%';

-- Check query performance
EXPLAIN ANALYZE
SELECT id, embedding <=> '[0.1, 0.2, ...]' AS distance
FROM persons
ORDER BY embedding <=> '[0.1, 0.2, ...]'
LIMIT 10;
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goals**: Set up infrastructure and core services

**Tasks**:
- [ ] Install pgvector extension
- [ ] Create database migration for schema changes
- [ ] Add new dependencies to requirements.txt
- [ ] Implement PhoneticEncoder service
- [ ] Implement FeatureExtractor service
- [ ] Write unit tests for core services

**Deliverables**:
- Migration file for database schema
- PhoneticEncoder with Daitch-Mokotoff support
- FeatureExtractor with normalization logic
- Unit test suite (>80% coverage)

**Dependencies**:
```txt
# Add to requirements.txt
pgvector==0.2.5
jellyfish==1.0.3
sentence-transformers==2.5.1
```

### Phase 2: Embedding Generation (Week 3)

**Goals**: Implement embedding generation and storage

**Tasks**:
- [ ] Implement EmbeddingGenerator service
- [ ] Choose/configure embedding model
- [ ] Create backfill CLI command
- [ ] Test embedding generation on sample data
- [ ] Optimize batch processing

**Deliverables**:
- EmbeddingGenerator service
- CLI command for backfilling embeddings
- Performance benchmarks
- Documentation for embedding model

### Phase 3: Similarity Search (Week 4)

**Goals**: Implement multi-stage similarity search

**Tasks**:
- [ ] Implement SimilaritySearchService
- [ ] Implement vector search with pgvector
- [ ] Implement phonetic filtering
- [ ] Implement date/location filtering
- [ ] Tune similarity thresholds
- [ ] Write integration tests

**Deliverables**:
- SimilaritySearchService with 4-stage pipeline
- Configurable threshold system
- Integration test suite
- Performance optimization

### Phase 4: Duplicate Detection (Week 5)

**Goals**: Implement duplicate detection pipeline

**Tasks**:
- [ ] Implement DuplicateDetectorService
- [ ] Create DuplicateCandidate model
- [ ] Integrate with GEDCOM parser
- [ ] Implement batch detection
- [ ] Add progress tracking
- [ ] Test on real data

**Deliverables**:
- DuplicateDetectorService
- GEDCOM parser integration
- Batch processing capability
- Real-world test results

### Phase 5: Resolution & API (Week 6)

**Goals**: Implement duplicate resolution and API endpoints

**Tasks**:
- [ ] Implement DuplicateResolverService
- [ ] Create API endpoints for duplicate management
- [ ] Implement merge logic
- [ ] Add audit trail
- [ ] Create UI mockups (optional)
- [ ] Write API documentation

**Deliverables**:
- DuplicateResolverService
- REST API endpoints
- API documentation
- Resolution workflow

### Phase 6: Testing & Optimization (Week 7-8)

**Goals**: Comprehensive testing and performance tuning

**Tasks**:
- [ ] Run full test suite
- [ ] Performance testing with large datasets
- [ ] Optimize slow queries
- [ ] Tune HNSW index parameters
- [ ] Load testing
- [ ] Security review
- [ ] Documentation review

**Deliverables**:
- Complete test coverage report
- Performance benchmark results
- Optimization recommendations
- Final documentation

---

## API Endpoints

### 1. Duplicate Detection Endpoints

#### POST /api/duplicates/detect
Detect duplicates for a specific record.

**Request**:
```json
{
  "record_type": "person",
  "record_id": "uuid-here",
  "threshold": 0.80
}
```

**Response**:
```json
{
  "candidates": [
    {
      "id": "candidate-uuid",
      "record1_id": "uuid1",
      "record2_id": "uuid2",
      "overall_similarity": 0.92,
      "vector_similarity": 0.95,
      "phonetic_similarity": 0.90,
      "date_similarity": 0.88,
      "location_similarity": 0.95,
      "match_details": {
        "matching_fields": ["first_name", "last_name", "birth_date"],
        "differing_fields": ["birth_place"]
      },
      "status": "pending"
    }
  ],
  "count": 1
}
```

#### POST /api/duplicates/batch-detect
Trigger batch duplicate detection.

**Request**:
```json
{
  "record_type": "person",
  "batch_size": 100,
  "threshold": 0.80
}
```

**Response**:
```json
{
  "status": "processing",
  "job_id": "job-uuid",
  "estimated_records": 1500
}
```

#### GET /api/duplicates/batch-status/:job_id
Check batch detection status.

**Response**:
```json
{
  "job_id": "job-uuid",
  "status": "completed",
  "progress": {
    "processed": 1500,
    "total": 1500,
    "candidates_found": 45
  },
  "started_at": "2026-05-16T10:00:00Z",
  "completed_at": "2026-05-16T10:15:00Z"
}
```

### 2. Candidate Management Endpoints

#### GET /api/duplicates/candidates
List duplicate candidates.

**Query Parameters**:
- `record_type`: Filter by record type
- `status`: Filter by status (pending, confirmed, rejected)
- `min_similarity`: Minimum similarity score
- `limit`: Results per page
- `offset`: Pagination offset

**Response**:
```json
{
  "candidates": [...],
  "total": 45,
  "limit": 20,
  "offset": 0
}
```

#### GET /api/duplicates/candidates/:id
Get detailed information about a candidate.

**Response**:
```json
{
  "id": "candidate-uuid",
  "record_type": "person",
  "record1": {
    "id": "uuid1",
    "first_name": "Jan",
    "last_name": "Kowalski",
    "birth_date": "1900-01-01",
    "birth_place": "Kraków"
  },
  "record2": {
    "id": "uuid2",
    "first_name": "Johann",
    "last_name": "Kowalsky",
    "birth_date": "1900-01-02",
    "birth_place": "Krakow"
  },
  "similarity_scores": {...},
  "match_details": {...},
  "status": "pending"
}
```

### 3. Resolution Endpoints

#### POST /api/duplicates/candidates/:id/merge
Merge two duplicate records.

**Request**:
```json
{
  "canonical_id": "uuid1",
  "duplicate_id": "uuid2",
  "merge_strategy": "keep_all",
  "resolved_by": "user@example.com",
  "notes": "Confirmed duplicate after manual review"
}
```

**Response**:
```json
{
  "status": "merged",
  "canonical_record": {...},
  "resolution_id": "resolution-uuid"
}
```

#### POST /api/duplicates/candidates/:id/reject
Reject a duplicate candidate.

**Request**:
```json
{
  "resolved_by": "user@example.com",
  "notes": "Not a duplicate - different persons"
}
```

**Response**:
```json
{
  "status": "rejected",
  "candidate_id": "candidate-uuid"
}
```

#### POST /api/duplicates/candidates/:id/mark-duplicate
Mark as duplicate without merging.

**Request**:
```json
{
  "canonical_id": "uuid1",
  "resolved_by": "user@example.com"
}
```

**Response**:
```json
{
  "status": "marked_duplicate",
  "canonical_id": "uuid1",
  "duplicate_id": "uuid2"
}
```

### 4. Statistics Endpoints

#### GET /api/duplicates/stats
Get duplicate detection statistics.

**Response**:
```json
{
  "total_candidates": 45,
  "by_status": {
    "pending": 30,
    "confirmed": 10,
    "rejected": 5
  },
  "by_record_type": {
    "person": 35,
    "baptism": 5,
    "marriage": 3,
    "death": 2
  },
  "avg_similarity": 0.87,
  "high_confidence_count": 15
}
```

---

## Configuration

### Application Configuration

**File**: `src/app/config.py`

```python
class Config:
    # ... existing config ...
    
    # Duplicate Detection Settings
    DUPLICATE_DETECTION_ENABLED = os.getenv('DUPLICATE_DETECTION_ENABLED', 'true').lower() == 'true'
    
    # Similarity Thresholds
    VECTOR_SIMILARITY_THRESHOLD = float(os.getenv('VECTOR_SIMILARITY_THRESHOLD', '0.75'))
    PHONETIC_SIMILARITY_THRESHOLD = float(os.getenv('PHONETIC_SIMILARITY_THRESHOLD', '0.80'))
    DATE_THRESHOLD_DAYS = int(os.getenv('DATE_THRESHOLD_DAYS', '365'))
    LOCATION_SIMILARITY_THRESHOLD = float(os.getenv('LOCATION_SIMILARITY_THRESHOLD', '0.70'))
    
    # Overall similarity threshold for creating candidates
    OVERALL_SIMILARITY_THRESHOLD = float(os.getenv('OVERALL_SIMILARITY_THRESHOLD', '0.80'))
    
    # Embedding Model
    EMBEDDING_MODEL_PATH = os.getenv('EMBEDDING_MODEL_PATH', 'sentence-transformers/all-MiniLM-L6-v2')
    EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '128'))
    
    # Batch Processing
    DUPLICATE_DETECTION_BATCH_SIZE = int(os.getenv('DUPLICATE_DETECTION_BATCH_SIZE', '100'))
    
    # Auto-merge threshold (very high confidence)
    AUTO_MERGE_THRESHOLD = float(os.getenv('AUTO_MERGE_THRESHOLD', '0.98'))
```

### Environment Variables

**File**: `.env.example`

```bash
# Duplicate Detection Configuration
DUPLICATE_DETECTION_ENABLED=true

# Similarity Thresholds (0.0 to 1.0)
VECTOR_SIMILARITY_THRESHOLD=0.75
PHONETIC_SIMILARITY_THRESHOLD=0.80
LOCATION_SIMILARITY_THRESHOLD=0.70
OVERALL_SIMILARITY_THRESHOLD=0.80

# Date threshold in days
DATE_THRESHOLD_DAYS=365

# Embedding Model
EMBEDDING_MODEL_PATH=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=128

# Batch Processing
DUPLICATE_DETECTION_BATCH_SIZE=100

# Auto-merge threshold (use with caution)
AUTO_MERGE_THRESHOLD=0.98
```

---

## Monitoring and Observability

### 1. Logging

**Configure structured logging**:

```python
import logging
import json

class DuplicateDetectionLogger:
    """Structured logger for duplicate detection events."""
    
    def __init__(self):
        self.logger = logging.getLogger('duplicate_detection')
    
    def log_detection(self, record_type, record_id, candidates_found, duration_ms):
        """Log duplicate detection event."""
        self.logger.info(json.dumps({
            'event': 'duplicate_detection',
            'record_type': record_type,
            'record_id': str(record_id),
            'candidates_found': candidates_found,
            'duration_ms': duration_ms,
            'timestamp': datetime.utcnow().isoformat()
        }))
    
    def log_resolution(self, candidate_id, action, resolved_by):
        """Log duplicate resolution event."""
        self.logger.info(json.dumps({
            'event': 'duplicate_resolution',
            'candidate_id': str(candidate_id),
            'action': action,
            'resolved_by': resolved_by,
            'timestamp': datetime.utcnow().isoformat()
        }))
```

### 2. Metrics

**Key metrics to track**:

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
duplicate_detections_total = Counter(
    'duplicate_detections_total',
    'Total number of duplicate detections',
    ['record_type']
)

duplicate_resolutions_total = Counter(
    'duplicate_resolutions_total',
    'Total number of duplicate resolutions',
    ['action']
)

# Histograms
detection_duration_seconds = Histogram(
    'detection_duration_seconds',
    'Time spent detecting duplicates',
    ['record_type']
)

similarity_score_distribution = Histogram(
    'similarity_score_distribution',
    'Distribution of similarity scores',
    buckets=[0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0]
)

# Gauges
pending_candidates = Gauge(
    'pending_candidates',
    'Number of pending duplicate candidates',
    ['record_type']
)
```

### 3. Health Checks

**Endpoint**: `GET /api/health/duplicate-detection`

```python
@bp.route('/api/health/duplicate-detection')
def duplicate_detection_health():
    """Health check for duplicate detection system."""
    try:
        # Check pgvector extension
        result = db.session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        has_pgvector = result.fetchone() is not None
        
        # Check if embeddings exist
        result = db.session.execute(text("SELECT COUNT(*) FROM persons WHERE embedding IS NOT NULL"))
        embeddings_count = result.fetchone()[0]
        
        # Check pending candidates
        pending_count = DuplicateCandidate.query.filter_by(status='pending').count()
        
        return jsonify({
            'status': 'healthy',
            'pgvector_enabled': has_pgvector,
            'records_with_embeddings': embeddings_count,
            'pending_candidates': pending_count,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
```

### 4. Dashboard Queries

**SQL queries for monitoring dashboard**:

```sql
-- Duplicate detection summary
SELECT 
    record_type,
    status,
    COUNT(*) as count,
    AVG(overall_similarity) as avg_similarity,
    MAX(overall_similarity) as max_similarity
FROM duplicate_candidates
GROUP BY record_type, status;

-- Recent detections
SELECT 
    dc.id,
    dc.record_type,
    dc.overall_similarity,
    dc.status,
    dc.detected_at
FROM duplicate_candidates dc
ORDER BY dc.detected_at DESC
LIMIT 20;

-- Resolution activity
SELECT 
    dr.action,
    COUNT(*) as count,
    DATE_TRUNC('day', dr.resolved_at) as date
FROM duplicate_resolutions dr
WHERE dr.resolved_at >= NOW() - INTERVAL '30 days'
GROUP BY dr.action, DATE_TRUNC('day', dr.resolved_at)
ORDER BY date DESC;

-- High-confidence candidates needing review
SELECT 
    dc.id,
    dc.record_type,
    dc.record1_id,
    dc.record2_id,
    dc.overall_similarity
FROM duplicate_candidates dc
WHERE dc.status = 'pending'
  AND dc.overall_similarity >= 0.90
ORDER BY dc.overall_similarity DESC;
```

---

## Summary

This implementation plan provides a comprehensive roadmap for building a vector embedding-based duplicate detection system for genealogical records. The system leverages:

1. **Daitch-Mokotoff phonetic encoding** for Slavic name matching
2. **128-dimensional vector embeddings** for semantic similarity
3. **PostgreSQL pgvector** for efficient similarity search
4. **Multi-stage filtering** combining vector, phonetic, date, and location matching
5. **Configurable thresholds** for flexibility
6. **Batch processing** for existing records
7. **REST API** for duplicate management
8. **Comprehensive testing** and monitoring

### Key Benefits

- **Accurate**: Multi-stage filtering reduces false positives
- **Scalable**: pgvector HNSW indexes enable fast search on large datasets
- **Flexible**: Configurable thresholds adapt to different use cases
- **Maintainable**: Clean service layer architecture
- **Observable**: Comprehensive logging and metrics

### Next Steps

1. Review and approve this plan
2. Set up development environment with pgvector
3. Begin Phase 1 implementation (Foundation)
4. Iterate based on testing results
5. Deploy to production with monitoring

### Success Criteria

- Detect >95% of true duplicates
- <5% false positive rate
- <100ms average detection time per record
- >10 records/second batch processing
- Complete API documentation
- >80% test coverage

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-16  
**Author**: Architecture Team  
**Status**: Ready for Review
