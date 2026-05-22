# Graph Hierarchy Refactor - Spouse Grouping & Generational Levels

## Overview

This document describes the refactoring of the graph visualization hierarchy calculation to ensure:
1. **Spouses are positioned at the same horizontal level**
2. **Ancestors are positioned above descendants** (lower level numbers = higher position)
3. **Proper generational separation** with consistent level increments

## Problem Statement

The previous implementation had issues with:
- Spouses sometimes appearing at different levels
- Inconsistent handling of multiple marriages
- Race conditions when processing nodes with multiple parent relationships
- Disconnected spouse groups when processing children

## Solution Architecture

### Key Concepts

1. **Level Assignment**: Lower numbers = ancestors (top), higher numbers = descendants (bottom)
   - Level 0: Root ancestors (no parents)
   - Level 1: Their children
   - Level 2: Grandchildren
   - And so on...

2. **Spouse Grouping**: All spouses of a person must be at the same level
   - When a person is assigned level N, all their spouses get level N
   - This ensures horizontal alignment in the visualization

3. **Parent-Child Relationships**: 
   - `PARENT_OF` edges go from parent → child
   - Children are always at parent_level + 1

## Algorithm Details

### Data Structures

```javascript
const marriages = new Map();      // personId -> Set<spouseIds>
const childrenMap = new Map();    // parentId -> [childIds]
const parentsMap = new Map();     // childId -> [parentIds]
const levels = new Map();         // personId -> level number
```

### Phase 1: Build Relationship Maps

1. **Marriage Relationships**: Build bidirectional spouse lookup
   ```javascript
   edges.forEach(edge => {
       if (edge.type === 'MARRIED_TO') {
           marriages.get(edge.from).add(edge.to);
           marriages.get(edge.to).add(edge.from);
       }
   });
   ```

2. **Parent-Child Relationships**: Build lookup maps
   ```javascript
   edges.forEach(edge => {
       if (edge.type === 'PARENT_OF') {
           childrenMap.get(edge.from).push(edge.to);
           parentsMap.get(edge.to).push(edge.from);
       }
   });
   ```

### Phase 2: Find Root Nodes

Root nodes are persons with no parents (ancestors):
```javascript
const roots = nodes.filter(node => !parentsMap.has(node.id));
```

### Phase 3: Level Assignment with BFS

1. **Initialize Queue**: Start with root nodes at level 0
   ```javascript
   roots.forEach(root => {
       queue.push({ id: root.id, level: 0 });
   });
   ```

2. **Process Queue**: For each person:
   - Assign level to person and ALL spouses (using `setLevelWithSpouses`)
   - Mark person and spouses as visited
   - Add all children to queue at level + 1

3. **Spouse Group Processing**: The `setLevelWithSpouses` function:
   - Takes a person and target level
   - Processes person and all their spouses together
   - Handles level conflicts by keeping minimum (closer to ancestors)
   - Returns the final level used for the group

### Phase 4: Handle Disconnected Components

Any unvisited nodes (disconnected from main tree) are assigned level 0:
```javascript
nodes.forEach(node => {
    if (!levels.has(node.id)) {
        levels.set(node.id, 0);
    }
});
```

## Example: Kennedy Family

### Input Structure
```
Generation 0: Patrick Kennedy ←→ Bridget Murphy
              ↓
Generation 1: Patrick Joseph Kennedy ←→ Mary Augusta Hickey
              ↓
Generation 2: Joseph P. Kennedy Sr ←→ Rose Fitzgerald
              ↓
Generation 3: John F. Kennedy ←→ Jacqueline Bouvier
              Robert F. Kennedy ←→ Ethel Skakel
              Edward Kennedy ←→ Virginia Joan Bennett
              ↓
Generation 4: Caroline Kennedy, John F. Kennedy Jr, etc.
```

### Expected Output
```
Level 0: Patrick Kennedy, Bridget Murphy
Level 1: Patrick Joseph Kennedy, Mary Augusta Hickey
Level 2: Joseph P. Kennedy Sr, Rose Fitzgerald
Level 3: John F. Kennedy, Jacqueline Bouvier, Robert F. Kennedy, Ethel Skakel, Edward Kennedy, Virginia Joan Bennett
Level 4: Caroline Kennedy, John F. Kennedy Jr, Kathleen Kennedy, Joseph P. Kennedy II
```

## Key Improvements

### 1. Atomic Spouse Group Processing
**Before**: Spouses were processed individually, leading to race conditions
```javascript
// Old approach - could assign different levels
visited.add(id);
levels.set(id, level);
marriages.get(id).forEach(spouseId => {
    levels.set(spouseId, level);  // Might conflict with other processing
});
```

**After**: Spouses processed as atomic group
```javascript
// New approach - all spouses get same level atomically
const finalLevel = setLevelWithSpouses(id, level);
const spouses = getAllSpouses(id);
spouses.forEach(spouseId => {
    visited.add(spouseId);  // Mark all as visited together
});
```

### 2. Conflict Resolution
When a node is reached via multiple paths, keep the minimum level (closer to ancestors):
```javascript
if (existingLevel !== level) {
    const minLevel = Math.min(existingLevel, level);
    levels.set(currentId, minLevel);
}
```

### 3. Children from All Spouses
Process children from both the person and all their spouses:
```javascript
const peopleToCheckChildren = [id, ...spouses];
peopleToCheckChildren.forEach(personId => {
    if (childrenMap.has(personId)) {
        childrenMap.get(personId).forEach(childId => {
            queue.push({ id: childId, level: finalLevel + 1 });
        });
    }
});
```

## Testing

### Test File: `test_graph_hierarchy.html`

The test file validates:
1. ✓ All spouse pairs are at the same level
2. ✓ Parents are at lower levels than children
3. ✓ Proper generational separation
4. ✓ Visual table showing all person levels

### Running Tests
1. Open `test_graph_hierarchy.html` in a browser
2. Check that all tests pass (green)
3. Review the level table to verify proper grouping

## Integration

### Files Modified
- [`src/app/static/js/graph.js`](src/app/static/js/graph.js:112) - `calculateHierarchicalLevels` function

### Backward Compatibility
- Function signature unchanged
- Return type unchanged (Map<nodeId, level>)
- Fully compatible with existing visualization code

## Visualization Impact

### vis-network Configuration
The hierarchical layout uses the calculated levels:
```javascript
layout: {
    hierarchical: {
        direction: 'UD',           // Up-Down (ancestors at top)
        sortMethod: 'directed',    // Use our level assignments
        nodeSpacing: 150,
        levelSeparation: 150,      // Vertical space between generations
        treeSpacing: 200
    }
}
```

### Node Assignment
Each node gets its calculated level:
```javascript
return {
    id: node.id,
    label: label,
    level: hierarchicalLevels.get(node.id) || 0,  // Use calculated level
    // ... other properties
};
```

## Edge Cases Handled

1. **Multiple Marriages**: Person married multiple times - all spouses at same level
2. **Circular Relationships**: Prevented by visited tracking
3. **Disconnected Components**: Assigned to level 0
4. **No Root Nodes**: First node used as root
5. **Conflicting Paths**: Minimum level (closer to ancestors) wins

## Performance

- **Time Complexity**: O(N + E) where N = nodes, E = edges
  - Single BFS traversal
  - Each node and edge processed once
  
- **Space Complexity**: O(N + E)
  - Maps for relationships and levels
  - Queue for BFS

## Future Enhancements

Potential improvements:
1. **Sibling Ordering**: Sort siblings by birth date
2. **Spouse Positioning**: Position spouses left/right based on marriage order
3. **Generation Labels**: Add visual generation markers (Gen 0, Gen 1, etc.)
4. **Compact Mode**: Reduce spacing for large trees
5. **Focus Mode**: Highlight specific lineages

## References

- GEDCOM Standard: Parent-child relationships via `PARENT_OF`
- vis-network Documentation: Hierarchical layout options
- Graph Theory: BFS for level assignment in DAGs

## Conclusion

The refactored hierarchy calculation ensures proper genealogical visualization with:
- ✓ Spouses horizontally aligned
- ✓ Ancestors above descendants
- ✓ Clear generational separation
- ✓ Robust handling of complex family structures

This provides an intuitive and accurate family tree visualization that matches traditional genealogical chart conventions.
