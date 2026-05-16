# Graph Visualizer for Korzen

## Overview

The Graph Visualizer provides an interactive, visual representation of the genealogy graph stored in Apache AGE. It allows users to explore family relationships, events, and connections in an intuitive graphical interface.

## Features

### Interactive Visualization
- **Node-based Graph**: Persons and events are displayed as nodes with different colors and shapes
- **Relationship Edges**: Connections between nodes show different types of relationships
- **Interactive Navigation**: Pan, zoom, and click on nodes to explore the graph
- **Physics Simulation**: Automatic layout using force-directed graph algorithms

### Visual Encoding

#### Node Colors
- **Blue** (`#64b5f6`): Male persons
- **Pink** (`#f48fb1`): Female persons
- **Gray** (`#bdbdbd`): Unknown gender
- **Yellow** (`#fff59d`): Events (baptisms, deaths, etc.)

#### Node Shapes
- **Circle**: Person nodes
- **Diamond**: Event nodes

#### Edge Colors & Styles
- **Green** (`#4caf50`, solid, width 2): Parent-child relationships (PARENT_OF)
- **Pink** (`#e91e63`, solid, width 2): Marriage relationships (MARRIED_TO)
- **Purple** (`#9c27b0`, dashed): Godparent relationships (GODPARENT_OF)
- **Orange** (`#ff9800`, dashed): Event relationships (BAPTIZED_IN, DIED_IN)
- **Gray** (`#999`, solid, width 1): Other relationships

### User Interface

#### Controls
- **Node Limit**: Adjust the number of nodes to load (10-1000)
- **Load Graph**: Fetch and display graph data
- **Reset View**: Reset zoom and pan to fit all nodes
- **Statistics**: Display node and edge counts

#### Information Panel
- Click on any node to view detailed information
- Shows person details (name, dates, places, occupation)
- Shows event details (type, date, place)
- Close button to hide the panel

#### Legend
- Visual guide to node colors and their meanings
- Located in bottom-left corner

## Technical Implementation

### Backend API

#### Route: `/graph`
- **Method**: GET
- **Description**: Renders the graph visualizer HTML page
- **Template**: `graph.html`

#### Route: `/api/graph/data`
- **Method**: GET
- **Parameters**: 
  - `limit` (optional, default: 100): Maximum number of nodes to return
- **Response**: JSON object with nodes and edges
  ```json
  {
    "nodes": [
      {
        "id": "uuid",
        "label": "John Smith",
        "type": "Person",
        "gender": "M",
        "birth_date": "1850-01-15",
        "death_date": "1920-05-20",
        "birth_place": "Warsaw",
        "occupation": "Farmer"
      }
    ],
    "edges": [
      {
        "from": "parent-uuid",
        "to": "child-uuid",
        "type": "PARENT_OF",
        "label": "PARENT OF",
        "properties": {"type": "father"}
      }
    ],
    "count": 100
  }
  ```

### Frontend Technology

#### Vis.js Network
- **Library**: [Vis.js Network](https://visjs.github.io/vis-network/)
- **Version**: Latest (loaded via CDN)
- **Purpose**: Interactive graph visualization with physics simulation

#### Graph Configuration
```javascript
{
  physics: {
    enabled: true,
    barnesHut: {
      gravitationalConstant: -2000,
      centralGravity: 0.3,
      springLength: 150,
      springConstant: 0.04,
      damping: 0.09,
      avoidOverlap: 0.1
    },
    stabilization: {
      iterations: 200
    }
  },
  interaction: {
    hover: true,
    tooltipDelay: 200,
    navigationButtons: true,
    keyboard: true
  }
}
```

### Data Flow

1. **User Action**: User clicks "Load Graph" button
2. **API Request**: Frontend sends GET request to `/api/graph/data?limit=100`
3. **Cypher Query**: Backend executes Cypher query on AGE graph:
   ```cypher
   MATCH (p:Person)
   WITH p LIMIT $limit
   OPTIONAL MATCH (p)-[r:PARENT_OF|MARRIED_TO|BAPTIZED_IN|DIED_IN|GODPARENT_OF]->(related)
   RETURN p, r, related
   ```
4. **Data Transformation**: Backend converts AGE format to JSON
5. **Visualization**: Frontend renders graph using Vis.js
6. **Interaction**: User can click nodes, pan, zoom, and explore

## Usage

### Accessing the Visualizer

1. Navigate to the Korzen home page
2. Click the "🌳 Graph Visualizer" button in the navigation
3. Or directly visit: `http://localhost:5000/graph`

### Loading Data

1. Set the desired node limit (default: 100)
2. Click "Load Graph" to fetch and display data
3. Wait for the graph to stabilize (physics simulation)

### Exploring the Graph

- **Pan**: Click and drag on empty space
- **Zoom**: Use mouse wheel or pinch gesture
- **Select Node**: Click on any node to view details
- **Reset View**: Click "Reset View" to fit all nodes in view
- **Hover**: Hover over nodes to see tooltips

### Performance Considerations

- **Node Limit**: Start with 100 nodes for best performance
- **Large Graphs**: Increase limit gradually (200, 500, 1000)
- **Physics**: Graph stabilizes after ~200 iterations
- **Browser**: Modern browsers (Chrome, Firefox, Safari, Edge) recommended

## File Structure

```
src/app/
├── routes/
│   └── main.py                 # Added /graph and /api/graph/data routes
└── templates/
    ├── graph.html              # Graph visualizer page (NEW)
    ├── index.html              # Updated with graph link
    └── persons.html            # Updated with graph link
```

## Integration with AGE

The visualizer queries the Apache AGE graph database directly:

1. **Graph Name**: `genealogy`
2. **Vertex Labels**: `Person`, `Event`, `Source`
3. **Edge Labels**: `PARENT_OF`, `MARRIED_TO`, `BAPTIZED_IN`, `DIED_IN`, `GODPARENT_OF`
4. **Properties**: All vertex and edge properties are preserved

## Future Enhancements

### Potential Features
- [ ] Filter by date range
- [ ] Filter by location
- [ ] Search for specific persons
- [ ] Highlight family branches
- [ ] Export graph as image (PNG, SVG)
- [ ] Save/load custom views
- [ ] Timeline view
- [ ] Ancestor/descendant path highlighting
- [ ] Clustering by family groups
- [ ] 3D visualization option

### Performance Optimizations
- [ ] Server-side graph layout
- [ ] Incremental loading (load more on demand)
- [ ] Graph caching
- [ ] WebGL rendering for large graphs
- [ ] Virtual scrolling for large datasets

## Troubleshooting

### Graph Not Loading
- **Check AGE Connection**: Ensure PostgreSQL with AGE is running
- **Check Graph Exists**: Verify `genealogy` graph exists in database
- **Check Data**: Ensure persons and relationships have been imported
- **Browser Console**: Check for JavaScript errors

### Performance Issues
- **Reduce Node Limit**: Try loading fewer nodes (50-100)
- **Disable Physics**: Temporarily disable physics simulation
- **Clear Browser Cache**: Refresh the page with Ctrl+F5
- **Update Browser**: Use latest version of modern browser

### Display Issues
- **Overlapping Nodes**: Increase spring length in physics settings
- **Nodes Too Small**: Adjust node size in configuration
- **Labels Unreadable**: Zoom in or increase font size

## API Error Handling

The API endpoint handles errors gracefully:

```json
{
  "error": "Failed to fetch graph data: <error message>",
  "nodes": [],
  "edges": [],
  "count": 0
}
```

Common errors:
- **Graph not found**: AGE graph hasn't been created
- **Connection error**: PostgreSQL/AGE not accessible
- **Query timeout**: Too many nodes requested
- **Invalid data**: Malformed AGE response

## Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+
- ⚠️ Internet Explorer: Not supported

## Dependencies

### Backend
- Flask (routing)
- SQLAlchemy (database connection)
- psycopg (PostgreSQL driver)
- Apache AGE (graph database)

### Frontend
- Vis.js Network (graph visualization)
- Vanilla JavaScript (no framework required)
- Modern CSS (flexbox, gradients, animations)

## License

Part of the Korzen genealogy application.

## Credits

- **Vis.js**: Graph visualization library
- **Apache AGE**: Graph database extension for PostgreSQL
- **Design**: Inspired by modern genealogy applications
