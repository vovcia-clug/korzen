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
            enabled: false  // Disable physics for pure hierarchical layout
        },
        layout: {
            hierarchical: {
                enabled: true,
                direction: 'UD',  // Up-Down: older nodes at top, newer at bottom
                sortMethod: 'hubsize',
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

// Calculate hierarchical levels based on birth dates with spouse grouping
function calculateHierarchicalLevels(nodes, edges) {
    const levels = new Map();
    const marriages = new Map(); // Track marriage relationships
    
    // Identify marriage relationships
    edges.forEach(edge => {
        if (edge.type === 'MARRIED_TO') {
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
    
    // Extract birth years and calculate levels
    const birthYears = new Map();
    let minYear = Infinity;
    let maxYear = -Infinity;
    
    nodes.forEach(node => {
        if (node.type === 'Person' && node.birth_date) {
            const year = parseInt(node.birth_date.split('-')[0]);
            if (!isNaN(year)) {
                birthYears.set(node.id, year);
                minYear = Math.min(minYear, year);
                maxYear = Math.max(maxYear, year);
            }
        }
    });
    
    // If we have birth years, use them to calculate levels
    if (minYear !== Infinity && maxYear !== -Infinity) {
        // Group years into levels (e.g., every 25-30 years is a generation)
        const yearsPerLevel = 25;
        
        // First pass: assign levels based on birth years
        nodes.forEach(node => {
            if (birthYears.has(node.id)) {
                const year = birthYears.get(node.id);
                // Calculate level: older = lower level number (top of graph)
                const level = Math.floor((year - minYear) / yearsPerLevel);
                levels.set(node.id, level);
            } else {
                // Nodes without birth dates go to level 0
                levels.set(node.id, 0);
            }
        });
        
        // Second pass: adjust spouse levels to match
        const processed = new Set();
        
        nodes.forEach(node => {
            if (processed.has(node.id)) return;
            
            // Get all spouses for this person
            const spouseGroup = [node.id];
            const toCheck = [node.id];
            const groupProcessed = new Set([node.id]);
            
            while (toCheck.length > 0) {
                const currentId = toCheck.shift();
                if (marriages.has(currentId)) {
                    marriages.get(currentId).forEach(spouseId => {
                        if (!groupProcessed.has(spouseId)) {
                            spouseGroup.push(spouseId);
                            toCheck.push(spouseId);
                            groupProcessed.add(spouseId);
                        }
                    });
                }
            }
            
            // Find the average level for the spouse group
            let totalLevel = 0;
            let count = 0;
            spouseGroup.forEach(id => {
                if (levels.has(id)) {
                    totalLevel += levels.get(id);
                    count++;
                }
            });
            
            if (count > 0) {
                const avgLevel = Math.round(totalLevel / count);
                // Set all spouses to the same level
                spouseGroup.forEach(id => {
                    levels.set(id, avgLevel);
                    processed.add(id);
                });
            }
        });
    } else {
        // Fallback: all nodes at level 0
        nodes.forEach(node => {
            levels.set(node.id, 0);
        });
    }
    
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
    
    // Build marriage map to identify spouse pairs
    const marriages = new Map(); // person_id -> Set of spouse_ids
    data.edges.forEach(edge => {
        if (edge.type === 'MARRIED_TO') {
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
    
    // Deduplicate parent-child edges: only one edge per child from married couples
    const childToParents = new Map(); // child_id -> [parent_ids]
    const parentChildEdges = data.edges.filter(e => e.type === 'PARENT_OF');
    
    parentChildEdges.forEach(edge => {
        const childId = edge.to;
        if (!childToParents.has(childId)) {
            childToParents.set(childId, []);
        }
        childToParents.get(childId).push(edge.from);
    });
    
    // Determine which parent-child edges to keep
    const edgesToKeep = new Set();
    childToParents.forEach((parents, childId) => {
        if (parents.length === 1) {
            // Only one parent, keep the edge
            edgesToKeep.add(`${parents[0]}-${childId}-PARENT_OF`);
        } else if (parents.length === 2) {
            // Check if parents are married to each other
            const [parent1, parent2] = parents;
            const areMarried = marriages.has(parent1) && marriages.get(parent1).has(parent2);
            
            if (areMarried) {
                // Parents are married, keep only one edge (prefer first parent)
                edgesToKeep.add(`${parent1}-${childId}-PARENT_OF`);
            } else {
                // Parents are not married, keep both edges
                edgesToKeep.add(`${parent1}-${childId}-PARENT_OF`);
                edgesToKeep.add(`${parent2}-${childId}-PARENT_OF`);
            }
        } else {
            // More than 2 parents (unusual), keep all edges
            parents.forEach(parentId => {
                edgesToKeep.add(`${parentId}-${childId}-PARENT_OF`);
            });
        }
    });
    
    // Calculate hierarchical levels with spouse grouping
    const levels = calculateHierarchicalLevels(data.nodes, data.edges);
    
    // Process nodes with hierarchical levels
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
            level: levels.get(node.id) || 0,  // Assign hierarchical level
            hidden: hideSource && sourceNodeIds.has(node.id)
        };
    });
    
    // Process edges with special handling for marriage edges and parent-child deduplication
    // Filter out edges that should be hidden instead of marking them as hidden
    const processedEdges = data.edges
        .filter(edge => {
            // Filter out hidden edges
            if (shouldHideEdge(edge.type)) return false;
            
            // Filter out duplicate parent-child edges
            if (edge.type === 'PARENT_OF') {
                const edgeKey = `${edge.from}-${edge.to}-PARENT_OF`;
                return edgesToKeep.has(edgeKey);
            }
            
            return true;
        })
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
