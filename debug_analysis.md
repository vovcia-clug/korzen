# calculateNodeLevels() Math.min() Failure Analysis

## Code Review Summary

The [`calculateNodeLevels()`](src/app/templates/graph.html:664) function uses BFS to assign hierarchical levels to nodes. Key components:

1. **Lines 696-698**: BFS initialization - roots start at level 0
2. **Lines 704-715**: Revisited node logic - if a node is encountered again at a lower level, update it and its spouse
3. **Lines 720-734**: Spouse synchronization - when processing a node, ensure spouse is at same level
4. **Lines 736-745**: Child queuing - add children at parent's level + 1

## Critical Bug: The Math.min() Problem

### Scenario: Three-generation family with one spouse having no parents

```
Generation 0: Alice (root, no parents in graph)
Generation 1: Bob (child of Alice), Carol (spouse of Bob, no parents in graph - married in)
Generation 2: David (child of Bob and Carol)
```

### BFS Trace with Math.min()

**Initialization:**
- Roots detected: [Alice, Carol] (both have no parents)
- Queue: [{Alice, 0}, {Carol, 0}]

**Step 1: Process Alice**
- visited = {Alice}
- levels = {Alice: 0}
- No spouse
- Add children: Bob is child of Alice
- Queue: [{Carol, 0}, {Bob, 1}]

**Step 2: Process Carol** ← **First critical point**
- visited = {Alice, Carol}
- levels = {Alice: 0, Carol: 0}
- Spouse = Bob
- Bob not in levels yet, so execute line 732: `levels.set(Bob, 0)` 
- **❌ PREMATURE ASSIGNMENT: Bob gets level 0, but Bob should be level 1 (child of Alice)**
- Add children: David is child of Carol
- Queue: [{Bob, 1}, {David, 1}]
- levels = {Alice: 0, Carol: 0, Bob: 0}

**Step 3: Process Bob** ← **Second critical point**
- level = 1 (from queue when Alice added Bob as child)
- visited.has(Bob) = false (Bob hasn't been visited through BFS yet)
- visited.add(Bob)
- Line 718: levels.set(Bob, 1) ← Tries to correct to level 1
- levels = {Alice: 0, Carol: 0, Bob: 1}
- Spouse = Carol
- Line 726: spouseLevel = 0 (Carol's level)
- Line 727: finalLevel = Math.min(1, 0) = 0
- Lines 728-729: **❌ COLLAPSE: Both get pulled down**
  - levels.set(Bob, 0)
  - levels.set(Carol, 0)
- levels = {Alice: 0, Carol: 0, Bob: 0}
- Add children: David at Bob's children go to level + 1 = 0 + 1 = 1
- **❌ But "level" variable = 1 from line 701, not the updated 0**
- Queue.push({David, 2})
- Queue: [{David, 1}, {David, 2}]

**Step 4: Process David (first occurrence)**
- level = 1 (added by Carol in step 2)
- levels.set(David, 1)
- **❌ WRONG: David should be generation 2, but is at level 1**

**Step 5: Process David (second occurrence)**
- level = 2 (added by Bob in step 3)
- visited.has(David) = true
- Line 706: levels.get(David) = 1, current level = 2
- 1 > 2? No, so doesn't update
- Continue and skip

**Final Result:**
- Alice: 0 ✓ (correct)
- Carol: 0 ✓ (correct - root with no parents)
- Bob: 0 ❌ (should be 1 - is Alice's child)
- David: 1 ❌ (should be 2 - is Bob/Carol's child)

### Why This Causes Complete Collapse

The cascade effect:
1. Spouses without parents are (correctly) treated as roots at level 0
2. When such a spouse is processed in BFS, it **prematurely sets its spouse's level** (line 732) before that spouse can be properly positioned by their parents
3. Later, when the spouse is encountered through normal parent-child relationships, Math.min() **actively pulls them back down** to the root level
4. The spouse's children then get added at wrong levels (off by 1 generation)
5. If those children have spouses without parents, the pattern repeats
6. Result: Multi-generational collapse toward level 0-1

### The Revisit Logic Amplification (lines 704-715)

The revisit logic makes this worse:
- Line 706: If a node is encountered at a LOWER level, it updates to that lower level
- This means if a child is accidentally added to the queue at level 1 (when it should be level 2), and later added at level 2, the level 1 value wins
- Combined with Math.min() in spouse logic, this creates a "race to the bottom"

## Why Math.max() Also Failed (Original Problem)

With Math.max():
- Spouses would be pushed to the level of whoever has parents
- Problem: When both spouses have parents at different levels, they get separated
- Example: Bob (child of Alice at level 0) marries Carol (child of Xavier at level 0)
  - Bob encountered first → level 1
  - Carol encountered → level 1
  - When they meet: Math.max(1, 1) = 1 ✓ Works here
- BUT: Bob (level 1) marries Carol (no parents, root at level 0)
  - Bob processed first → level 1
  - Carol processed → level 0
  - When Carol meets Bob: Math.max(0, 1) = 1
  - Carol gets pushed to level 1 ✓ Works!
  - But Bob processed first: Math.max(1, 0) = 1
  - Stays at 1, Carol stays at 0 ❌ Separated!

The issue with Math.max() is ordering-dependent and causes spouse separation.

## Root Cause Analysis

### The Fundamental Conflict

There are TWO competing goals:
1. **Spouse synchronization**: Spouses must be at the same level
2. **Hierarchical integrity**: Children must be exactly 1 level below their parents

The current algorithm tries to solve both simultaneously during BFS traversal, but this creates conflicts:

- **Premature Level Assignment**: Line 732 sets spouse level before BFS naturally discovers them
- **Forced Synchronization**: Lines 727-729 force spouses to same level, overriding parent-based levels
- **Queue Contamination**: Children added to queue using stale level values after spouse sync changes their parent's level

### The Order-Dependency Problem

The algorithm's behavior depends on which spouse is encountered first in BFS:
- If spouse WITH parents encountered first → correct hierarchical level → Math.min pulls spouse down → collapse
- If spouse WITHOUT parents encountered first → sets other spouse to 0 → even worse collapse

This is fundamentally broken.

## Correct Algorithm Design

### Key Insights

1. **Spouses need special handling**: They're not in a parent-child relationship but must share a level
2. **Parent-based levels are authoritative**: A person's level should be determined by their parents, not their spouse
3. **Two-phase approach needed**: 
   - Phase 1: Calculate levels based purely on parent-child hierarchy
   - Phase 2: Adjust spouse levels to match

### Proposed Algorithm

```pseudocode
function calculateNodeLevels(nodes, marriages, parentChildEdges):
    
    // PHASE 1: Calculate hierarchical levels (ignore spouses)
    levels = new Map()
    parentMap = buildParentMap(parentChildEdges)
    roots = findRoots(nodes, parentMap)
    
    queue = roots.map(id => ({id, level: 0}))
    visited = new Set()
    
    while queue is not empty:
        {id, level} = queue.shift()
        
        if visited.has(id):
            // Handle revisit: take MINIMUM level (earliest generation encountered)
            if !levels.has(id) OR levels.get(id) > level:
                levels.set(id, level)
            continue
            
        visited.add(id)
        levels.set(id, level)
        
        // Add ALL children at next level (no spouse special logic yet)
        for each child of id:
            if !visited.has(child):
                queue.push({child, level + 1})
    
    // PHASE 2: Synchronize spouse levels
    spouseMap = buildSpouseMap(marriages)
    
    for each person in nodes:
        spouse = spouseMap.get(person)
        if !spouse:
            continue
            
        personLevel = levels.get(person)
        spouseLevel = levels.get(spouse)
        
        // Strategy: Use the MAXIMUM level (later generation)
        // Rationale: The person deeper in the tree has the authoritative generation
        // This handles "marrying in" - spouse without parents adopts the level
        // of the spouse who has parents
        
        if personLevel != spouseLevel:
            finalLevel = Math.max(personLevel, spouseLevel)
            levels.set(person, finalLevel)
            levels.set(spouse, finalLevel)
    
    return levels
```

### Why This Works

1. **Phase 1 focuses solely on hierarchy**
   - BFS naturally assigns generation levels
   - Parent at level N → child at level N+1
   - No spouse interference during traversal
   - Revisit logic uses minimum to handle multiple paths to same person

2. **Phase 2 resolves spouse conflicts**
   - After all hierarchical levels are stable
   - Uses Math.max() to bring spouses together at the DEEPER level
   - Rationale: Person with parents has "real" generational position
   - Person without parents (married in) should adopt spouse's level
   - Both spouses have parents? Both already calculated, take max (handles edge cases)

### Handling Edge Cases

**Case 1: Both spouses have parents (same generation)**
- Phase 1: Bob = level 1, Carol = level 1
- Phase 2: Math.max(1, 1) = 1, both stay at 1 ✓

**Case 2: One spouse has no parents**
- Phase 1: Bob = level 1 (child of Alice), Carol = level 0 (root)
- Phase 2: Math.max(1, 0) = 1, Carol moves to 1 ✓
- Children of Bob/Carol = level 2 ✓

**Case 3: Both spouses have parents (different generations - unusual)**
- Phase 1: Bob = level 1, Carol = level 2
- Phase 2: Math.max(1, 2) = 2, both move to 2
- Note: This is unusual but happens in complex families. The algorithm chooses the deeper generation.

**Case 4: Multiple marriages**
- Each marriage processed independently in Phase 2
- Each spouse pair synchronized to their max level

### Alternative: Math.min() in Phase 2?

Could we use Math.min() in Phase 2 instead?
- Bob = level 1 (has parents), Carol = level 0 (no parents)
- Math.min(1, 0) = 0 → Both at level 0
- But Bob is child of Alice at level 0, so Bob's children would be at level 1
- This is wrong - violates hierarchy

**Conclusion**: Must use Math.max() in Phase 2 to preserve hierarchy.

## Specific Code Changes Needed

### Current Problems in Code

1. **Lines 720-734**: Spouse logic integrated into BFS - remove this
2. **Lines 704-715**: Revisit logic updates spouse immediately - remove spouse update
3. **Line 727**: Math.min() - change to Math.max() but only in Phase 2
4. **Missing**: No separation between hierarchy calculation and spouse synchronization

### Recommended Changes

```javascript
function calculateNodeLevels(visNodes, marriages, parentChildEdges) {
    const levels = new Map();
    const parentMap = new Map();
    const spouseMap = new Map();
    
    // Build maps (keep lines 669-681 unchanged)
    parentChildEdges.forEach(edge => {
        if (!parentMap.has(edge.to)) {
            parentMap.set(edge.to, new Set());
        }
        parentMap.get(edge.to).add(edge.from);
    });
    
    marriages.forEach(marriage => {
        spouseMap.set(marriage.spouse1Id, marriage.spouse2Id);
        spouseMap.set(marriage.spouse2Id, marriage.spouse1Id);
    });
    
    // Find roots (keep lines 683-694 unchanged)
    const nodeIds = visNodes.map(n => n.id);
    const roots = nodeIds.filter(id => !parentMap.has(id) || parentMap.get(id).size === 0);
    if (roots.length === 0) {
        const minParents = Math.min(...Array.from(parentMap.values()).map(s => s.size));
        roots.push(...nodeIds.filter(id =>
            parentMap.has(id) && parentMap.get(id).size === minParents
        ));
    }
    
    // === PHASE 1: BFS for hierarchical levels (NO spouse logic) ===
    const queue = roots.map(id => ({ id, level: 0 }));
    const visited = new Set();
    
    while (queue.length > 0) {
        const { id, level } = queue.shift();
        
        // Handle revisits - take minimum level
        if (visited.has(id)) {
            if (levels.has(id) && levels.get(id) > level) {
                levels.set(id, level);
            }
            continue;
        }
        
        visited.add(id);
        levels.set(id, level);
        
        // Add all children to queue (no spouse special handling)
        parentChildEdges.forEach(edge => {
            if (edge.from === id && !visited.has(edge.to)) {
                queue.push({ id: edge.to, level: level + 1 });
            }
        });
    }
    
    // Assign default level to disconnected nodes
    nodeIds.forEach(id => {
        if (!levels.has(id)) {
            levels.set(id, 0);
        }
    });
    
    // === PHASE 2: Synchronize spouse levels ===
    const processedPairs = new Set();
    
    nodeIds.forEach(id => {
        const spouseId = spouseMap.get(id);
        if (!spouseId) return;
        
        // Avoid processing same pair twice
        const pairKey = [id, spouseId].sort().join('-');
        if (processedPairs.has(pairKey)) return;
        processedPairs.add(pairKey);
        
        const level1 = levels.get(id) || 0;
        const level2 = levels.get(spouseId) || 0;
        
        if (level1 !== level2) {
            // Use maximum level - spouse without parents adopts level of spouse with parents
            const finalLevel = Math.max(level1, level2);
            levels.set(id, finalLevel);
            levels.set(spouseId, finalLevel);
        }
    });
    
    return levels;
}
```

### Key Changes

1. **Removed lines 720-734**: No spouse logic during BFS
2. **Modified lines 704-715**: Removed spouse update in revisit logic
3. **Simplified lines 736-745**: Only add direct children, not spouse's children (BFS handles both parents naturally)
4. **Added Phase 2 (new lines after 753)**: Separate spouse synchronization using Math.max()
5. **Added processedPairs tracking**: Prevents processing same spouse pair twice

### Why Phase 2 Uses Math.max()

- **Person with parents = authoritative level**: Their generation is determined by ancestry
- **Person without parents = flexible level**: They "marry into" a generation
- **Math.max() = adopt deeper generation**: Brings rootless spouse down to match spouse who has generational context
- **Preserves hierarchy**: Children calculated in Phase 1 based on parent levels are already correct

## Summary

The Math.min() approach failed because it:
1. Prematurely assigns spouse levels during BFS (line 732)
2. Actively collapses hierarchy by pulling nodes toward roots (line 727 Math.min)
3. Creates cascading generational errors that propagate to all descendants

The solution is:
1. **Separate concerns**: Calculate hierarchy first, then synchronize spouses
2. **Use Math.max() in Phase 2**: Bring spouses to the deeper (more authoritative) generation
3. **No spouse logic during BFS**: Let parent-child relationships determine base levels
