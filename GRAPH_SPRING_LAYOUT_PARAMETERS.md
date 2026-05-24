# Graph Spring Layout Parameters Documentation

## Overview

The graph visualization in [`src/app/static/js/graph.js`](src/app/static/js/graph.js) has been changed from a **hierarchical layout** to a **spring-based (force-directed) layout** using the vis-network library's `forceAtlas2Based` physics solver.

## Layout Type

**Spring-Based Layout (Force-Directed)** - Uses physics simulation to position nodes based on attractive and repulsive forces, creating an organic, natural-looking graph structure.

---

## Available Parameters

### Physics Configuration

#### `physics.enabled`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Enables or disables the physics simulation. When enabled, nodes will move according to force calculations until the graph stabilizes.
- **Recommended Range:** `true` for dynamic layouts, `false` for static positioning

---

#### `physics.solver`
- **Type:** String
- **Default:** `'barnesHut'`
- **Current Value:** `'forceAtlas2Based'`
- **Description:** Determines which physics solver algorithm to use. Options include:
  - `'barnesHut'` - Fast, good for large graphs (default)
  - `'forceAtlas2Based'` - Better clustering, more organic layouts
  - `'repulsion'` - Simple repulsion-based
  - `'hierarchicalRepulsion'` - For hierarchical layouts (previous setting)
- **Recommended:** `'forceAtlas2Based'` for family trees and relationship graphs

---

### ForceAtlas2Based Solver Parameters

#### `physics.forceAtlas2Based.gravitationalConstant`
- **Type:** Number
- **Default:** `-50`
- **Current Value:** `-50`
- **Description:** Controls the strength of the gravitational attraction between nodes. Negative values create repulsion, positive values create attraction.
- **Recommended Range:** `-100` to `-10`
- **Effect:** 
  - More negative = nodes spread out more
  - Less negative = nodes cluster more tightly
  - Positive values = nodes attract each other (usually not desired)

---

#### `physics.forceAtlas2Based.centralGravity`
- **Type:** Number
- **Default:** `0.01`
- **Current Value:** `0.01`
- **Description:** Pulls all nodes toward the center of the canvas. Prevents the graph from drifting apart.
- **Recommended Range:** `0.001` to `0.1`
- **Effect:**
  - Higher values = stronger pull to center, more compact graph
  - Lower values = weaker pull, nodes can spread out more
  - `0` = no central gravity, graph may drift

---

#### `physics.forceAtlas2Based.springLength`
- **Type:** Number
- **Default:** `100`
- **Current Value:** `200`
- **Description:** The natural resting length of the springs (edges) connecting nodes. Determines the ideal distance between connected nodes.
- **Recommended Range:** `50` to `500`
- **Effect:**
  - Higher values = nodes spread out more, longer edges
  - Lower values = nodes cluster closer together, shorter edges
  - Adjust based on graph density and desired spacing

---

#### `physics.forceAtlas2Based.springConstant`
- **Type:** Number
- **Default:** `0.05`
- **Current Value:** `0.08`
- **Description:** The stiffness of the springs connecting nodes. Controls how strongly edges pull connected nodes toward their spring length.
- **Recommended Range:** `0.01` to `0.2`
- **Effect:**
  - Higher values = stiffer springs, nodes reach equilibrium faster
  - Lower values = softer springs, more flexible layout
  - Too high = oscillation and instability
  - Too low = slow convergence

---

#### `physics.forceAtlas2Based.damping`
- **Type:** Number
- **Default:** `0.4`
- **Current Value:** `0.4`
- **Description:** Reduces node velocity over time, helping the simulation stabilize. Acts like friction.
- **Recommended Range:** `0.1` to `0.9`
- **Effect:**
  - Higher values = faster stabilization, less movement
  - Lower values = more movement, slower stabilization
  - `1.0` = instant stop (not recommended)
  - `0.0` = no damping, perpetual motion

---

#### `physics.forceAtlas2Based.avoidOverlap`
- **Type:** Number
- **Default:** `0`
- **Current Value:** `0.5`
- **Description:** Prevents nodes from overlapping by adding repulsion when nodes get too close. Value represents the strength of the overlap avoidance.
- **Recommended Range:** `0` to `1`
- **Effect:**
  - `0` = no overlap avoidance
  - `0.5` = moderate overlap prevention
  - `1.0` = strong overlap prevention
  - Higher values = more spacing between nodes

---

### Stabilization Parameters

#### `physics.stabilization.enabled`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Runs the physics simulation before rendering to find a stable layout. Prevents initial "explosion" effect.
- **Recommended:** `true` for better initial appearance

---

#### `physics.stabilization.iterations`
- **Type:** Number
- **Default:** `1000`
- **Current Value:** `1000`
- **Description:** Maximum number of physics iterations to run during stabilization before displaying the graph.
- **Recommended Range:** `100` to `2000`
- **Effect:**
  - Higher values = more stable initial layout, longer load time
  - Lower values = faster load, potentially less stable layout
  - Adjust based on graph size

---

#### `physics.stabilization.updateInterval`
- **Type:** Number
- **Default:** `50`
- **Current Value:** `25`
- **Description:** How often (in iterations) to update the screen during stabilization. Lower values show more frequent updates.
- **Recommended Range:** `10` to `100`
- **Effect:**
  - Lower values = smoother visual feedback, slightly slower
  - Higher values = faster stabilization, less visual feedback

---

#### `physics.stabilization.onlyDynamicEdges`
- **Type:** Boolean
- **Default:** `false`
- **Current Value:** `false`
- **Description:** If true, only edges with physics enabled will be considered during stabilization.
- **Recommended:** `false` for consistent behavior

---

#### `physics.stabilization.fit`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Automatically zooms to fit all nodes in view after stabilization.
- **Recommended:** `true` for better user experience

---

### General Physics Parameters

#### `physics.timestep`
- **Type:** Number
- **Default:** `0.5`
- **Current Value:** `0.5`
- **Description:** The time step for each physics iteration. Smaller values = more accurate but slower simulation.
- **Recommended Range:** `0.1` to `1.0`
- **Effect:**
  - Lower values = more accurate physics, slower simulation
  - Higher values = faster simulation, less accurate
  - Too high = instability and oscillation

---

#### `physics.adaptiveTimestep`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Automatically adjusts timestep based on simulation stability. Helps prevent oscillation.
- **Recommended:** `true` for better stability

---

### Layout Parameters

#### `layout.randomSeed`
- **Type:** Number or undefined
- **Default:** `undefined`
- **Current Value:** `undefined`
- **Description:** Seed for random initial positioning. Use a specific number for reproducible layouts.
- **Recommended Range:** Any integer, or `undefined` for random
- **Effect:**
  - `undefined` = different layout each time
  - Specific number = same initial layout every time

---

#### `layout.improvedLayout`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Uses an improved initial layout algorithm before physics simulation.
- **Recommended:** `true` for better initial positioning

---

#### `layout.clusterThreshold`
- **Type:** Number
- **Default:** `150`
- **Current Value:** `150`
- **Description:** Threshold for cluster detection in the improved layout algorithm.
- **Recommended Range:** `50` to `300`
- **Effect:** Higher values = fewer, larger clusters detected

---

### Edge Smoothing Parameters

#### `edges.smooth.type`
- **Type:** String
- **Default:** `'dynamic'`
- **Current Value:** `'continuous'`
- **Description:** Type of edge smoothing/curvature. Options:
  - `'continuous'` - Smooth curves
  - `'discrete'` - Straight segments
  - `'dynamic'` - Adapts based on layout
  - `'cubicBezier'` - Bezier curves
- **Recommended:** `'continuous'` for organic spring layouts

---

#### `edges.smooth.roundness`
- **Type:** Number
- **Default:** `0.5`
- **Current Value:** `0.5`
- **Description:** How curved the edges are (for smooth edge types).
- **Recommended Range:** `0` to `1`
- **Effect:**
  - `0` = straight lines
  - `0.5` = moderate curves
  - `1` = maximum curvature

---

### Interaction Parameters

#### `interaction.dragNodes`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Allows users to drag nodes to reposition them.
- **Recommended:** `true` for interactive exploration

---

#### `interaction.dragView`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Allows users to drag the entire canvas to pan the view.
- **Recommended:** `true` for navigation

---

#### `interaction.zoomView`
- **Type:** Boolean
- **Default:** `true`
- **Current Value:** `true`
- **Description:** Allows users to zoom in and out using mouse wheel or pinch gestures.
- **Recommended:** `true` for navigation

---

## Alternative Physics Solvers

### BarnesHut Solver (Alternative)

If you want to switch to the BarnesHut solver for better performance on large graphs, use these parameters:

```javascript
physics: {
    enabled: true,
    solver: 'barnesHut',
    barnesHut: {
        gravitationalConstant: -2000,  // Repulsion strength
        centralGravity: 0.3,            // Pull to center
        springLength: 95,               // Edge length
        springConstant: 0.04,           // Edge stiffness
        damping: 0.09,                  // Friction
        avoidOverlap: 0                 // Overlap prevention
    }
}
```

### Repulsion Solver (Alternative)

For a simpler repulsion-based layout:

```javascript
physics: {
    enabled: true,
    solver: 'repulsion',
    repulsion: {
        centralGravity: 0.2,      // Pull to center
        springLength: 200,        // Edge length
        springConstant: 0.05,     // Edge stiffness
        nodeDistance: 100,        // Minimum distance between nodes
        damping: 0.09             // Friction
    }
}
```

---

## Tuning Tips

### For Dense Graphs (Many Nodes)
- Increase `springLength` (300-500)
- Increase `gravitationalConstant` magnitude (-80 to -100)
- Increase `avoidOverlap` (0.7-1.0)
- Increase `stabilization.iterations` (1500-2000)

### For Sparse Graphs (Few Nodes)
- Decrease `springLength` (100-150)
- Decrease `gravitationalConstant` magnitude (-30 to -50)
- Decrease `centralGravity` (0.005-0.01)

### For Faster Stabilization
- Increase `damping` (0.5-0.7)
- Increase `springConstant` (0.1-0.15)
- Decrease `stabilization.iterations` (500-800)

### For More Organic Layouts
- Use `forceAtlas2Based` solver
- Moderate `damping` (0.3-0.5)
- Lower `springConstant` (0.05-0.08)
- Enable `avoidOverlap` (0.3-0.5)

### For Clustered Layouts
- Increase `centralGravity` (0.05-0.1)
- Decrease `springLength` (100-150)
- Increase `springConstant` (0.1-0.15)

---

## Performance Considerations

- **Large graphs (>500 nodes):** Consider using `barnesHut` solver instead of `forceAtlas2Based`
- **Slow stabilization:** Reduce `stabilization.iterations` or increase `damping`
- **Oscillating nodes:** Increase `damping` or enable `adaptiveTimestep`
- **Overlapping nodes:** Increase `avoidOverlap` or `gravitationalConstant` magnitude

---

## Changes Made

### Previous Configuration (Hierarchical)
- **Layout:** Hierarchical with fixed levels
- **Solver:** `hierarchicalRepulsion`
- **Direction:** Top-down (Up-Down)
- **Characteristics:** Rigid, tree-like structure with defined generations

### Current Configuration (Spring-Based)
- **Layout:** Force-directed with physics simulation
- **Solver:** `forceAtlas2Based`
- **Direction:** Organic, determined by forces
- **Characteristics:** Flexible, natural clustering, interactive repositioning

---

## Code Location

All configuration is in the [`getGraphOptions()`](src/app/static/js/graph.js:60) function in [`src/app/static/js/graph.js`](src/app/static/js/graph.js).

To modify parameters, edit the returned object in this function.
