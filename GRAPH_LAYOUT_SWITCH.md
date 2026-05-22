# Graph Layout Switch: Hierarchical to Force-Directed

## Problem

The hierarchical layout algorithm in [`graph.js`](src/app/static/js/graph.js) was only generating 3 levels in the graph hierarchy, failing to properly represent multi-generational family trees. Test results showed:

- **Spouse alignment**: ✓ PASS - Spouses were correctly placed at the same level
- **Generation hierarchy**: ✗ FAIL - All ancestors were placed at level 0 instead of incrementing by generation
- Only 3 distinct levels were created (0, 1, and sometimes 2)

### Root Cause

The [`calculateHierarchicalLevels()`](src/app/static/js/graph.js:112) function had a fundamental flaw:
- It started with root nodes (those with no parents) at level 0
- However, the BFS traversal and spouse grouping logic caused all ancestors to collapse to level 0
- Only the youngest generations (children with no descendants) were assigned higher levels

## Solution

**Disabled hierarchical layout entirely** and switched to a **force-directed physics-based layout** using the Barnes-Hut algorithm.

### Changes Made

#### 1. Updated Graph Options ([`getGraphOptions()`](src/app/static/js/graph.js:59))

**Before:**
```javascript
layout: {
    hierarchical: {
        direction: 'UD',
        sortMethod: 'directed',
        nodeSpacing: 150,
        levelSeparation: 150,
        treeSpacing: 200,
        shakeTowards: 'leaves'
    }
},
physics: {
    enabled: false
}
```

**After:**
```javascript
layout: {
    randomSeed: 42,
    improvedLayout: true
},
physics: {
    enabled: true,
    stabilization: {
        enabled: true,
        iterations: 1000,
        updateInterval: 25
    },
    barnesHut: {
        gravitationalConstant: -8000,
        centralGravity: 0.3,
        springLength: 200,
        springConstant: 0.04,
        damping: 0.09,
        avoidOverlap: 0.5
    },
    solver: 'barnesHut'
}
```

#### 2. Removed Level Calculation ([`renderGraph()`](src/app/static/js/graph.js:307))

- Removed call to `calculateHierarchicalLevels()`
- Removed `level` property assignment from nodes
- Nodes now position themselves naturally based on physics simulation

#### 3. Updated Edge Smoothing

Changed from `cubicBezier` with forced vertical direction to `continuous` smoothing for more natural curves in force-directed layout.

## Benefits of Force-Directed Layout

1. **No hierarchy constraints**: Works with any graph structure, including complex family trees with multiple marriages and generations
2. **Natural clustering**: Related nodes naturally group together through physics simulation
3. **Spouse proximity**: Marriage edges naturally keep spouses close together
4. **Scalability**: Handles large graphs better than hierarchical layout
5. **Interactive**: Users can drag nodes to reorganize the view

## Physics Parameters Explained

- **gravitationalConstant (-8000)**: Strong repulsion between nodes to prevent overlap
- **centralGravity (0.3)**: Moderate pull toward center to keep graph compact
- **springLength (200)**: Desired distance between connected nodes
- **springConstant (0.04)**: Flexibility of connections (lower = more flexible)
- **damping (0.09)**: Reduces oscillation for faster stabilization
- **avoidOverlap (0.5)**: Prevents nodes from overlapping

## Trade-offs

### Advantages
- ✓ Works with any family tree structure
- ✓ No artificial level constraints
- ✓ Natural visual clustering
- ✓ Interactive and flexible

### Disadvantages
- ✗ No guaranteed generational alignment (ancestors not always "above" descendants)
- ✗ Layout may vary slightly between loads (mitigated by `randomSeed: 42`)
- ✗ Requires physics simulation time (1000 iterations)

## Future Improvements

If strict generational hierarchy is needed in the future, consider:

1. **Fix the hierarchical algorithm**: Properly implement generation-based level assignment
2. **Hybrid approach**: Use physics for X-axis positioning but fix Y-axis by generation
3. **Custom layout**: Implement a specialized family tree layout algorithm
4. **Layout toggle**: Allow users to switch between force-directed and hierarchical views

## Testing

The force-directed layout can be tested by:
1. Loading the graph visualization page
2. Observing that nodes arrange themselves naturally
3. Verifying that connected nodes are close together
4. Checking that the graph stabilizes after ~1-2 seconds

## Files Modified

- [`src/app/static/js/graph.js`](src/app/static/js/graph.js:59) - Updated `getGraphOptions()` and `renderGraph()`

## Related Documentation

- [`GRAPH_HIERARCHY_REFACTOR.md`](GRAPH_HIERARCHY_REFACTOR.md) - Previous attempt to fix hierarchical layout
- [`SPOUSE_GROUPING_IMPLEMENTATION.md`](SPOUSE_GROUPING_IMPLEMENTATION.md) - Spouse grouping logic (still relevant for marriage edges)
- [`GRAPH_REFACTOR_SUMMARY.md`](GRAPH_REFACTOR_SUMMARY.md) - Overall graph visualization architecture
