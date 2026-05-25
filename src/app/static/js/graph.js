// Custom genealogical graph visualization.
// The renderer uses SVG for drawing and computes all hierarchical positions client-side.
let graphSvg = null;
let graphLayer = null;
let edgeLayer = null;
let nodeLayer = null;
let nodesById = new Map();
let layoutState = null;
let currentRootId = null;
let allData = { nodes: [], edges: [] };
let selectedNodeId = null;
let viewTransform = { x: 0, y: 0, scale: 1 };
let panState = null;

const SVG_NS = 'http://www.w3.org/2000/svg';
const NODE_WIDTH = 170;
const NODE_HEIGHT = 72;
const SPOUSE_GAP = 28;
const GROUP_GAP = 90;
const GENERATION_GAP = 170;
const SOURCE_GAP = 120;
const FIT_PADDING = 60;
const MIN_SCALE = 0.15;
const MAX_SCALE = 2.5;

// Get translations (passed from template, fallback to English)
const t = window.graphTranslations || {
    born: 'Born',
    died: 'Died',
    place: 'Place',
    occupation: 'Occupation',
    source: 'Source',
    doubleClickToSetAsAncestor: 'Double-click to set as ancestor',
    gender: 'Gender',
    birthDate: 'Birth Date',
    deathDate: 'Death Date',
    birthPlace: 'Birth Place',
    relationships: 'Relationships',
    loadingGraphData: 'Loading graph data',
    errorLoadingGraph: 'Error loading graph'
};

function initGraph() {
    const container = document.getElementById('graph');
    if (!container) return;

    container.innerHTML = '';
    container.classList.add('custom-graph');

    graphSvg = createSvgElement('svg', {
        class: 'graph-svg',
        role: 'img',
        'aria-label': 'Family tree graph'
    });

    graphLayer = createSvgElement('g', { class: 'graph-layer' });
    edgeLayer = createSvgElement('g', { class: 'graph-edges' });
    nodeLayer = createSvgElement('g', { class: 'graph-nodes' });

    graphLayer.appendChild(edgeLayer);
    graphLayer.appendChild(nodeLayer);
    graphSvg.appendChild(graphLayer);
    container.appendChild(graphSvg);

    graphSvg.addEventListener('wheel', handleWheel, { passive: false });
    graphSvg.addEventListener('mousedown', startPan);
    graphSvg.addEventListener('dblclick', function(event) {
        if (event.target === graphSvg) resetView();
    });
    window.addEventListener('mousemove', movePan);
    window.addEventListener('mouseup', endPan);
    window.addEventListener('resize', debounce(function() {
        if (layoutState) fitToLayout(false);
    }, 150));
}

function createSvgElement(tagName, attributes) {
    const element = document.createElementNS(SVG_NS, tagName);
    Object.keys(attributes || {}).forEach(key => {
        element.setAttribute(key, attributes[key]);
    });
    return element;
}

function clearSvg() {
    if (edgeLayer) edgeLayer.innerHTML = '';
    if (nodeLayer) nodeLayer.innerHTML = '';
    nodesById.clear();
    selectedNodeId = null;
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

        let url = `/api/graph/data?limit=${encodeURIComponent(limit)}&depth=${encodeURIComponent(depth)}`;
        if (currentRootId) {
            url += `&root_id=${encodeURIComponent(currentRootId)}`;
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
        clearSvg();
    } finally {
        loadingDiv.style.display = 'none';
        loadBtn.disabled = false;
    }
}

function renderGraph(data) {
    if (!graphSvg) {
        initGraph();
    }

    clearSvg();

    const prepared = prepareGraphData(data);
    layoutState = calculateGenealogicalLayout(prepared.nodes, prepared.edges);

    drawGenerationGuides(layoutState);
    drawEdges(layoutState, prepared.edges);
    drawNodes(layoutState);

    applyTransform();
    setTimeout(function() {
        fitToLayout(true);
    }, 50);
}

function prepareGraphData(data) {
    const hideSource = document.getElementById('hideSourceEdges')?.checked;
    const sourceNodeIds = new Set();

    (data.edges || []).forEach(edge => {
        if (edge.type !== 'FROM_SOURCE') return;

        const fromNode = (data.nodes || []).find(node => node.id === edge.from);
        const toNode = (data.nodes || []).find(node => node.id === edge.to);

        if (fromNode && fromNode.type !== 'Person') sourceNodeIds.add(edge.from);
        if (toNode && toNode.type !== 'Person') sourceNodeIds.add(edge.to);
    });

    const visibleNodes = (data.nodes || []).filter(node => !(hideSource && sourceNodeIds.has(node.id)));
    const visibleNodeIds = new Set(visibleNodes.map(node => node.id));
    const visibleEdges = (data.edges || []).filter(edge => {
        if (shouldHideEdge(edge.type)) return false;
        return visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to);
    });

    return {
        nodes: visibleNodes,
        edges: visibleEdges
    };
}

function calculateGenealogicalLayout(rawNodes, rawEdges) {
    const nodeMap = new Map(rawNodes.map(node => [node.id, node]));
    const relationships = buildRelationshipMaps(rawNodes, rawEdges);
    const groups = buildSpouseGroups(rawNodes, relationships.marriages);

    assignGroupLevels(groups, relationships.parents, relationships.children);
    assignGroupPositions(groups, relationships.parents, relationships.children, nodeMap);

    const positionedNodes = positionNodesInsideGroups(groups, nodeMap);
    const bounds = calculateBounds(positionedNodes);

    return {
        nodes: positionedNodes,
        nodeMap,
        groups,
        relationships,
        bounds
    };
}

function buildRelationshipMaps(rawNodes, rawEdges) {
    const marriages = new Map();
    const parents = new Map();
    const children = new Map();

    rawNodes.forEach(node => {
        marriages.set(node.id, new Set());
        parents.set(node.id, new Set());
        children.set(node.id, new Set());
    });

    rawEdges.forEach(edge => {
        if (!parents.has(edge.from) || !parents.has(edge.to)) return;

        if (edge.type === 'MARRIED_TO') {
            marriages.get(edge.from).add(edge.to);
            marriages.get(edge.to).add(edge.from);
        } else if (edge.type === 'PARENT_OF') {
            children.get(edge.from).add(edge.to);
            parents.get(edge.to).add(edge.from);
        }
    });

    return { marriages, parents, children };
}

function buildSpouseGroups(rawNodes, marriages) {
    const visited = new Set();
    const groups = [];
    const groupByNodeId = new Map();

    rawNodes.forEach(node => {
        if (visited.has(node.id)) return;

        const memberIds = [];
        const queue = [node.id];
        visited.add(node.id);

        while (queue.length > 0) {
            const nodeId = queue.shift();
            memberIds.push(nodeId);

            (marriages.get(nodeId) || new Set()).forEach(spouseId => {
                if (!visited.has(spouseId)) {
                    visited.add(spouseId);
                    queue.push(spouseId);
                }
            });
        }

        const group = {
            id: groups.length,
            memberIds,
            level: 0,
            x: 0,
            y: 0,
            width: Math.max(NODE_WIDTH, memberIds.length * NODE_WIDTH + (memberIds.length - 1) * SPOUSE_GAP),
            parentGroupIds: new Set(),
            childGroupIds: new Set()
        };

        groups.push(group);
        memberIds.forEach(memberId => groupByNodeId.set(memberId, group.id));
    });

    groups.groupByNodeId = groupByNodeId;
    return groups;
}

function assignGroupLevels(groups, parents, children) {
    const groupByNodeId = groups.groupByNodeId;

    groups.forEach(group => {
        group.memberIds.forEach(memberId => {
            (parents.get(memberId) || new Set()).forEach(parentId => {
                const parentGroupId = groupByNodeId.get(parentId);
                if (parentGroupId !== undefined && parentGroupId !== group.id) {
                    group.parentGroupIds.add(parentGroupId);
                    groups[parentGroupId].childGroupIds.add(group.id);
                }
            });

            (children.get(memberId) || new Set()).forEach(childId => {
                const childGroupId = groupByNodeId.get(childId);
                if (childGroupId !== undefined && childGroupId !== group.id) {
                    group.childGroupIds.add(childGroupId);
                    groups[childGroupId].parentGroupIds.add(group.id);
                }
            });
        });
    });

    let changed = true;
    let iterations = 0;

    while (changed && iterations < groups.length * 4 + 20) {
        changed = false;
        iterations += 1;

        groups.forEach(group => {
            let desiredLevel = 0;
            group.parentGroupIds.forEach(parentGroupId => {
                desiredLevel = Math.max(desiredLevel, groups[parentGroupId].level + 1);
            });

            if (desiredLevel > group.level) {
                group.level = desiredLevel;
                changed = true;
            }
        });
    }
}

function assignGroupPositions(groups, parents, children, nodeMap) {
    const levels = new Map();
    groups.forEach(group => {
        if (!levels.has(group.level)) levels.set(group.level, []);
        levels.get(group.level).push(group);
    });

    const sortedLevels = Array.from(levels.keys()).sort((a, b) => a - b);

    sortedLevels.forEach(level => {
        const groupsAtLevel = levels.get(level);
        groupsAtLevel.sort(function(a, b) {
            const parentXDiff = averageParentX(a, groups) - averageParentX(b, groups);
            if (isFinite(parentXDiff) && parentXDiff !== 0) return parentXDiff;
            return compareGroups(a, b, nodeMap);
        });
        spreadGroups(groupsAtLevel, level);
    });

    for (let pass = 0; pass < 3; pass += 1) {
        for (let index = sortedLevels.length - 2; index >= 0; index -= 1) {
            levels.get(sortedLevels[index]).forEach(group => {
                const childXs = Array.from(group.childGroupIds)
                    .map(childGroupId => groups[childGroupId].x)
                    .filter(Number.isFinite);

                if (childXs.length > 0) {
                    group.x = average(childXs);
                }
            });
            normalizeLevel(levels.get(sortedLevels[index]));
        }

        sortedLevels.forEach(level => {
            levels.get(level).sort(function(a, b) {
                const parentXDiff = averageParentX(a, groups) - averageParentX(b, groups);
                if (isFinite(parentXDiff) && parentXDiff !== 0) return parentXDiff;
                return a.x - b.x;
            });
            normalizeLevel(levels.get(level));
        });
    }

    groups.forEach(group => {
        group.y = group.level * GENERATION_GAP;
    });

    placeSourceGroups(groups, nodeMap);
}

function averageParentX(group, groups) {
    const parentXs = Array.from(group.parentGroupIds)
        .map(parentGroupId => groups[parentGroupId].x)
        .filter(Number.isFinite);
    return parentXs.length > 0 ? average(parentXs) : Number.POSITIVE_INFINITY;
}

function spreadGroups(groupsAtLevel, level) {
    const totalWidth = groupsAtLevel.reduce((sum, group) => sum + group.width, 0) + Math.max(0, groupsAtLevel.length - 1) * GROUP_GAP;
    let cursor = -totalWidth / 2;

    groupsAtLevel.forEach(group => {
        group.x = cursor + group.width / 2;
        group.y = level * GENERATION_GAP;
        cursor += group.width + GROUP_GAP;
    });
}

function normalizeLevel(groupsAtLevel) {
    if (!groupsAtLevel || groupsAtLevel.length === 0) return;

    groupsAtLevel.sort((a, b) => a.x - b.x);

    for (let index = 1; index < groupsAtLevel.length; index += 1) {
        const previous = groupsAtLevel[index - 1];
        const current = groupsAtLevel[index];
        const minimumX = previous.x + previous.width / 2 + GROUP_GAP + current.width / 2;
        if (current.x < minimumX) {
            current.x = minimumX;
        }
    }

    const minX = groupsAtLevel[0].x - groupsAtLevel[0].width / 2;
    const maxGroup = groupsAtLevel[groupsAtLevel.length - 1];
    const maxX = maxGroup.x + maxGroup.width / 2;
    const offset = (minX + maxX) / 2;

    groupsAtLevel.forEach(group => {
        group.x -= offset;
    });
}

function placeSourceGroups(groups, nodeMap) {
    const maxPersonLevel = groups.reduce((maxLevel, group) => {
        const hasPerson = group.memberIds.some(nodeId => nodeMap.get(nodeId)?.type === 'Person');
        return hasPerson ? Math.max(maxLevel, group.level) : maxLevel;
    }, 0);

    const sourceGroups = groups.filter(group => group.memberIds.every(nodeId => nodeMap.get(nodeId)?.type !== 'Person'));
    if (sourceGroups.length === 0) return;

    sourceGroups.forEach((group, index) => {
        group.level = maxPersonLevel + 1;
        group.y = maxPersonLevel * GENERATION_GAP + SOURCE_GAP;
        group.x = (index - (sourceGroups.length - 1) / 2) * (NODE_WIDTH + GROUP_GAP);
    });
}

function positionNodesInsideGroups(groups, nodeMap) {
    const positioned = new Map();

    groups.forEach(group => {
        const members = group.memberIds
            .map(nodeId => nodeMap.get(nodeId))
            .filter(Boolean)
            .sort(compareNodesForSpouseOrder);
        const totalWidth = members.length * NODE_WIDTH + Math.max(0, members.length - 1) * SPOUSE_GAP;
        let cursor = group.x - totalWidth / 2;

        members.forEach(node => {
            positioned.set(node.id, {
                ...node,
                x: cursor + NODE_WIDTH / 2,
                y: group.y,
                width: NODE_WIDTH,
                height: NODE_HEIGHT,
                groupId: group.id
            });
            cursor += NODE_WIDTH + SPOUSE_GAP;
        });
    });

    return positioned;
}

function drawGenerationGuides(state) {
    if (!state || !state.bounds) return;

    const levelLabels = new Map();
    state.groups.forEach(group => {
        const hasPerson = group.memberIds.some(nodeId => state.nodeMap.get(nodeId)?.type === 'Person');
        if (hasPerson && !levelLabels.has(group.level)) {
            levelLabels.set(group.level, group.y);
        }
    });

    const left = state.bounds.minX - 120;
    const right = state.bounds.maxX + 120;

    Array.from(levelLabels.keys()).sort((a, b) => a - b).forEach(level => {
        const y = levelLabels.get(level);
        const line = createSvgElement('line', {
            class: 'generation-guide',
            x1: left,
            y1: y,
            x2: right,
            y2: y
        });
        edgeLayer.appendChild(line);

        const label = createSvgElement('text', {
            class: 'generation-label',
            x: left,
            y: y - NODE_HEIGHT / 2 - 14
        });
        label.textContent = `Generation ${level + 1}`;
        edgeLayer.appendChild(label);
    });
}

function drawEdges(state, edgesToRender) {
    const drawnParentChildren = new Set();
    const drawnMarriages = new Set();

    edgesToRender.forEach(edge => {
        const fromNode = state.nodes.get(edge.from);
        const toNode = state.nodes.get(edge.to);
        if (!fromNode || !toNode) return;

        if (edge.type === 'MARRIED_TO') {
            const key = [edge.from, edge.to].sort().join('::');
            if (drawnMarriages.has(key)) return;
            drawnMarriages.add(key);
            drawMarriageEdge(fromNode, toNode);
        } else if (edge.type === 'PARENT_OF') {
            const childParents = Array.from(state.relationships.parents.get(edge.to) || [])
                .filter(parentId => state.nodes.has(parentId));
            const marriedParentIds = childParents.filter(parentId => {
                return childParents.some(otherId => otherId !== parentId && (state.relationships.marriages.get(parentId) || new Set()).has(otherId));
            });

            if (marriedParentIds.length > 1) {
                const key = `${marriedParentIds.sort().join('::')}=>${edge.to}`;
                if (drawnParentChildren.has(key)) return;
                drawnParentChildren.add(key);
                drawParentChildEdge(marriedParentIds.map(parentId => state.nodes.get(parentId)), toNode, true);
            } else {
                drawParentChildEdge([fromNode], toNode, false);
            }
        } else if (edge.type === 'FROM_SOURCE') {
            drawSourceEdge(fromNode, toNode);
        } else {
            drawGenericEdge(fromNode, toNode, edge.type);
        }
    });
}

function drawMarriageEdge(fromNode, toNode) {
    const path = createSvgElement('path', {
        class: 'graph-edge marriage-edge',
        d: `M ${fromNode.x} ${fromNode.y} L ${toNode.x} ${toNode.y}`
    });
    edgeLayer.appendChild(path);

    const label = createSvgElement('text', {
        class: 'edge-label marriage-label',
        x: (fromNode.x + toNode.x) / 2,
        y: fromNode.y - NODE_HEIGHT / 2 - 8,
        'text-anchor': 'middle'
    });
    label.textContent = '💑';
    edgeLayer.appendChild(label);
}

function drawParentChildEdge(parentNodes, childNode, familyConnector) {
    const visibleParents = parentNodes.filter(Boolean);
    if (visibleParents.length === 0) return;

    const fromX = average(visibleParents.map(node => node.x));
    const fromY = Math.max(...visibleParents.map(node => node.y)) + NODE_HEIGHT / 2;
    const toX = childNode.x;
    const toY = childNode.y - NODE_HEIGHT / 2;
    const midY = fromY + Math.max(36, (toY - fromY) / 2);

    if (familyConnector && visibleParents.length > 1) {
        const minParentX = Math.min(...visibleParents.map(node => node.x));
        const maxParentX = Math.max(...visibleParents.map(node => node.x));
        const bridge = createSvgElement('path', {
            class: 'graph-edge family-bridge-edge',
            d: `M ${minParentX} ${fromY - 12} L ${maxParentX} ${fromY - 12}`
        });
        edgeLayer.appendChild(bridge);
    }

    const path = createSvgElement('path', {
        class: 'graph-edge parent-edge',
        d: `M ${fromX} ${fromY} V ${midY} H ${toX} V ${toY}`
    });
    edgeLayer.appendChild(path);
}

function drawSourceEdge(fromNode, toNode) {
    const path = createSvgElement('path', {
        class: 'graph-edge source-edge',
        d: elbowPath(fromNode, toNode)
    });
    edgeLayer.appendChild(path);
}

function drawGenericEdge(fromNode, toNode, type) {
    const path = createSvgElement('path', {
        class: 'graph-edge generic-edge',
        d: elbowPath(fromNode, toNode)
    });
    path.appendChild(createSvgElement('title', {})).textContent = type || 'RELATED_TO';
    edgeLayer.appendChild(path);
}

function elbowPath(fromNode, toNode) {
    const fromY = fromNode.y + (fromNode.y <= toNode.y ? NODE_HEIGHT / 2 : -NODE_HEIGHT / 2);
    const toY = toNode.y + (fromNode.y <= toNode.y ? -NODE_HEIGHT / 2 : NODE_HEIGHT / 2);
    const midY = (fromY + toY) / 2;
    return `M ${fromNode.x} ${fromY} V ${midY} H ${toNode.x} V ${toY}`;
}

function drawNodes(state) {
    state.nodes.forEach(node => {
        const group = createSvgElement('g', {
            class: `graph-node${node.id === currentRootId ? ' root-node' : ''}`,
            transform: `translate(${node.x - NODE_WIDTH / 2}, ${node.y - NODE_HEIGHT / 2})`,
            tabindex: '0',
            role: 'button',
            'data-node-id': node.id
        });

        const color = getNodeColor(node);
        const rect = createSvgElement('rect', {
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
            rx: 8,
            ry: 8,
            fill: color.background,
            stroke: node.id === currentRootId ? '#FFD700' : color.border,
            'stroke-width': node.id === currentRootId ? 5 : 2
        });
        group.appendChild(rect);

        const title = createSvgElement('title', {});
        title.textContent = getNodeTooltipText(node);
        group.appendChild(title);

        const labelLines = getNodeLabelLines(node);
        labelLines.forEach((line, index) => {
            const text = createSvgElement('text', {
                class: index === 0 ? 'node-label node-label-name' : 'node-label node-label-years',
                x: NODE_WIDTH / 2,
                y: NODE_HEIGHT / 2 - ((labelLines.length - 1) * 9) + index * 18,
                'text-anchor': 'middle'
            });
            text.textContent = line;
            group.appendChild(text);
        });

        group.addEventListener('click', function(event) {
            event.stopPropagation();
            selectNode(node.id);
            showNodeInfo(node.id);
        });

        group.addEventListener('dblclick', function(event) {
            event.stopPropagation();
            setAsRoot(node.id);
        });

        group.addEventListener('keydown', function(event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectNode(node.id);
                showNodeInfo(node.id);
            }
        });

        nodeLayer.appendChild(group);
        nodesById.set(node.id, group);
    });
}

function getNodeLabelLines(node) {
    let name = node.label || 'Unknown';
    if (node.id === currentRootId) name = `⭐ ${name}`;

    const lines = [truncateLabel(name, 24)];

    if (node.type === 'Person') {
        const birthYear = extractYear(node.birth_date);
        const deathYear = extractYear(node.death_date);
        if (birthYear || deathYear) {
            lines.push(`(${birthYear || ''} - ${deathYear || ''})`);
        }
    } else if (node.type) {
        lines.push(node.type);
    }

    return lines;
}

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

function getNodeTooltipText(node) {
    const parts = [node.label || 'Unknown'];

    if (node.birth_date) parts.push(`${t.born}: ${node.birth_date}`);
    if (node.death_date) parts.push(`${t.died}: ${node.death_date}`);
    if (node.birth_place) parts.push(`${t.place}: ${node.birth_place}`);
    if (node.occupation) parts.push(`${t.occupation}: ${node.occupation}`);
    if (node.source) parts.push(`${t.source}: ${node.source}`);
    parts.push(t.doubleClickToSetAsAncestor);

    return parts.join('\n');
}

function getNodeTooltip(node) {
    let tooltip = `<strong>${escapeHtml(node.label || 'Unknown')}</strong><br>`;

    if (node.birth_date) tooltip += `${t.born}: ${escapeHtml(node.birth_date)}<br>`;
    if (node.death_date) tooltip += `${t.died}: ${escapeHtml(node.death_date)}<br>`;
    if (node.birth_place) tooltip += `${t.place}: ${escapeHtml(node.birth_place)}<br>`;
    if (node.occupation) tooltip += `${t.occupation}: ${escapeHtml(node.occupation)}<br>`;
    if (node.source) tooltip += `${t.source}: ${escapeHtml(node.source)}<br>`;

    tooltip += `<br><em>${t.doubleClickToSetAsAncestor}</em>`;

    return tooltip;
}

function selectNode(nodeId) {
    if (selectedNodeId && nodesById.has(selectedNodeId)) {
        nodesById.get(selectedNodeId).classList.remove('selected');
    }

    selectedNodeId = nodeId;

    if (nodesById.has(nodeId)) {
        nodesById.get(nodeId).classList.add('selected');
    }
}

function focusNode(nodeId, scale) {
    if (!layoutState || !layoutState.nodes.has(nodeId)) return;

    const container = document.getElementById('graph');
    const node = layoutState.nodes.get(nodeId);
    const nextScale = clamp(scale || Math.max(viewTransform.scale, 1.2), MIN_SCALE, MAX_SCALE);

    viewTransform = {
        scale: nextScale,
        x: container.clientWidth / 2 - node.x * nextScale,
        y: container.clientHeight / 2 - node.y * nextScale
    };
    applyTransform();
    selectNode(nodeId);
}

function applyTransform() {
    if (!graphLayer) return;
    graphLayer.setAttribute('transform', `translate(${viewTransform.x}, ${viewTransform.y}) scale(${viewTransform.scale})`);
}

function fitToLayout(animate) {
    if (!layoutState || !layoutState.bounds) return;

    const container = document.getElementById('graph');
    if (!container || container.clientWidth === 0 || container.clientHeight === 0) return;

    const width = Math.max(1, layoutState.bounds.maxX - layoutState.bounds.minX + FIT_PADDING * 2);
    const height = Math.max(1, layoutState.bounds.maxY - layoutState.bounds.minY + FIT_PADDING * 2);
    const scale = clamp(Math.min(container.clientWidth / width, container.clientHeight / height), MIN_SCALE, MAX_SCALE);
    const centerX = (layoutState.bounds.minX + layoutState.bounds.maxX) / 2;
    const centerY = (layoutState.bounds.minY + layoutState.bounds.maxY) / 2;

    viewTransform = {
        scale,
        x: container.clientWidth / 2 - centerX * scale,
        y: container.clientHeight / 2 - centerY * scale
    };

    if (animate) {
        graphLayer.classList.add('graph-layer-animated');
        setTimeout(function() {
            graphLayer?.classList.remove('graph-layer-animated');
        }, 350);
    }

    applyTransform();
}

function handleWheel(event) {
    if (!layoutState) return;
    event.preventDefault();

    const rect = graphSvg.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const worldX = (mouseX - viewTransform.x) / viewTransform.scale;
    const worldY = (mouseY - viewTransform.y) / viewTransform.scale;
    const zoomFactor = event.deltaY < 0 ? 1.12 : 0.88;
    const nextScale = clamp(viewTransform.scale * zoomFactor, MIN_SCALE, MAX_SCALE);

    viewTransform = {
        scale: nextScale,
        x: mouseX - worldX * nextScale,
        y: mouseY - worldY * nextScale
    };
    applyTransform();
}

function startPan(event) {
    if (event.button !== 0 || event.target.closest('.graph-node')) return;
    panState = {
        startX: event.clientX,
        startY: event.clientY,
        transformX: viewTransform.x,
        transformY: viewTransform.y
    };
    graphSvg.classList.add('panning');
}

function movePan(event) {
    if (!panState) return;

    viewTransform.x = panState.transformX + event.clientX - panState.startX;
    viewTransform.y = panState.transformY + event.clientY - panState.startY;
    applyTransform();
}

function endPan() {
    if (!panState) return;
    panState = null;
    graphSvg?.classList.remove('panning');
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

    if (node.gender) content += `<p><strong>${t.gender}:</strong> ${escapeHtml(node.gender)}</p>`;
    if (node.birth_date) content += `<p><strong>${t.birthDate}:</strong> ${escapeHtml(node.birth_date)}</p>`;
    if (node.death_date) content += `<p><strong>${t.deathDate}:</strong> ${escapeHtml(node.death_date)}</p>`;
    if (node.birth_place) content += `<p><strong>${t.birthPlace}:</strong> ${escapeHtml(node.birth_place)}</p>`;
    if (node.occupation) content += `<p><strong>${t.occupation}:</strong> ${escapeHtml(node.occupation)}</p>`;
    if (node.source) content += `<p><strong>${t.source}:</strong> ${escapeHtml(node.source)}</p>`;

    const relationships = allData.edges.filter(e => e.from === nodeId || e.to === nodeId);
    if (relationships.length > 0) {
        content += `<p><strong>${t.relationships}:</strong></p><ul class="relationships-list">`;
        relationships.forEach(rel => {
            const otherId = rel.from === nodeId ? rel.to : rel.from;
            const otherNode = allData.nodes.find(n => n.id === otherId);
            if (otherNode) {
                const direction = rel.from === nodeId ? '→' : '←';
                content += `<li>${direction} ${escapeHtml(rel.type)}: <span class="person-link" data-person-id="${escapeAttribute(otherId)}">${escapeHtml(otherNode.label)}</span></li>`;
            }
        });
        content += '</ul>';
    }

    content += '</div>';
    infoContent.innerHTML = content;

    infoPanel.classList.add('active');

    const personLinks = infoContent.querySelectorAll('.person-link');
    personLinks.forEach(link => {
        link.addEventListener('click', function() {
            const personId = this.getAttribute('data-person-id');
            handlePersonClick(personId);
        });
    });
}

function handlePersonClick(personId) {
    if (nodesById.has(personId)) {
        focusNode(personId, 1.35);
    }
    showNodeInfo(personId);
}

function closeInfo() {
    const infoPanel = document.getElementById('infoPanel');
    infoPanel.classList.remove('active');
}

function setAsRoot(nodeId) {
    const node = allData.nodes.find(n => n.id === nodeId);
    if (!node || node.type !== 'Person') return;

    currentRootId = nodeId;

    document.getElementById('rootName').textContent = node.label;
    document.getElementById('rootIndicator').style.display = 'flex';
    document.getElementById('clearRootBtn').style.display = 'inline-block';

    loadGraph();
}

function clearRoot() {
    currentRootId = null;

    document.getElementById('rootIndicator').style.display = 'none';
    document.getElementById('clearRootBtn').style.display = 'none';

    loadGraph();
}

function resetView() {
    fitToLayout(true);
}

function toggleSourceEdges() {
    if (allData && allData.nodes && allData.edges) {
        renderGraph(allData);
    }
}

function shouldHideEdge(edgeType) {
    const hideSource = document.getElementById('hideSourceEdges')?.checked;
    return Boolean(hideSource && edgeType === 'FROM_SOURCE');
}

function calculateBounds(positionedNodes) {
    const nodes = Array.from(positionedNodes.values());
    if (nodes.length === 0) {
        return { minX: -100, maxX: 100, minY: -100, maxY: 100 };
    }

    return nodes.reduce((bounds, node) => {
        bounds.minX = Math.min(bounds.minX, node.x - NODE_WIDTH / 2);
        bounds.maxX = Math.max(bounds.maxX, node.x + NODE_WIDTH / 2);
        bounds.minY = Math.min(bounds.minY, node.y - NODE_HEIGHT / 2);
        bounds.maxY = Math.max(bounds.maxY, node.y + NODE_HEIGHT / 2);
        return bounds;
    }, {
        minX: Number.POSITIVE_INFINITY,
        maxX: Number.NEGATIVE_INFINITY,
        minY: Number.POSITIVE_INFINITY,
        maxY: Number.NEGATIVE_INFINITY
    });
}

function compareGroups(a, b, nodeMap) {
    const yearA = groupBirthYear(a, nodeMap);
    const yearB = groupBirthYear(b, nodeMap);
    if (yearA !== yearB) return yearA - yearB;
    return groupLabel(a, nodeMap).localeCompare(groupLabel(b, nodeMap));
}

function compareNodesForSpouseOrder(a, b) {
    const rankA = genderRank(a.gender);
    const rankB = genderRank(b.gender);
    if (rankA !== rankB) return rankA - rankB;

    const yearA = parseBirthYear(a);
    const yearB = parseBirthYear(b);
    if (yearA !== yearB) return yearA - yearB;

    return (a.label || '').localeCompare(b.label || '');
}

function groupBirthYear(group, nodeMap) {
    const years = group.memberIds
        .map(nodeId => parseBirthYear(nodeMap.get(nodeId)))
        .filter(year => year !== Number.POSITIVE_INFINITY);
    return years.length > 0 ? Math.round(average(years)) : Number.POSITIVE_INFINITY;
}

function groupLabel(group, nodeMap) {
    return group.memberIds
        .map(nodeId => nodeMap.get(nodeId)?.label || '')
        .sort()
        .join(' ');
}

function genderRank(gender) {
    switch (gender?.toLowerCase()) {
        case 'm':
        case 'male':
            return 0;
        case 'f':
        case 'female':
            return 1;
        default:
            return 2;
    }
}

function parseBirthYear(node) {
    if (!node || !node.birth_date) return Number.POSITIVE_INFINITY;
    const year = parseInt(String(node.birth_date).split('-')[0], 10);
    return Number.isFinite(year) ? year : Number.POSITIVE_INFINITY;
}

function extractYear(dateValue) {
    if (!dateValue) return '';
    const match = String(dateValue).match(/\d{3,4}/);
    return match ? match[0] : '';
}

function average(values) {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function truncateLabel(label, maxLength) {
    if (!label || label.length <= maxLength) return label;
    return `${label.slice(0, maxLength - 1)}…`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}

function debounce(callback, wait) {
    let timeoutId;
    return function() {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(callback, wait);
    };
}

document.addEventListener('DOMContentLoaded', function() {
    initGraph();
    loadGraph();
});
