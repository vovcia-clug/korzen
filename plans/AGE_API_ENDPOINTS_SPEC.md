# AGE Graph API Endpoints Specification

## Overview

This document specifies the REST API endpoints for querying genealogical data from the Apache AGE graph database.

## Base URL

```
/api/graph
```

## Authentication

All endpoints should respect the existing authentication mechanism in the application.

## File Structure

```
src/app/routes/
├── main.py          # Existing routes
├── health.py        # Existing health check
└── graph.py         # New graph API routes (this spec)
```

## Implementation

**File:** `src/app/routes/graph.py`

```python
"""
Graph API Routes

REST API endpoints for querying genealogical data from AGE graph.
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any
import logging

from ..extensions import db
from ..services.genealogy_graph_service import GenealogyGraphService

logger = logging.getLogger(__name__)

# Create blueprint
graph_bp = Blueprint('graph', __name__, url_prefix='/api/graph')


def get_graph_service() -> GenealogyGraphService:
    """
    Get a GenealogyGraphService instance with raw connection.
    
    Returns:
        GenealogyGraphService instance
    """
    raw_conn = db.engine.raw_connection()
    return GenealogyGraphService(raw_conn)


def format_response(data: Any, meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Format API response in consistent structure.
    
    Args:
        data: Response data
        meta: Optional metadata
        
    Returns:
        Formatted response dictionary
    """
    response = {'data': data}
    if meta:
        response['meta'] = meta
    return response


def format_error(message: str, status_code: int = 400) -> tuple:
    """
    Format error response.
    
    Args:
        message: Error message
        status_code: HTTP status code
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    return jsonify({
        'error': {
            'message': message,
            'status_code': status_code
        }
    }), status_code


@graph_bp.route('/person/<uuid>/ancestors', methods=['GET'])
def get_ancestors(uuid: str):
    """
    Get all ancestors of a person.
    
    Query Parameters:
        - max_generations (int): Maximum generations to traverse (default: 10)
        - include_details (bool): Include full person details (default: true)
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/ancestors?max_generations=5
    
    Response:
        {
            "data": [
                {
                    "uuid": "parent-uuid",
                    "first_name": "John",
                    "last_name": "Smith",
                    "generation": 1,
                    "relationship_chain": ["father"]
                },
                ...
            ],
            "meta": {
                "count": 10,
                "max_generations": 5
            }
        }
    """
    try:
        # Parse query parameters
        max_generations = request.args.get('max_generations', 10, type=int)
        include_details = request.args.get('include_details', 'true').lower() == 'true'
        
        # Validate parameters
        if max_generations < 1 or max_generations > 20:
            return format_error('max_generations must be between 1 and 20', 400)
        
        # Query graph
        service = get_graph_service()
        ancestors = service.find_ancestors(uuid, max_generations, include_details)
        
        return jsonify(format_response(
            ancestors,
            {
                'count': len(ancestors),
                'max_generations': max_generations,
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting ancestors for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/descendants', methods=['GET'])
def get_descendants(uuid: str):
    """
    Get all descendants of a person.
    
    Query Parameters:
        - max_generations (int): Maximum generations to traverse (default: 10)
        - include_details (bool): Include full person details (default: true)
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/descendants?max_generations=5
    
    Response:
        {
            "data": [
                {
                    "uuid": "child-uuid",
                    "first_name": "Mary",
                    "last_name": "Smith",
                    "generation": 1,
                    "relationship_chain": ["father"]
                },
                ...
            ],
            "meta": {
                "count": 15,
                "max_generations": 5
            }
        }
    """
    try:
        max_generations = request.args.get('max_generations', 10, type=int)
        include_details = request.args.get('include_details', 'true').lower() == 'true'
        
        if max_generations < 1 or max_generations > 20:
            return format_error('max_generations must be between 1 and 20', 400)
        
        service = get_graph_service()
        descendants = service.find_descendants(uuid, max_generations, include_details)
        
        return jsonify(format_response(
            descendants,
            {
                'count': len(descendants),
                'max_generations': max_generations,
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting descendants for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/siblings', methods=['GET'])
def get_siblings(uuid: str):
    """
    Get all siblings of a person.
    
    Query Parameters:
        - include_half_siblings (bool): Include half-siblings (default: true)
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/siblings
    
    Response:
        {
            "data": [
                {
                    "uuid": "sibling-uuid",
                    "first_name": "Robert",
                    "last_name": "Smith",
                    "sibling_type": "full",
                    "shared_parent_count": 2
                },
                ...
            ],
            "meta": {
                "count": 3,
                "full_siblings": 2,
                "half_siblings": 1
            }
        }
    """
    try:
        include_half_siblings = request.args.get('include_half_siblings', 'true').lower() == 'true'
        
        service = get_graph_service()
        siblings = service.find_siblings(uuid, include_half_siblings)
        
        # Count sibling types
        full_siblings = sum(1 for s in siblings if s.get('sibling_type') == 'full')
        half_siblings = sum(1 for s in siblings if s.get('sibling_type') == 'half')
        
        return jsonify(format_response(
            siblings,
            {
                'count': len(siblings),
                'full_siblings': full_siblings,
                'half_siblings': half_siblings,
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting siblings for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/parents', methods=['GET'])
def get_parents(uuid: str):
    """
    Get parents of a person.
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/parents
    
    Response:
        {
            "data": [
                {
                    "uuid": "father-uuid",
                    "first_name": "John",
                    "last_name": "Smith",
                    "parent_type": "father"
                },
                {
                    "uuid": "mother-uuid",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "parent_type": "mother"
                }
            ],
            "meta": {
                "count": 2
            }
        }
    """
    try:
        service = get_graph_service()
        parents = service.find_parents(uuid)
        
        return jsonify(format_response(
            parents,
            {
                'count': len(parents),
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting parents for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/children', methods=['GET'])
def get_children(uuid: str):
    """
    Get all children of a person.
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/children
    
    Response:
        {
            "data": [
                {
                    "uuid": "child-uuid",
                    "first_name": "Mary",
                    "last_name": "Smith",
                    "birth_date": "1875-06-20",
                    "parent_type": "father"
                },
                ...
            ],
            "meta": {
                "count": 5
            }
        }
    """
    try:
        service = get_graph_service()
        children = service.find_children(uuid)
        
        return jsonify(format_response(
            children,
            {
                'count': len(children),
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting children for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/spouses', methods=['GET'])
def get_spouses(uuid: str):
    """
    Get all spouses of a person.
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/spouses
    
    Response:
        {
            "data": [
                {
                    "uuid": "spouse-uuid",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "marriage_date": "1870-05-10",
                    "marriage_place": "Warsaw Cathedral"
                },
                ...
            ],
            "meta": {
                "count": 1
            }
        }
    """
    try:
        service = get_graph_service()
        spouses = service.find_spouses(uuid)
        
        return jsonify(format_response(
            spouses,
            {
                'count': len(spouses),
                'person_uuid': uuid
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting spouses for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/relationship/<uuid1>/<uuid2>', methods=['GET'])
def get_relationship(uuid1: str, uuid2: str):
    """
    Find the relationship path between two people.
    
    Query Parameters:
        - max_hops (int): Maximum path length to search (default: 15)
    
    Example:
        GET /api/graph/relationship/uuid1/uuid2?max_hops=10
    
    Response:
        {
            "data": {
                "path_length": 3,
                "node_uuids": ["uuid1", "parent-uuid", "grandparent-uuid", "uuid2"],
                "relationship_types": ["PARENT_OF", "PARENT_OF", "PARENT_OF"],
                "relationship_description": "3 generations apart"
            },
            "meta": {
                "person1_uuid": "uuid1",
                "person2_uuid": "uuid2"
            }
        }
    """
    try:
        max_hops = request.args.get('max_hops', 15, type=int)
        
        if max_hops < 1 or max_hops > 20:
            return format_error('max_hops must be between 1 and 20', 400)
        
        service = get_graph_service()
        path = service.find_relationship_path(uuid1, uuid2, max_hops)
        
        if path is None:
            return jsonify(format_response(
                None,
                {
                    'message': 'No relationship path found',
                    'person1_uuid': uuid1,
                    'person2_uuid': uuid2
                }
            ))
        
        return jsonify(format_response(
            path,
            {
                'person1_uuid': uuid1,
                'person2_uuid': uuid2
            }
        ))
        
    except Exception as e:
        logger.error(f"Error finding relationship between {uuid1} and {uuid2}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/common-ancestors/<uuid1>/<uuid2>', methods=['GET'])
def get_common_ancestors(uuid1: str, uuid2: str):
    """
    Find common ancestors between two people.
    
    Query Parameters:
        - max_generations (int): Maximum generations to search (default: 10)
    
    Example:
        GET /api/graph/common-ancestors/uuid1/uuid2?max_generations=10
    
    Response:
        {
            "data": [
                {
                    "uuid": "ancestor-uuid",
                    "first_name": "John",
                    "last_name": "Smith",
                    "generations_to_person1": 3,
                    "generations_to_person2": 4,
                    "total_distance": 7
                },
                ...
            ],
            "meta": {
                "count": 2,
                "person1_uuid": "uuid1",
                "person2_uuid": "uuid2"
            }
        }
    """
    try:
        max_generations = request.args.get('max_generations', 10, type=int)
        
        if max_generations < 1 or max_generations > 20:
            return format_error('max_generations must be between 1 and 20', 400)
        
        service = get_graph_service()
        ancestors = service.find_common_ancestors(uuid1, uuid2, max_generations)
        
        return jsonify(format_response(
            ancestors,
            {
                'count': len(ancestors),
                'person1_uuid': uuid1,
                'person2_uuid': uuid2,
                'max_generations': max_generations
            }
        ))
        
    except Exception as e:
        logger.error(f"Error finding common ancestors: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/person/<uuid>/tree', methods=['GET'])
def get_family_tree(uuid: str):
    """
    Get complete family tree for a person (ancestors and descendants).
    
    Query Parameters:
        - generations_up (int): Number of ancestor generations (default: 3)
        - generations_down (int): Number of descendant generations (default: 3)
    
    Example:
        GET /api/graph/person/550e8400-e29b-41d4-a716-446655440000/tree?generations_up=3&generations_down=3
    
    Response:
        {
            "data": {
                "root_person": {...},
                "nodes": [...],
                "edges": [...],
                "statistics": {
                    "total_nodes": 25,
                    "total_edges": 30,
                    "ancestor_count": 10,
                    "descendant_count": 14
                }
            },
            "meta": {
                "person_uuid": "uuid",
                "generations_up": 3,
                "generations_down": 3
            }
        }
    """
    try:
        generations_up = request.args.get('generations_up', 3, type=int)
        generations_down = request.args.get('generations_down', 3, type=int)
        
        if generations_up < 0 or generations_up > 10:
            return format_error('generations_up must be between 0 and 10', 400)
        if generations_down < 0 or generations_down > 10:
            return format_error('generations_down must be between 0 and 10', 400)
        
        service = get_graph_service()
        tree = service.get_family_tree(uuid, generations_up, generations_down)
        
        return jsonify(format_response(
            tree,
            {
                'person_uuid': uuid,
                'generations_up': generations_up,
                'generations_down': generations_down
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting family tree for {uuid}: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Get overall graph statistics.
    
    Example:
        GET /api/graph/statistics
    
    Response:
        {
            "data": {
                "total_persons": 1000,
                "total_relationships": 2500,
                "parent_child_relationships": 1800,
                "marriages": 350,
                "persons_with_birth_dates": 950,
                "persons_with_death_dates": 600
            },
            "meta": {
                "timestamp": "2026-05-16T17:00:00Z"
            }
        }
    """
    try:
        from datetime import datetime
        
        service = get_graph_service()
        stats = service.get_graph_statistics()
        
        return jsonify(format_response(
            stats,
            {
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        ))
        
    except Exception as e:
        logger.error(f"Error getting graph statistics: {e}")
        return format_error(f'Internal server error: {str(e)}', 500)


@graph_bp.route('/health', methods=['GET'])
def health_check():
    """
    Check if graph database is accessible.
    
    Example:
        GET /api/graph/health
    
    Response:
        {
            "data": {
                "status": "healthy",
                "graph_name": "genealogy",
                "connection": "ok"
            }
        }
    """
    try:
        service = get_graph_service()
        stats = service.get_graph_statistics()
        
        return jsonify(format_response({
            'status': 'healthy',
            'graph_name': 'genealogy',
            'connection': 'ok',
            'total_persons': stats.get('total_persons', 0)
        }))
        
    except Exception as e:
        logger.error(f"Graph health check failed: {e}")
        return jsonify(format_response({
            'status': 'unhealthy',
            'graph_name': 'genealogy',
            'connection': 'error',
            'error': str(e)
        })), 503


# Error handlers
@graph_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return format_error('Resource not found', 404)


@graph_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return format_error('Internal server error', 500)
```

## Register Blueprint

**File:** `src/app/__init__.py` (add to existing file)

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register blueprints
    from .routes.main import main_bp
    from .routes.health import health_bp
    from .routes.graph import graph_bp  # Add this
    
    app.register_blueprint(main_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(graph_bp)  # Add this
    
    return app
```

## API Documentation

### Response Format

All successful responses follow this structure:

```json
{
    "data": <response_data>,
    "meta": {
        <metadata_fields>
    }
}
```

All error responses follow this structure:

```json
{
    "error": {
        "message": "Error description",
        "status_code": 400
    }
}
```

### HTTP Status Codes

- `200 OK`: Successful request
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Graph database unavailable

### Rate Limiting

Consider implementing rate limiting for expensive queries:
- Ancestors/descendants: 60 requests/minute
- Relationship paths: 30 requests/minute
- Family tree: 10 requests/minute
- Statistics: 120 requests/minute

### Pagination

For endpoints that may return large result sets, consider adding pagination:

```python
@graph_bp.route('/person/<uuid>/descendants', methods=['GET'])
def get_descendants(uuid: str):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Limit per_page
    per_page = min(per_page, 100)
    
    # Get all descendants
    all_descendants = service.find_descendants(uuid, max_generations)
    
    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_descendants[start:end]
    
    return jsonify(format_response(
        paginated,
        {
            'count': len(paginated),
            'total': len(all_descendants),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(all_descendants) + per_page - 1) // per_page
        }
    ))
```

## CORS Configuration

If the API will be accessed from a frontend on a different domain:

```python
from flask_cors import CORS

def create_app(config_class=Config):
    app = Flask(__name__)
    
    # Enable CORS for graph API
    CORS(app, resources={r"/api/graph/*": {"origins": "*"}})
    
    # ... rest of configuration
```

## API Testing with curl

```bash
# Get ancestors
curl http://localhost:5000/api/graph/person/550e8400-e29b-41d4-a716-446655440000/ancestors?max_generations=5

# Get descendants
curl http://localhost:5000/api/graph/person/550e8400-e29b-41d4-a716-446655440000/descendants

# Get siblings
curl http://localhost:5000/api/graph/person/550e8400-e29b-41d4-a716-446655440000/siblings

# Find relationship
curl http://localhost:5000/api/graph/relationship/uuid1/uuid2

# Get family tree
curl http://localhost:5000/api/graph/person/550e8400-e29b-41d4-a716-446655440000/tree?generations_up=3&generations_down=3

# Get statistics
curl http://localhost:5000/api/graph/statistics

# Health check
curl http://localhost:5000/api/graph/health
```

## Frontend Integration Example

```javascript
// Fetch ancestors
async function getAncestors(personUuid, maxGenerations = 5) {
    const response = await fetch(
        `/api/graph/person/${personUuid}/ancestors?max_generations=${maxGenerations}`
    );
    const result = await response.json();
    return result.data;
}

// Fetch family tree for visualization
async function getFamilyTree(personUuid) {
    const response = await fetch(
        `/api/graph/person/${personUuid}/tree?generations_up=3&generations_down=3`
    );
    const result = await response.json();
    
    // result.data contains nodes and edges for D3.js or similar
    return {
        nodes: result.data.nodes,
        edges: result.data.edges
    };
}

// Find relationship between two people
async function findRelationship(uuid1, uuid2) {
    const response = await fetch(
        `/api/graph/relationship/${uuid1}/${uuid2}`
    );
    const result = await response.json();
    
    if (result.data) {
        console.log(`Relationship: ${result.data.relationship_description}`);
        console.log(`Path length: ${result.data.path_length}`);
    } else {
        console.log('No relationship found');
    }
}
```

## Security Considerations

1. **Input Validation**: All UUIDs should be validated
2. **Parameter Limits**: Enforce reasonable limits on generations/hops
3. **Query Timeouts**: Implement timeouts for long-running queries
4. **Authentication**: Add authentication middleware if needed
5. **Authorization**: Check user permissions for accessing person data
6. **Rate Limiting**: Prevent abuse of expensive queries

## Monitoring

Log the following metrics:
- Request count per endpoint
- Response times
- Error rates
- Query complexity (generations, hops)
- Result set sizes

## Performance Optimization

1. **Caching**: Cache frequently accessed family trees
2. **Connection Pooling**: Reuse database connections
3. **Async Processing**: For very large queries, consider async processing
4. **Result Limits**: Always limit result sets

## Future Enhancements

1. **WebSocket Support**: Real-time updates for collaborative editing
2. **GraphQL API**: Alternative to REST for flexible queries
3. **Batch Operations**: Query multiple persons in one request
4. **Export**: Export family trees in various formats (GEDCOM, JSON, SVG)
5. **Visualization Endpoints**: Pre-rendered family tree images
