# Family Tree Visualizer - Genealogy Style

## Overview

The graph visualizer has been transformed into a genealogy-style family tree that displays people, their families, and descendants in a hierarchical layout traveling downward from ancestors to descendants.

## Key Changes

### 1. Hierarchical Layout
- **Direction**: Top-to-bottom (ancestors at top, descendants below)
- **Layout Algorithm**: Hierarchical with directed sorting
- **Spacing**: 
  - Node spacing: 150px (horizontal between siblings)
  - Level separation: 200px (vertical between generations)
  - Tree spacing: 250px (between separate family trees)
- **Physics**: Disabled for stable hierarchical positioning

### 2. Visual Styling

#### Person Nodes
- **Shape**: Box (rectangular) instead of circles
- **Male**: Light blue background (#e3f2fd) with dark blue border (#1976d2)
- **Female**: Light pink background (#fce4ec) with dark pink border (#c2185b)
- **Unknown**: Light gray background (#f5f5f5) with gray border (#757575)
- **Labels**: Show name and birth-death years (e.g., "John Smith\n(1850 - 1920)")
- **Root Ancestor**: Orange border (#ff6f00) when selected

#### Relationships
- **Parent → Child**: Dark green (#2e7d32), solid line, width 3, with arrow
- **Marriage**: Pink (#c2185b), dashed line, width 2, with 💑 emoji
- **Other relationships**: Hidden (godparents, events) for cleaner family tree view

#### Event Nodes
- **Hidden**: Event nodes are filtered out in family tree view for simplicity

### 3. API Endpoint Updates

#### Route: `/api/graph/data`
**New Parameters**:
- `limit` (default: 100): Maximum number of people to show
- `depth` (default: 3): Number of descendant generations to display
- `root_id` (optional): UUID of ancestor to start from

**Query Behavior**:
- **With root_id**: Shows descendants only, following PARENT_OF edges downward
- **Without root_id**: Shows all people with family relationships (PARENT_OF, MARRIED_TO)
- **Relationship Focus**: Only PARENT_OF and MARRIED_TO relationships are included

**Cypher Query Example** (with root):
```cypher
MATCH (root:Person {uuid: 'root-uuid'})
OPTIONAL MATCH path = (root)-[:PARENT_OF*0..3]->(descendant:Person)
WITH DISTINCT descendant AS p
LIMIT 100
OPTIONAL MATCH (p)-[r:PARENT_OF|MARRIED_TO]->(related:Person)
RETURN p, r, related
```

### 4. User Interface

#### Controls
- **Person Limit**: Adjust number of people to load (10-1000)
- **Generations**: Select how many descendant generations to show (1-10)
- **Load Family Tree**: Fetch and display the tree
- **Reset View**: Fit all nodes in viewport
- **Clear Ancestor**: Remove root filter and show all families

#### Statistics
- **People**: Count of person nodes displayed
- **Relationships**: Count of family connections
- **Ancestor**: Name of selected root person (when filtered)

#### Interactions
- **Click**: View person details in info panel
- **Double-click**: Set person as root ancestor to show their descendants
- **Pan**: Click and drag to move view
- **Zoom**: Mouse wheel to zoom in/out

#### Legend
Updated to show:
- Male (light blue box)
- Female (light pink box)
- Unknown (gray box)
- Parent → Child (green arrow)
- Marriage 💑 (pink dashed line)

### 5. Terminology Updates

All UI text updated to reflect genealogy focus:
- "Graph Visualizer" → "Family Tree Visualizer"
- "Node" → "Person"
- "Root node" → "Ancestor"
- "Load Graph" → "Load Family Tree"
- "Nodes" → "People"
- "Edges" → "Relationships"
- Hints reference "descendants" instead of generic connections

## Usage

### Viewing the Family Tree

1. Navigate to `/graph` or click "🌳 Graph Visualizer" from home page
2. Adjust settings:
   - Set person limit (default: 100)
   - Set generations depth (default: 3)
3. Click "Load Family Tree"
4. Tree displays with ancestors at top, descendants below

### Focusing on a Family Line

1. Click on any person to view their details
2. Double-click on a person to set them as the root ancestor
3. The tree reloads showing only that person's descendants
4. Click "Clear Ancestor" to return to full view

### Navigation

- **Pan**: Click and drag empty space
- **Zoom**: Use mouse wheel
- **Reset**: Click "Reset View" to fit all people in viewport

## Technical Details

### File Changes

#### [`src/app/templates/graph.html`](src/app/templates/graph.html)
- Updated title and headers
- Changed vis.js configuration to hierarchical layout
- Modified node styling for box shapes with genealogy colors
- Updated edge styling to focus on family relationships
- Added generations depth control
- Updated all UI text and notifications
- Modified legend to show family tree elements

#### [`src/app/routes/main.py`](src/app/routes/main.py)
- Updated `/api/graph/data` endpoint documentation
- Added `depth` parameter support
- Modified Cypher queries to focus on PARENT_OF and MARRIED_TO
- Changed query to follow descendants when root_id provided
- Updated to filter only family relationships

### Vis.js Configuration

```javascript
{
  layout: {
    hierarchical: {
      enabled: true,
      direction: 'UD',              // Up-Down
      sortMethod: 'directed',       // Follow edge direction
      nodeSpacing: 150,
      levelSeparation: 200,
      treeSpacing: 250,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true
    }
  },
  physics: {
    enabled: false                  // Stable layout
  },
  nodes: {
    shape: 'box',
    margin: 10,
    widthConstraint: { min: 100, max: 200 }
  },
  edges: {
    smooth: {
      type: 'cubicBezier',
      forceDirection: 'vertical'
    }
  }
}
```

## Benefits

### 1. Traditional Genealogy View
- Familiar top-to-bottom family tree layout
- Clear parent-child relationships
- Easy to trace lineages

### 2. Simplified Display
- Focus on core family relationships
- Removed clutter from events and godparents
- Clean, readable presentation

### 3. Descendant Focus
- Start from any ancestor
- See multiple generations of descendants
- Adjustable depth for exploration

### 4. Better Visual Encoding
- Box shapes show more information (names + dates)
- Color coding by gender
- Clear relationship indicators

## Future Enhancements

Potential additions:
- [ ] Spouse grouping (show married couples side-by-side)
- [ ] Sibling ordering by birth date
- [ ] Collapsible branches (hide/show descendants)
- [ ] Ancestor view (show parents/grandparents upward)
- [ ] Both directions (ancestors above, descendants below)
- [ ] Export as PDF/PNG
- [ ] Print-friendly view
- [ ] Search and highlight person
- [ ] Filter by date range or location
- [ ] Show photos/portraits in nodes

## Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

## Performance

- Recommended: 100-200 people for smooth interaction
- Maximum: 1000 people (may be slow on older devices)
- Generations: 3-5 levels recommended for readability

## Troubleshooting

### Tree looks cluttered
- Reduce person limit
- Reduce generation depth
- Select a specific ancestor to focus on

### Can't see all people
- Click "Reset View" to fit all nodes
- Zoom out with mouse wheel
- Increase person limit if some are missing

### Relationships not showing
- Ensure PARENT_OF relationships exist in database
- Check that people have been imported from GEDCOM
- Verify AGE graph is populated

## Credits

- **Vis.js Network**: Hierarchical graph visualization
- **Apache AGE**: Graph database for genealogy data
- **Design**: Traditional genealogy tree principles
