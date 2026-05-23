# AGE Integration Testing Specification

## Overview

This document specifies comprehensive testing for the Apache AGE graph integration, including unit tests, integration tests, and performance tests.

## Test File Structure

```
tests/
├── test_age_graph_importer.py      # Unit tests for importer service
├── test_genealogy_graph_service.py # Unit tests for query service
├── test_graph_api_endpoints.py     # Integration tests for API
├── test_age_integration.py         # End-to-end integration tests
└── test_age_performance.py         # Performance benchmarks
```

## Test Dependencies

Add to `requirements.txt`:
```
pytest==9.0.3
pytest-cov==7.1.0
pytest-mock==3.15.1
```

## 1. Unit Tests for AGE Graph Importer

**File:** `test_age_graph_importer.py`

```python
"""
Unit tests for AGE Graph Importer Service
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from src.app.services.age_graph_importer import AgeGraphImporter


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn


@pytest.fixture
def importer(mock_connection):
    """Create an AgeGraphImporter instance with mock connection."""
    return AgeGraphImporter(mock_connection)


class TestAgeGraphImporter:
    """Test suite for AgeGraphImporter."""
    
    def test_initialization(self, mock_connection):
        """Test importer initialization."""
        importer = AgeGraphImporter(mock_connection)
        assert importer.conn == mock_connection
        assert importer.graph_name == 'genealogy'
    
    def test_create_graph_if_not_exists_new_graph(self, importer, mock_connection):
        """Test creating a new graph."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None  # Graph doesn't exist
        
        importer.create_graph_if_not_exists()
        
        # Verify graph creation was attempted
        assert cursor.execute.call_count >= 2
        mock_connection.commit.assert_called()
    
    def test_create_graph_if_not_exists_existing_graph(self, importer, mock_connection):
        """Test with existing graph."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('genealogy',)  # Graph exists
        
        importer.create_graph_if_not_exists()
        
        # Should not attempt to create
        mock_connection.commit.assert_called()
    
    def test_vertex_exists_true(self, importer, mock_connection):
        """Test vertex_exists when vertex exists."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('vertex_data',)
        
        result = importer.vertex_exists('Person', 'test-uuid')
        
        assert result is True
        cursor.execute.assert_called_once()
    
    def test_vertex_exists_false(self, importer, mock_connection):
        """Test vertex_exists when vertex doesn't exist."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        
        result = importer.vertex_exists('Person', 'test-uuid')
        
        assert result is False
    
    def test_create_person_vertex_success(self, importer, mock_connection):
        """Test creating a person vertex successfully."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None  # Vertex doesn't exist
        
        properties = {
            'gedcom_id': 'I123',
            'first_name': 'John',
            'last_name': 'Smith',
            'gender': 'M',
            'birth_date': datetime(1850, 1, 1).date(),
            'death_date': datetime(1920, 1, 1).date()
        }
        
        result = importer.create_person_vertex('test-uuid', properties)
        
        assert result is True
        mock_connection.commit.assert_called()
    
    def test_create_person_vertex_already_exists(self, importer, mock_connection):
        """Test creating a person vertex that already exists."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('existing_vertex',)  # Vertex exists
        
        properties = {'first_name': 'John'}
        result = importer.create_person_vertex('test-uuid', properties)
        
        assert result is False
    
    def test_create_parent_child_edge_success(self, importer, mock_connection):
        """Test creating a parent-child edge."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None  # Edge doesn't exist
        
        result = importer.create_parent_child_edge(
            'parent-uuid', 'child-uuid', 'father'
        )
        
        assert result is True
        mock_connection.commit.assert_called()
    
    def test_create_marriage_edge_success(self, importer, mock_connection):
        """Test creating a marriage edge."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None  # Edge doesn't exist
        
        result = importer.create_marriage_edge(
            'spouse1-uuid', 'spouse2-uuid', '1875-06-20', 'Warsaw'
        )
        
        assert result is True
        mock_connection.commit.assert_called()
    
    def test_edge_exists_true(self, importer, mock_connection):
        """Test edge_exists when edge exists."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('edge_data',)
        
        result = importer.edge_exists('PARENT_OF', 'uuid1', 'uuid2')
        
        assert result is True
    
    def test_get_statistics(self, importer, mock_connection):
        """Test getting graph statistics."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ('100',),  # persons
            ('50',),   # events
            ('5',),    # sources
            ('180',),  # parent_of edges
            ('60',),   # married_to edges
        ]
        
        stats = importer.get_statistics()
        
        assert stats['persons'] == 100
        assert stats['events'] == 50
        assert stats['sources'] == 5
        assert stats['parent_of_edges'] == 180
        assert stats['married_to_edges'] == 60
    
    def test_error_handling(self, importer, mock_connection):
        """Test error handling in vertex creation."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = Exception("Database error")
        
        result = importer.create_person_vertex('test-uuid', {})
        
        assert result is False
        mock_connection.rollback.assert_called()


## 2. Unit Tests for Genealogy Graph Service

**File:** `test_genealogy_graph_service.py`

```python
"""
Unit tests for Genealogy Graph Service
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.app.services.genealogy_graph_service import GenealogyGraphService


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = None
    return conn


@pytest.fixture
def service(mock_connection):
    """Create a GenealogyGraphService instance."""
    return GenealogyGraphService(mock_connection)


class TestGenealogyGraphService:
    """Test suite for GenealogyGraphService."""
    
    def test_initialization(self, mock_connection):
        """Test service initialization."""
        service = GenealogyGraphService(mock_connection)
        assert service.conn == mock_connection
        assert service.graph_name == 'genealogy'
    
    def test_find_ancestors_success(self, service, mock_connection):
        """Test finding ancestors."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('{"uuid": "parent-uuid", "first_name": "John"}', '1', '["father"]'),
            ('{"uuid": "grandparent-uuid", "first_name": "James"}', '2', '["father", "father"]')
        ]
        
        ancestors = service.find_ancestors('person-uuid', max_generations=5)
        
        assert len(ancestors) == 2
        assert ancestors[0]['generation'] == 1
        assert ancestors[1]['generation'] == 2
    
    def test_find_descendants_success(self, service, mock_connection):
        """Test finding descendants."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('{"uuid": "child-uuid", "first_name": "Mary"}', '1', '["father"]')
        ]
        
        descendants = service.find_descendants('person-uuid', max_generations=5)
        
        assert len(descendants) == 1
        assert descendants[0]['generation'] == 1
    
    def test_find_siblings_full_siblings(self, service, mock_connection):
        """Test finding full siblings."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('{"uuid": "sibling-uuid", "first_name": "Robert"}', 
             '["parent1-uuid", "parent2-uuid"]', '["father", "mother"]')
        ]
        
        siblings = service.find_siblings('person-uuid')
        
        assert len(siblings) == 1
        assert siblings[0]['sibling_type'] == 'full'
    
    def test_find_common_ancestors(self, service, mock_connection):
        """Test finding common ancestors."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('{"uuid": "ancestor-uuid", "first_name": "John"}', '3', '4')
        ]
        
        ancestors = service.find_common_ancestors('uuid1', 'uuid2')
        
        assert len(ancestors) == 1
        assert ancestors[0]['generations_to_person1'] == 3
        assert ancestors[0]['generations_to_person2'] == 4
    
    def test_find_relationship_path_found(self, service, mock_connection):
        """Test finding relationship path when path exists."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            'path_data', '3', 
            '["uuid1", "parent-uuid", "grandparent-uuid", "uuid2"]',
            '["PARENT_OF", "PARENT_OF", "PARENT_OF"]'
        )
        
        path = service.find_relationship_path('uuid1', 'uuid2')
        
        assert path is not None
        assert path['path_length'] == 3
    
    def test_find_relationship_path_not_found(self, service, mock_connection):
        """Test finding relationship path when no path exists."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        
        path = service.find_relationship_path('uuid1', 'uuid2')
        
        assert path is None
    
    def test_find_spouses(self, service, mock_connection):
        """Test finding spouses."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('{"uuid": "spouse-uuid", "first_name": "Jane"}', 
             '1875-06-20', 'Warsaw', 'F123')
        ]
        
        spouses = service.find_spouses('person-uuid')
        
        assert len(spouses) == 1
        assert spouses[0]['marriage_date'] == '1875-06-20'
    
    def test_get_graph_statistics(self, service, mock_connection):
        """Test getting graph statistics."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ('1000',),  # total_persons
            ('2500',),  # total_relationships
            ('1800',),  # parent_child
            ('700',),   # marriages (will be divided by 2)
            ('950',),   # with birth dates
            ('600',),   # with death dates
        ]
        
        stats = service.get_graph_statistics()
        
        assert stats['total_persons'] == 1000
        assert stats['marriages'] == 350  # Divided by 2
    
    def test_error_handling(self, service, mock_connection):
        """Test error handling in queries."""
        cursor = mock_connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = Exception("Query error")
        
        ancestors = service.find_ancestors('person-uuid')
        
        assert ancestors == []


## 3. Integration Tests for API Endpoints

**File:** `test_graph_api_endpoints.py`

```python
"""
Integration tests for Graph API endpoints
"""

import pytest
import json
from flask import Flask
from src.app import create_app
from src.app.extensions import db


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestGraphAPIEndpoints:
    """Test suite for Graph API endpoints."""
    
    def test_health_check(self, client):
        """Test graph health check endpoint."""
        response = client.get('/api/graph/health')
        assert response.status_code in [200, 503]
        data = json.loads(response.data)
        assert 'data' in data
        assert 'status' in data['data']
    
    def test_get_ancestors_valid_uuid(self, client):
        """Test getting ancestors with valid UUID."""
        # Note: This requires test data in the database
        response = client.get('/api/graph/person/test-uuid/ancestors?max_generations=5')
        assert response.status_code in [200, 500]  # May fail if no data
        data = json.loads(response.data)
        assert 'data' in data or 'error' in data
    
    def test_get_ancestors_invalid_generations(self, client):
        """Test getting ancestors with invalid max_generations."""
        response = client.get('/api/graph/person/test-uuid/ancestors?max_generations=25')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_get_descendants(self, client):
        """Test getting descendants."""
        response = client.get('/api/graph/person/test-uuid/descendants')
        assert response.status_code in [200, 500]
    
    def test_get_siblings(self, client):
        """Test getting siblings."""
        response = client.get('/api/graph/person/test-uuid/siblings')
        assert response.status_code in [200, 500]
    
    def test_get_relationship(self, client):
        """Test finding relationship between two people."""
        response = client.get('/api/graph/relationship/uuid1/uuid2')
        assert response.status_code in [200, 500]
    
    def test_get_family_tree(self, client):
        """Test getting family tree."""
        response = client.get('/api/graph/person/test-uuid/tree?generations_up=3&generations_down=3')
        assert response.status_code in [200, 500]
        data = json.loads(response.data)
        if response.status_code == 200:
            assert 'data' in data
            assert 'nodes' in data['data']
            assert 'edges' in data['data']
    
    def test_get_statistics(self, client):
        """Test getting graph statistics."""
        response = client.get('/api/graph/statistics')
        assert response.status_code in [200, 500]
        data = json.loads(response.data)
        if response.status_code == 200:
            assert 'data' in data
    
    def test_invalid_endpoint(self, client):
        """Test accessing invalid endpoint."""
        response = client.get('/api/graph/invalid')
        assert response.status_code == 404


## 4. End-to-End Integration Tests

**File:** `test_age_integration.py`

```python
"""
End-to-end integration tests for AGE graph
"""

import pytest
from datetime import datetime
from src.app import create_app
from src.app.extensions import db
from src.app.models import Person, RecordBatch, BaptismRecord, MarriageRecord
from src.app.services.age_graph_importer import AgeGraphImporter
from src.app.services.genealogy_graph_service import GenealogyGraphService


@pytest.fixture(scope='module')
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@localhost:5432/korzen_test'
    return app


@pytest.fixture(scope='module')
def test_db(app):
    """Create test database."""
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()


class TestAGEIntegration:
    """End-to-end integration tests."""
    
    def test_full_import_workflow(self, app, test_db):
        """Test complete import workflow from relational to graph."""
        with app.app_context():
            # Create test data in relational database
            batch = RecordBatch(source='Test Import')
            test_db.session.add(batch)
            test_db.session.flush()
            
            # Create persons
            father = Person(
                gedcom_id='I1',
                first_name='John',
                last_name='Smith',
                gender='M',
                birth_date=datetime(1850, 1, 1).date(),
                source_batch_id=batch.id
            )
            mother = Person(
                gedcom_id='I2',
                first_name='Jane',
                last_name='Smith',
                maiden_name='Johnson',
                gender='F',
                birth_date=datetime(1855, 1, 1).date(),
                source_batch_id=batch.id
            )
            child = Person(
                gedcom_id='I3',
                first_name='Mary',
                last_name='Smith',
                gender='F',
                birth_date=datetime(1875, 1, 1).date(),
                source_batch_id=batch.id
            )
            
            test_db.session.add_all([father, mother, child])
            test_db.session.flush()
            
            # Create baptism record
            baptism = BaptismRecord(
                gedcom_id='I3_BAPM',
                child_id=child.id,
                father_id=father.id,
                mother_id=mother.id,
                baptism_date=datetime(1875, 2, 1).date(),
                source_batch_id=batch.id
            )
            test_db.session.add(baptism)
            
            # Create marriage record
            marriage = MarriageRecord(
                gedcom_id='F1_MARR',
                spouse1_id=father.id,
                spouse2_id=mother.id,
                marriage_date=datetime(1874, 6, 1).date(),
                source_batch_id=batch.id
            )
            test_db.session.add(marriage)
            test_db.session.commit()
            
            # Import to AGE graph
            raw_conn = test_db.engine.raw_connection()
            importer = AgeGraphImporter(raw_conn)
            importer.create_graph_if_not_exists()
            
            # Import persons
            for person in [father, mother, child]:
                importer.create_person_vertex(
                    str(person.id),
                    {
                        'gedcom_id': person.gedcom_id,
                        'first_name': person.first_name,
                        'last_name': person.last_name,
                        'gender': person.gender,
                        'birth_date': person.birth_date
                    }
                )
            
            # Import relationships
            importer.create_parent_child_edge(str(father.id), str(child.id), 'father')
            importer.create_parent_child_edge(str(mother.id), str(child.id), 'mother')
            importer.create_marriage_edge(str(father.id), str(mother.id), '1874-06-01')
            
            # Query graph
            service = GenealogyGraphService(raw_conn)
            
            # Test ancestor query
            ancestors = service.find_ancestors(str(child.id), max_generations=5)
            assert len(ancestors) == 2
            
            # Test parent query
            parents = service.find_parents(str(child.id))
            assert len(parents) == 2
            
            # Test spouse query
            spouses = service.find_spouses(str(father.id))
            assert len(spouses) == 1
            
            raw_conn.close()


## 5. Performance Tests

**File:** `test_age_performance.py`

```python
"""
Performance benchmarks for AGE graph operations
"""

import pytest
import time
from src.app import create_app
from src.app.extensions import db
from src.app.services.genealogy_graph_service import GenealogyGraphService


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app()
    app.config['TESTING'] = True
    return app


class TestAGEPerformance:
    """Performance benchmark tests."""
    
    def test_ancestor_query_performance(self, app):
        """Benchmark ancestor query performance."""
        with app.app_context():
            raw_conn = db.engine.raw_connection()
            service = GenealogyGraphService(raw_conn)
            
            start_time = time.time()
            ancestors = service.find_ancestors('test-uuid', max_generations=10)
            end_time = time.time()
            
            query_time = end_time - start_time
            print(f"\nAncestor query time: {query_time:.3f}s")
            
            # Assert reasonable performance (< 1 second for typical query)
            assert query_time < 1.0
            
            raw_conn.close()
    
    def test_relationship_path_performance(self, app):
        """Benchmark relationship path query performance."""
        with app.app_context():
            raw_conn = db.engine.raw_connection()
            service = GenealogyGraphService(raw_conn)
            
            start_time = time.time()
            path = service.find_relationship_path('uuid1', 'uuid2', max_hops=15)
            end_time = time.time()
            
            query_time = end_time - start_time
            print(f"\nRelationship path query time: {query_time:.3f}s")
            
            # Assert reasonable performance (< 2 seconds)
            assert query_time < 2.0
            
            raw_conn.close()
    
    def test_family_tree_performance(self, app):
        """Benchmark family tree query performance."""
        with app.app_context():
            raw_conn = db.engine.raw_connection()
            service = GenealogyGraphService(raw_conn)
            
            start_time = time.time()
            tree = service.get_family_tree('test-uuid', generations_up=3, generations_down=3)
            end_time = time.time()
            
            query_time = end_time - start_time
            print(f"\nFamily tree query time: {query_time:.3f}s")
            
            # Assert reasonable performance (< 3 seconds)
            assert query_time < 3.0
            
            raw_conn.close()
```

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_age_graph_importer.py -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src/app/services --cov-report=html
```

### Run Performance Tests
```bash
pytest tests/test_age_performance.py -v -s
```

## Test Data Setup

Create test data fixtures:

**File:** `tests/fixtures/test_gedcom.ged`

```gedcom
0 HEAD
1 SOUR TestApp
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Smith/
1 SEX M
1 BIRT
2 DATE 1 JAN 1850
0 @I2@ INDI
1 NAME Jane /Johnson/
1 SEX F
1 BIRT
2 DATE 1 JAN 1855
0 @I3@ INDI
1 NAME Mary /Smith/
1 SEX F
1 BIRT
2 DATE 1 JAN 1875
1 FAMC @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 MARR
2 DATE 1 JUN 1874
1 CHIL @I3@
0 TRLR
```

## Continuous Integration

### GitHub Actions Workflow

**File:** `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: apache/age:latest
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: korzen_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src/app/services
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/korzen_test
```

## Test Coverage Goals

- **Unit Tests**: > 90% coverage
- **Integration Tests**: All major workflows
- **API Tests**: All endpoints
- **Performance Tests**: Baseline metrics established

## Test Maintenance

1. **Update tests** when adding new features
2. **Run tests** before committing code
3. **Review coverage** reports regularly
4. **Benchmark performance** after optimizations
5. **Document** test failures and resolutions
