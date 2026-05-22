// Graph visualization using vis-network
let network = null;
let nodes = null;
let edges = null;
let currentRootId = null;
let allData = { nodes: [], edges: [] };

// Get translations (passed from template, fallback to English)
const t = window.graphTranslations || {
    born: "Born",
    died: "Died",
    place: "Place",
    occupation: "Occupation",
    source: "Source",
    doubleClickToSetAsAncestor: "Double-click to set as ancestor",
    gender: "Gender",
    birthDate: "Birth Date",
    deathDate: "Death Date",
    birthPlace: "Birth Place",
    relationships: "Relationships",
    loadingGraphData: "Loading graph data",
    errorLoadingGraph: "Error loading graph"
};

// Initialize the graph
function initGraph() {
    const container = document.getElementById('graph');
    
    // Create empty datasets
    nodes = new vis.DataSet([]);
    edges = new vis.DataSet([]);
    
    const data = {
        nodes: nodes,
        edges: edges
    };
    
    const options = getGraphOptions();
    
    network = new vis.Network(container, data, options);
    
    // Add click event listener
    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            showNodeInfo(nodeId);
        }
    });
    
    // Add double-click event listener to set as root
    network.on('doubleClick', function(params) {
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            setAsRoot(nodeId);
        }
    });
}

// Get graph options for hierarchical layout
function getGraphOptions() {
    return {
        nodes: {
            shape: 'box',
            margin: 10,
            widthConstraint: {
                maximum: 200
            },
            font: {
                size: 14,
                face: 'Arial'
            }
        },
        edges: {
            arrows: {
                to: {
                    enabled: true,
                    scaleFactor: 0.5
                }
            },
            smooth: {
                type: 'cubicBezier',
                forceDirection: 'vertical',
                roundness: 0.4
            }
        },
        physics: {
            enabled: true,
            stabilization: {
                enabled: true,
                iterations: 1000,
                updateInterval: 25
            },
            hierarchicalRepulsion: {
                centralGravity: 0.0,
                springLength: 150,
                springConstant: 0.01,
                nodeDistance: 200,
                damping: 0.09
            },
            solver: 'hierarchicalRepulsion'
        },
        layout: {
            hierarchical: {
                enabled: true,
                direction: 'UD',  // Up-Down: older nodes at top, newer at bottom
                sortMethod: 'directed',
                nodeSpacing: 200,
                levelSeparation: 200,
                treeSpacing: 250,
                blockShifting: true,
                edgeMinimization: true,
                parentCentralization: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            navigationButtons: true,
            keyboard: true
        }
    };
}

// Calculate hierarchical levels with spouse grouping
function calculateHierarchicalLevels(nodes, edges) {
    const nodeMap = new Map();
    const levels = new Map();
    const marriages = new Map(); // Track marriage relationships
    
    // Build node map
    nodes.forEach(node => {
        nodeMap.set(node.id, node);
    });
    
    // Identify marriage relationships and build spouse groups
    edges.forEach(edge => {
        if (edge.type === 'MARRIED_TO') {
            // Store both directions for easy lookup
            if (!marriages.has(edge.from)) {
                marriages.set(edge.from, new Set());
            }
            if (!marriages.has(edge.to)) {
                marriages.set(edge.to, new Set());
            }
            marriages.get(edge.from).add(edge.to);
            marriages.get(edge.to).add(edge.from);
        }
    });
    
    // Build parent-child relationships for easier lookup
    const childrenMap = new Map(); // parent -> [children]
    const parentsMap = new Map(); // child -> [parents]
    
    edges.forEach(edge => {
        if (edge.type === 'PARENT_OF') {
            // PARENT_OF goes from parent to child
            if (!childrenMap.has(edge.from)) {
                childrenMap.set(edge.from, []);
            }
            childrenMap.get(edge.from).push(edge.to);
            
            if (!parentsMap.has(edge.to)) {
                parentsMap.set(edge.to, []);
            }
            parentsMap.get(edge.to).push(edge.from);
        }
    });
    
    // Find root nodes (nodes with no parents)
    const roots = nodes.filter(node => !parentsMap.has(node.id));
    
    // Helper function to get all spouses of a person
    function getAllSpouses(personId) {
        const spouses = new Set();
        if (marriages.has(personId)) {
            marriages.get(personId).forEach(spouseId => {
                spouses.add(spouseId);
            });
        }
        return Array.from(spouses);
    }
    
    // Helper function to set level for a person and all their spouses
    function setLevelWithSpouses(personId, targetLevel) {
        const toProcess = [personId];
        const processed = new Set();
        let finalLevel = targetLevel;
        
        while (toProcess.length > 0) {
            const currentId = toProcess.shift();
            
            if (processed.has(currentId)) {
                continue;
            }
            
            processed.add(currentId);
            
            // Set or update level
            const existingLevel = levels.get(currentId);
            if (existingLevel === undefined) {
                levels.set(currentId, finalLevel);
            } else if (existingLevel !== finalLevel) {
                // Conflict: keep minimum level (closer to ancestors)
                finalLevel = Math.min(existingLevel, finalLevel);
                levels.set(currentId, finalLevel);
            }
            
            // Add all spouses to process at same level
            const spouses = getAllSpouses(currentId);
            spouses.forEach(spouseId => {
                if (!processed.has(spouseId)) {
                    toProcess.push(spouseId);
                }
            });
        }
        
        return finalLevel; // Return the final level used
    }
    
    // BFS to assign levels
    const queue = [];
    const processed = new Set();
    
    // Start with root nodes at level 0
    roots.forEach(root => {
        queue.push({ id: root.id, level: 0 });
    });
    
    // If no roots found (circular relationships), start with first node
    if (queue.length === 0 && nodes.length > 0) {
        queue.push({ id: nodes[0].id, level: 0 });
    }
    
    while (queue.length > 0) {
        const { id, level } = queue.shift();
        
        // Skip if already processed
        if (processed.has(id)) {
            continue;
        }
        
        // Set level for this person and all spouses
        const finalLevel = setLevelWithSpouses(id, level);
        
        // Mark person as processed
        processed.add(id);
        
        // Mark all spouses as processed
        const spouses = getAllSpouses(id);
        spouses.forEach(spouseId => {
            processed.add(spouseId);
        });
        
        // Add children to queue at next level
        // Check children of both the person and their spouses
        const peopleToCheckChildren = [id, ...spouses];
        
        peopleToCheckChildren.forEach(personId => {
            if (childrenMap.has(personId)) {
                childrenMap.get(personId).forEach(childId => {
                    if (!processed.has(childId)) {
                        queue.push({ id: childId, level: finalLevel + 1 });
                    }
                });
            }
        });
    }
    
    // Assign levels to any remaining unprocessed nodes (disconnected components)
    nodes.forEach(node => {
        if (!levels.has(node.id)) {
            levels.set(node.id, 0);
        }
    });
    
    return levels;
}

// Load graph data from API
async function loadGraph() {
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const loadBtn = document.getElementById('loadBtn');
    
    try {
        loadingDiv.style.display = 'block';
        errorDiv.style.display = 'none';
        loadBtn.disabled = true;
        
        const limit = document.getElementById('limitInput').value;
        const depth = document.getElementById('depthInput').value;
        
        let url = `/api/graph/data?limit=${limit}&depth=${depth}`;
        if (currentRootId) {
            url += `&root_id=${currentRootId}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load graph data');
        }
        
        allData = data;
        renderGraph(data);
        
        document.getElementById('nodeCount').textContent = data.count || 0;
        
    } catch (error) {
        console.error('Error loading graph:', error);
        errorDiv.textContent = `Error: ${error.message}`;
        errorDiv.style.display = 'block';
    } finally {
        loadingDiv.style.display = 'none';
        loadBtn.disabled = false;
    }
}

// Render graph with data
function renderGraph(data) {
    if (!network) {
        initGraph();
    }
    
    // Clear existing data
    nodes.clear();
    edges.clear();
    
    // Check if source edges should be hidden
    const hideSource = document.getElementById('hideSourceEdges')?.checked;
    
    // Identify source node IDs from edges
    const sourceNodeIds = new Set();
    data.edges.forEach(edge => {
        if (edge.type === 'FROM_SOURCE') {
            // Find which node is the source record (non-Person type)
            const fromNode = data.nodes.find(n => n.id === edge.from);
            const toNode = data.nodes.find(n => n.id === edge.to);
            
            if (fromNode && fromNode.type !== 'Person') {
                sourceNodeIds.add(edge.from);
            }
            if (toNode && toNode.type !== 'Person') {
                sourceNodeIds.add(edge.to);
            }
        }
    });
    
    // Process nodes (no hierarchical levels needed for force-directed layout)
    const processedNodes = data.nodes.map(node => {
        const color = getNodeColor(node);
        const title = getNodeTooltip(node);
        
        // Build label with birth and death years for Person nodes
        let label = node.label;
        if (node.type === 'Person') {
            // Extract years from dates (format: YYYY-MM-DD or just YYYY)
            const birthYear = node.birth_date ? node.birth_date.split('-')[0] : '';
            const deathYear = node.death_date ? node.death_date.split('-')[0] : '';
            
            // Format as "(birth year - death year)"
            if (birthYear || deathYear) {
                label += '\n(' + birthYear + ' - ' + deathYear + ')';
            }
        }
        
        return {
            id: node.id,
            label: label,
            title: title,
            color: color,
            font: {
                color: '#333',
                multi: true,
                bold: {
                    size: 14
                }
            },
            hidden: hideSource && sourceNodeIds.has(node.id)
        };
    });
    
    // Process edges with special handling for marriage edges
    // Filter out edges that should be hidden instead of marking them as hidden
    const processedEdges = data.edges
        .filter(edge => !shouldHideEdge(edge.type))
        .map(edge => {
            const color = getEdgeColor(edge.type);
            const label = edge.type === 'MARRIED_TO' ? '💑' : '';
            
            // For marriage edges, make them very short and strong to group spouses
            const edgeConfig = {
                id: `${edge.from}-${edge.to}-${edge.type}`,
                from: edge.from,
                to: edge.to,
                label: label,
                color: color,
                width: edge.type === 'MARRIED_TO' ? 3 : 2
            };
            
            // Configure marriage edges to keep spouses close together
            if (edge.type === 'MARRIED_TO') {
                edgeConfig.arrows = { to: { enabled: false } };
                edgeConfig.smooth = { enabled: false }; // Straight line for spouses
                edgeConfig.length = 100; // Short fixed length to keep spouses close
                edgeConfig.physics = true; // Enable physics for this edge
            }
            
            return edgeConfig;
        });
    
    // Add nodes and edges
    nodes.add(processedNodes);
    edges.add(processedEdges);
    
    // Fit the network
    setTimeout(() => {
        network.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }, 100);
}

// Get node color based on gender
function getNodeColor(node) {
    if (node.type !== 'Person') {
        return {
            background: '#fff3e0',
            border: '#ff9800'
        };
    }
    
    switch (node.gender?.toLowerCase()) {
        case 'm':
        case 'male':
            return {
                background: '#e3f2fd',
                border: '#1976d2'
            };
        case 'f':
        case 'female':
            return {
                background: '#fce4ec',
                border: '#c2185b'
            };
        default:
            return {
                background: '#f5f5f5',
                border: '#757575'
            };
    }
}

// Get edge color based on relationship type
function getEdgeColor(type) {
    switch (type) {
        case 'PARENT_OF':
            return { color: '#2e7d32', highlight: '#1b5e20' };
        case 'MARRIED_TO':
            return { color: '#c2185b', highlight: '#880e4f' };
        case 'FROM_SOURCE':
            return { color: '#ff9800', highlight: '#f57c00' };
        default:
            return { color: '#757575', highlight: '#424242' };
    }
}

// Get node tooltip
function getNodeTooltip(node) {
    let tooltip = `<strong>${node.label}</strong><br>`;
    
    if (node.birth_date) {
        tooltip += `${t.born}: ${node.birth_date}<br>`;
    }
    if (node.death_date) {
        tooltip += `${t.died}: ${node.death_date}<br>`;
    }
    if (node.birth_place) {
        tooltip += `${t.place}: ${node.birth_place}<br>`;
    }
    if (node.occupation) {
        tooltip += `${t.occupation}: ${node.occupation}<br>`;
    }
    if (node.source) {
        tooltip += `${t.source}: ${node.source}<br>`;
    }
    
    tooltip += `<br><em>${t.doubleClickToSetAsAncestor}</em>`;
    
    return tooltip;
}

// Show node information in side panel
function showNodeInfo(nodeId) {
    const node = allData.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    const infoPanel = document.getElementById('infoPanel');
    const infoTitle = document.getElementById('infoTitle');
    const infoContent = document.getElementById('infoContent');
    
    infoTitle.textContent = node.label;
    
    let content = '<div class="info-details">';
    
    if (node.gender) {
        content += `<p><strong>${t.gender}:</strong> ${node.gender}</p>`;
    }
    if (node.birth_date) {
        content += `<p><strong>${t.birthDate}:</strong> ${node.birth_date}</p>`;
    }
    if (node.death_date) {
        content += `<p><strong>${t.deathDate}:</strong> ${node.death_date}</p>`;
    }
    if (node.birth_place) {
        content += `<p><strong>${t.birthPlace}:</strong> ${node.birth_place}</p>`;
    }
    if (node.occupation) {
        content += `<p><strong>${t.occupation}:</strong> ${node.occupation}</p>`;
    }
    if (node.source) {
        content += `<p><strong>${t.source}:</strong> ${node.source}</p>`;
    }
    
    // Find relationships
    const relationships = allData.edges.filter(e => e.from === nodeId || e.to === nodeId);
    if (relationships.length > 0) {
        content += `<p><strong>${t.relationships}:</strong></p><ul class="relationships-list">`;
        relationships.forEach(rel => {
            const otherId = rel.from === nodeId ? rel.to : rel.from;
            const otherNode = allData.nodes.find(n => n.id === otherId);
            if (otherNode) {
                const direction = rel.from === nodeId ? '→' : '←';
                content += `<li>${direction} ${rel.type}: <span class="person-link" data-person-id="${otherId}">${otherNode.label}</span></li>`;
            }
        });
        content += '</ul>';
    }
    
    content += '</div>';
    infoContent.innerHTML = content;
    
    infoPanel.classList.add('active');
    
    // Add click event listeners to person links
    const personLinks = infoContent.querySelectorAll('.person-link');
    personLinks.forEach(link => {
        link.addEventListener('click', function() {
            const personId = this.getAttribute('data-person-id');
            handlePersonClick(personId);
        });
    });
}

// Handle click on a person link in the relationships list
function handlePersonClick(personId) {
    // First, try to focus on the node in the graph
    if (network && nodes.get(personId)) {
        // Select and focus on the node
        network.selectNodes([personId]);
        network.focus(personId, {
            scale: 1.5,
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
        
        // Show the node's information in the panel
        showNodeInfo(personId);
    } else {
        // If node is not in the current graph view, just show its info
        showNodeInfo(personId);
    }
}

// Close info panel
function closeInfo() {
    const infoPanel = document.getElementById('infoPanel');
    infoPanel.classList.remove('active');
}

// Set node as root ancestor
function setAsRoot(nodeId) {
    const node = allData.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    currentRootId = nodeId;
    
    // Update UI
    document.getElementById('rootName').textContent = node.label;
    document.getElementById('rootIndicator').style.display = 'flex';
    document.getElementById('clearRootBtn').style.display = 'inline-block';
    
    // Reload graph with new root
    loadGraph();
}

// Clear root ancestor
function clearRoot() {
    currentRootId = null;
    
    // Update UI
    document.getElementById('rootIndicator').style.display = 'none';
    document.getElementById('clearRootBtn').style.display = 'none';
    
    // Reload graph
    loadGraph();
}

// Reset view
function resetView() {
    if (network) {
        network.fit({
            animation: {
                duration: 1000,
                easingFunction: 'easeInOutQuad'
            }
        });
    }
}

// Toggle source edges and source nodes
function toggleSourceEdges() {
    // Re-render the graph with updated visibility settings
    // This ensures edges are filtered out completely, not just hidden
    if (allData && allData.nodes && allData.edges) {
        renderGraph(allData);
    }
}

// Check if edge should be hidden
function shouldHideEdge(edgeType) {
    const hideSource = document.getElementById('hideSourceEdges')?.checked;
    if (hideSource && edgeType === 'FROM_SOURCE') return true;
    return false;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Wait for vis library to be available
    if (typeof vis !== 'undefined') {
        initGraph();
        loadGraph();
    } else {
        // Retry after a short delay if vis is not yet loaded
        setTimeout(function() {
            if (typeof vis !== 'undefined') {
                initGraph();
                loadGraph();
            } else {
                console.error('vis-network library failed to load');
                const errorDiv = document.getElementById('error');
                errorDiv.textContent = 'Error: Graph visualization library failed to load. Please refresh the page.';
                errorDiv.style.display = 'block';
            }
        }, 500);
    }
});
