# Spouse Grouping and Family Unit Implementation for Family Tree Visualizer

## Overview
Enhanced the family tree visualizer to visually group married couples (husband and wife) together on the graph and create unified parent-child connections from the family unit, making family relationships clearer and more intuitive. Children now have a single connection coming from the middle of their parents' marriage instead of two separate connections.

## Changes Made

### 1. Layout Configuration Updates
**File:** [`src/app/templates/graph.html`](src/app/templates/graph.html)

#### Adjusted Hierarchical Layout Settings:
- **Reduced `nodeSpacing`**: Changed from 150 to 80 pixels to allow spouses to be positioned closer together horizontally
- **Disabled `edgeMinimization`**: Changed from `true` to `false` to allow custom positioning of spouse nodes
- **Added `shakeTowards`**: Set to 'leaves' to help organize tree structure better

#### Enabled Physics Engine:
- **Enabled physics**: Changed from `false` to `true` to allow dynamic positioning adjustments
- **Added stabilization**: Configured with 200 iterations to ensure smooth layout convergence
- **Configured hierarchical repulsion**: Fine-tuned spring constants and node distances for optimal spouse grouping

### 2. Spouse Detection and Grouping Logic

Added JavaScript code to:
1. **Identify married couples**: Scan all edges to find `MARRIED_TO` relationships
2. **Create spouse groups**: Assign unique group IDs to each married couple
3. **Mark spouse nodes**: Tag nodes that are part of a marriage with their group ID

```javascript
// Group spouses together by assigning them to the same level
const marriages = visEdges.filter(e => e.label === '💑');
const spouseGroups = new Map();

marriages.forEach(marriage => {
    const spouse1Id = marriage.from;
    const spouse2Id = marriage.to;
    const groupId = `couple_${spouse1Id}_${spouse2Id}`;
    spouseGroups.set(spouse1Id, groupId);
    spouseGroups.set(spouse2Id, groupId);
});
```

### 3. Family Unit Node Creation

Added logic to create invisible "family unit" nodes that represent married couples:

1. **Detect common children**: Identify children who have both parents in the marriage
2. **Create family unit nodes**: Add invisible dot nodes positioned between the couple
3. **Redirect parent-child edges**: Remove duplicate edges from each parent and create single edges from family unit to children
4. **Filter edges**: Only create family unit nodes for couples with common children

```javascript
// Create invisible family unit nodes for each married couple
marriages.forEach((marriage, index) => {
    const familyUnitId = `family_unit_${spouse1Id}_${spouse2Id}`;
    
    // Find common children (children of both parents)
    const commonChildren = new Set([...spouse1Children].filter(x => spouse2Children.has(x)));
    
    // Only create family unit node if there are common children
    if (commonChildren.size > 0) {
        visNodes.push({
            id: familyUnitId,
            shape: 'dot',
            size: 1,
            color: { background: 'transparent', border: 'transparent' }
        });
    }
});
```

### 4. Edge Redirection Logic

Implemented smart edge management to eliminate duplicate parent-child connections:

1. **Track parent-child relationships**: Build a map of which children belong to which parents
2. **Identify common children**: Find children who have both parents from a marriage
3. **Remove duplicate edges**: Mark original parent→child edges for removal
4. **Add family unit edges**: Create single edges from family unit node to each common child
5. **Preserve single-parent edges**: Keep edges for children with only one parent

### 5. Post-Stabilization Positioning

Added an event handler that runs after the initial graph stabilization to:
1. **Calculate midpoints**: Find the center point between each spouse pair
2. **Position spouses side-by-side**: Place spouses 120 pixels apart horizontally at the same vertical level
3. **Position family unit nodes**: Place invisible nodes 40 pixels below the couple's midpoint
4. **Fix positions**: Lock all positions to prevent drift
5. **Smooth animation**: Re-fit the view with a smooth animation

```javascript
network.once('stabilizationIterationsDone', function() {
    // For each marriage, position spouses side by side
    marriages.forEach(marriage => {
        const midX = (pos1.x + pos2.x) / 2;
        const midY = (pos1.y + pos2.y) / 2;
        const spacing = 120;
        
        // Position spouse1 on left, spouse2 on right
        updates.push({
            id: spouse1Id,
            x: midX - spacing / 2,
            y: midY,
            fixed: { x: true, y: true }
        });
    });
});
```

### 6. Marriage Edge Styling Updates

Enhanced the visual appearance of marriage connections:
- **Changed line style**: From dashed to solid for stronger visual connection
- **Increased width**: From 2 to 3 pixels for better visibility
- **Horizontal smoothing**: Marriage edges use horizontal curve type for cleaner appearance
- **Reduced roundness**: Set to 0.2 for more direct connection between spouses

### 7. Legend Update

Updated the graph legend to reflect the new marriage line style:
- Changed from dashed line to solid line representation
- Added text "(grouped together)" to clarify the spouse grouping feature

## Visual Results

### Before:
- Spouses could be positioned far apart vertically or horizontally
- Marriage relationships were shown with dashed lines
- No special positioning logic for married couples
- **Each child had two separate connections** - one from mother and one from father
- Duplicate edges made the graph cluttered and harder to read

### After:
- **Spouses are positioned side-by-side** at the same vertical level
- **120-pixel horizontal spacing** between husband and wife
- **Solid pink lines** (💑) connect married couples
- **Single connection from family unit** to each child, originating from the middle of the couple
- **Invisible family unit nodes** positioned 40 pixels below the couple's midpoint
- **No duplicate parent-child edges** for children with both parents
- **Positions are locked** after initial layout to maintain grouping
- **Smooth animations** when the graph loads and adjusts
- **Cleaner, more readable** family tree structure

## Technical Benefits

1. **Improved Readability**: Family units are visually distinct and easy to identify
2. **Reduced Visual Clutter**: Single connection per child instead of two eliminates duplicate edges
3. **Better Hierarchy**: Parent-child relationships remain clear while spouses are grouped
4. **Consistent Layout**: Spouse and family unit positions are fixed after stabilization, preventing layout drift
5. **Scalable**: Works with any number of marriages and children in the family tree
6. **Performance**: Stabilization completes in ~200 iterations for smooth loading
7. **Smart Edge Management**: Automatically detects common children and redirects edges appropriately
8. **Preserves Single-Parent Relationships**: Children with only one parent keep their direct connection

## Usage

The spouse grouping feature works automatically when:
1. Loading the family tree graph at `/graph`
2. The graph contains `MARRIED_TO` relationships in the AGE database
3. Both spouses exist as Person nodes in the graph

No additional configuration or user interaction is required - the grouping happens automatically during graph rendering.

## How It Works - Technical Flow

1. **Data Loading**: Graph data is fetched from the API with person nodes and relationship edges
2. **Marriage Detection**: All `MARRIED_TO` edges are identified
3. **Parent-Child Analysis**: Build a map of which children belong to which parents
4. **Common Children Identification**: For each marriage, find children who have both parents
5. **Family Unit Creation**: Create invisible nodes for couples with common children
6. **Edge Redirection**: Remove duplicate parent→child edges and create family_unit→child edges
7. **Initial Layout**: vis.js hierarchical layout positions all nodes
8. **Stabilization**: Physics engine runs for 200 iterations
9. **Post-Processing**: Custom positioning logic places spouses side-by-side and family units in the middle
10. **Position Locking**: All adjusted positions are locked to prevent drift
11. **Final Animation**: Smooth zoom-to-fit animation completes the visualization

## Future Enhancements

Potential improvements for future versions:
- Add visual containers/boxes around spouse pairs
- Support for multiple marriages (same person married multiple times)
- Configurable spacing between spouses via UI controls
- Option to toggle spouse grouping on/off
- Special handling for divorced couples vs. current marriages
- Visual indicators on family unit nodes (e.g., small marriage icon)
- Configurable family unit node positioning (above, below, or middle of couple)
