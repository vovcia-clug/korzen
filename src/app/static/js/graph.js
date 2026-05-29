// Genealogical family tree renderer — SVG-based, top-down layout.
// Couples are placed side-by-side with a marriage bar; children drop below.

'use strict';

// ─── SVG infrastructure ───────────────────────────────────────────────────────
const SVG_NS = 'http://www.w3.org/2000/svg';

let graphSvg    = null;
let graphLayer  = null;
let edgeLayer   = null;
let nodeLayer   = null;
let guideLayer  = null;

// ─── State ────────────────────────────────────────────────────────────────────
let nodesById      = new Map();   // nodeId → SVG <g> element
let layoutState    = null;
let currentRootId  = null;
let allData        = { nodes: [], edges: [] };
let selectedNodeId = null;
let viewTransform  = { x: 0, y: 0, scale: 1 };
let panState       = null;

// ─── Layout constants ─────────────────────────────────────────────────────────
const NODE_W          = 160;   // card width
const NODE_H          = 80;    // card height
const SPOUSE_GAP      = 0;     // gap between spouses (they share the marriage bar)
const COUPLE_INNER    = 8;     // horizontal gap between two spouse cards
const SIBLING_GAP     = 30;    // horizontal gap between sibling groups
const GEN_GAP         = 130;   // vertical distance between generation baselines
const MARRIAGE_BAR_H  = 22;    // height of the marriage connector bar above children drop
const FIT_PADDING     = 80;
const MIN_SCALE       = 0.08;
const MAX_SCALE       = 3.0;
const CORNER_R        = 6;     // card corner radius
const ACCENT_W        = 6;     // left accent bar width on card

// ─── Translations ─────────────────────────────────────────────────────────────
const t = window.graphTranslations || {
    born: 'Born', died: 'Died', place: 'Place',
    occupation: 'Occupation', source: 'Source',
    doubleClickToSetAsAncestor: 'Double-click to set as ancestor',
    gender: 'Gender', birthDate: 'Birth Date', deathDate: 'Death Date',
    birthPlace: 'Birth Place', relationships: 'Relationships',
    loadingGraphData: 'Loading graph data', errorLoadingGraph: 'Error loading graph'
};

// ═════════════════════════════════════════════════════════════════════════════
// SVG helpers
// ═════════════════════════════════════════════════════════════════════════════

function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
    return el;
}

function svgText(content, attrs) {
    const el = svgEl('text', attrs);
    el.textContent = content;
    return el;
}

// ═════════════════════════════════════════════════════════════════════════════
// Initialisation
// ═════════════════════════════════════════════════════════════════════════════

function initGraph() {
    const container = document.getElementById('graph');
    if (!container) return;

    container.innerHTML = '';
    container.classList.add('custom-graph');

    graphSvg = svgEl('svg', { class: 'graph-svg', role: 'img', 'aria-label': 'Family tree' });

    graphLayer = svgEl('g', { class: 'graph-layer' });
    guideLayer = svgEl('g', { class: 'graph-guides' });
    edgeLayer  = svgEl('g', { class: 'graph-edges' });
    nodeLayer  = svgEl('g', { class: 'graph-nodes' });

    graphLayer.appendChild(guideLayer);
    graphLayer.appendChild(edgeLayer);
    graphLayer.appendChild(nodeLayer);
    graphSvg.appendChild(graphLayer);
    container.appendChild(graphSvg);

    graphSvg.addEventListener('wheel',     handleWheel, { passive: false });
    graphSvg.addEventListener('mousedown', startPan);
    graphSvg.addEventListener('dblclick',  e => { if (e.target === graphSvg) resetView(); });
    window.addEventListener('mousemove',   movePan);
    window.addEventListener('mouseup',     endPan);
    window.addEventListener('resize', debounce(() => { if (layoutState) fitToLayout(false); }, 150));
}

function clearSvg() {
    if (guideLayer) guideLayer.innerHTML = '';
    if (edgeLayer)  edgeLayer.innerHTML  = '';
    if (nodeLayer)  nodeLayer.innerHTML  = '';
    nodesById.clear();
    selectedNodeId = null;
}

// ═════════════════════════════════════════════════════════════════════════════
// Data loading
// ═════════════════════════════════════════════════════════════════════════════

async function loadGraph() {
    const loadingDiv = document.getElementById('loading');
    const errorDiv   = document.getElementById('error');
    const loadBtn    = document.getElementById('loadBtn');

    try {
        loadingDiv.style.display = 'block';
        errorDiv.style.display   = 'none';
        loadBtn.disabled         = true;

        const limit = document.getElementById('limitInput').value;
        const depth = document.getElementById('depthInput').value;
        let url = `/api/graph/data?limit=${encodeURIComponent(limit)}&depth=${encodeURIComponent(depth)}`;
        if (currentRootId) url += `&root_id=${encodeURIComponent(currentRootId)}`;

        const response = await fetch(url);
        const data     = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to load graph data');

        allData = data;
        renderGraph(data);
        document.getElementById('nodeCount').textContent = data.count || 0;
    } catch (err) {
        console.error('Error loading graph:', err);
        const errorDiv = document.getElementById('error');
        errorDiv.textContent    = `Error: ${err.message}`;
        errorDiv.style.display  = 'block';
        clearSvg();
    } finally {
        loadingDiv.style.display = 'none';
        loadBtn.disabled         = false;
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Render pipeline
// ═════════════════════════════════════════════════════════════════════════════

function renderGraph(data) {
    if (!graphSvg) initGraph();
    clearSvg();

    const { nodes, edges } = filterData(data);
    layoutState = buildLayout(nodes, edges);

    drawGenerationBands(layoutState);
    drawConnectors(layoutState);
    drawCards(layoutState);

    applyTransform();
    setTimeout(() => fitToLayout(true), 50);
}

// ─── Filter hidden edges / source nodes ──────────────────────────────────────

function filterData(data) {
    const hideSource    = document.getElementById('hideSourceEdges')?.checked;
    const sourceNodeIds = new Set();

    (data.edges || []).forEach(e => {
        if (e.type !== 'FROM_SOURCE') return;
        const fn = (data.nodes || []).find(n => n.id === e.from);
        const tn = (data.nodes || []).find(n => n.id === e.to);
        if (fn && fn.type !== 'Person') sourceNodeIds.add(e.from);
        if (tn && tn.type !== 'Person') sourceNodeIds.add(e.to);
    });

    const nodes = (data.nodes || []).filter(n => !(hideSource && sourceNodeIds.has(n.id)));
    const ids   = new Set(nodes.map(n => n.id));
    const edges = (data.edges || []).filter(e => {
        if (hideSource && e.type === 'FROM_SOURCE') return false;
        return ids.has(e.from) && ids.has(e.to);
    });

    return { nodes, edges };
}

// ═════════════════════════════════════════════════════════════════════════════
// Layout engine
// ═════════════════════════════════════════════════════════════════════════════

/**
 * Returns:
 *   positions  Map<nodeId, {x, y, w, h}>
 *   couples    Array<{id, spouseIds[], childIds[], x, y, midX}>
 *   nodeMap    Map<nodeId, rawNode>
 *   genY       Map<generation, y>
 *   bounds     {minX, maxX, minY, maxY}
 */
function buildLayout(rawNodes, rawEdges) {
    const nodeMap = new Map(rawNodes.map(n => [n.id, n]));

    // ── 1. Build relationship maps ──────────────────────────────────────────
    const spousesOf  = new Map();   // nodeId → Set<nodeId>
    const parentsOf  = new Map();   // nodeId → Set<nodeId>
    const childrenOf = new Map();   // nodeId → Set<nodeId>

    rawNodes.forEach(n => {
        spousesOf.set(n.id,  new Set());
        parentsOf.set(n.id,  new Set());
        childrenOf.set(n.id, new Set());
    });

    rawEdges.forEach(e => {
        if (!spousesOf.has(e.from) || !spousesOf.has(e.to)) return;
        if (e.type === 'MARRIED_TO') {
            spousesOf.get(e.from).add(e.to);
            spousesOf.get(e.to).add(e.from);
        } else if (e.type === 'PARENT_OF') {
            childrenOf.get(e.from).add(e.to);
            parentsOf.get(e.to).add(e.from);
        }
    });

    // ── 2. Build couple units ───────────────────────────────────────────────
    // A "couple" is a set of spouses that share children (or a lone person).
    // We group by connected-component of the MARRIED_TO graph.
    const visited = new Set();
    const couples = [];           // [{id, memberIds, childIds, parentCoupleIds, childCoupleIds, level, x, y}]
    const coupleOfNode = new Map(); // nodeId → coupleIndex

    rawNodes.forEach(n => {
        if (visited.has(n.id)) return;
        const members = [];
        const queue   = [n.id];
        visited.add(n.id);
        while (queue.length) {
            const id = queue.shift();
            members.push(id);
            spousesOf.get(id).forEach(sid => {
                if (!visited.has(sid)) { visited.add(sid); queue.push(sid); }
            });
        }
        const idx = couples.length;
        // Collect all children of any member
        const childSet = new Set();
        members.forEach(mid => childrenOf.get(mid).forEach(cid => childSet.add(cid)));

        couples.push({
            id: idx,
            memberIds: members,
            childIds:  [...childSet],
            parentCoupleIds: new Set(),
            childCoupleIds:  new Set(),
            level: 0,
            x: 0,
            y: 0,
            width: coupleWidth(members)
        });
        members.forEach(mid => coupleOfNode.set(mid, idx));
    });

    // ── 3. Wire couple parent/child relationships ───────────────────────────
    couples.forEach(c => {
        c.childIds.forEach(cid => {
            const childCoupleIdx = coupleOfNode.get(cid);
            if (childCoupleIdx !== undefined && childCoupleIdx !== c.id) {
                c.childCoupleIds.add(childCoupleIdx);
                couples[childCoupleIdx].parentCoupleIds.add(c.id);
            }
        });
    });

    // ── 4. Assign generation levels (topological) ──────────────────────────
    let changed = true;
    let iters   = 0;
    while (changed && iters++ < couples.length * 4 + 20) {
        changed = false;
        couples.forEach(c => {
            let want = 0;
            c.parentCoupleIds.forEach(pid => { want = Math.max(want, couples[pid].level + 1); });
            if (want > c.level) { c.level = want; changed = true; }
        });
    }

    // ── 5. Assign X positions ───────────────────────────────────────────────
    const byLevel = new Map();
    couples.forEach(c => {
        if (!byLevel.has(c.level)) byLevel.set(c.level, []);
        byLevel.get(c.level).push(c);
    });

    const sortedLevels = [...byLevel.keys()].sort((a, b) => a - b);

    // Initial spread per level
    sortedLevels.forEach(lv => {
        const row = byLevel.get(lv);
        row.sort((a, b) => avgParentX(a, couples) - avgParentX(b, couples) || compareCouples(a, b, nodeMap));
        spreadRow(row);
    });

    // Iterative refinement: pull parents over children, then re-spread
    for (let pass = 0; pass < 4; pass++) {
        // Pull parents toward their children's centroid
        for (let li = sortedLevels.length - 2; li >= 0; li--) {
            byLevel.get(sortedLevels[li]).forEach(c => {
                const xs = [...c.childCoupleIds].map(ci => couples[ci].x).filter(isFinite);
                if (xs.length) c.x = avg(xs);
            });
            normaliseRow(byLevel.get(sortedLevels[li]));
        }
        // Re-sort and spread each level
        sortedLevels.forEach(lv => {
            const row = byLevel.get(lv);
            row.sort((a, b) => avgParentX(a, couples) - avgParentX(b, couples) || a.x - b.x);
            normaliseRow(row);
        });
    }

    // ── 6. Assign Y positions ───────────────────────────────────────────────
    const genY = new Map();
    couples.forEach(c => {
        c.y = c.level * GEN_GAP;
        genY.set(c.level, c.y);
    });

    // ── 7. Compute per-node positions ───────────────────────────────────────
    const positions = new Map();

    couples.forEach(c => {
        const members = c.memberIds
            .map(id => nodeMap.get(id))
            .filter(Boolean)
            .sort(spouseOrder);

        const totalW = members.length * NODE_W + Math.max(0, members.length - 1) * COUPLE_INNER;
        let cursor   = c.x - totalW / 2;

        members.forEach(n => {
            positions.set(n.id, {
                x: cursor + NODE_W / 2,
                y: c.y,
                w: NODE_W,
                h: NODE_H,
                coupleId: c.id
            });
            cursor += NODE_W + COUPLE_INNER;
        });

        // Store midpoint for connector drawing
        c.midX = c.x;
        c.midY = c.y;
    });

    const bounds = calcBounds(positions);

    return { positions, couples, coupleOfNode, nodeMap, spousesOf, parentsOf, childrenOf, genY, bounds, rawEdges };
}

// ─── Layout helpers ───────────────────────────────────────────────────────────

function coupleWidth(memberIds) {
    return memberIds.length * NODE_W + Math.max(0, memberIds.length - 1) * COUPLE_INNER;
}

function avgParentX(couple, couples) {
    const xs = [...couple.parentCoupleIds].map(pi => couples[pi].x).filter(isFinite);
    return xs.length ? avg(xs) : Infinity;
}

function compareCouples(a, b, nodeMap) {
    const ya = minBirthYear(a, nodeMap);
    const yb = minBirthYear(b, nodeMap);
    if (ya !== yb) return ya - yb;
    return coupleLabel(a, nodeMap).localeCompare(coupleLabel(b, nodeMap));
}

function minBirthYear(couple, nodeMap) {
    const years = couple.memberIds.map(id => parseBirthYear(nodeMap.get(id))).filter(y => isFinite(y));
    return years.length ? Math.min(...years) : Infinity;
}

function coupleLabel(couple, nodeMap) {
    return couple.memberIds.map(id => nodeMap.get(id)?.label || '').sort().join(' ');
}

function spreadRow(row) {
    const total = row.reduce((s, c) => s + c.width, 0) + Math.max(0, row.length - 1) * SIBLING_GAP;
    let cursor  = -total / 2;
    row.forEach(c => {
        c.x = cursor + c.width / 2;
        cursor += c.width + SIBLING_GAP;
    });
}

function normaliseRow(row) {
    if (!row || !row.length) return;
    row.sort((a, b) => a.x - b.x);
    for (let i = 1; i < row.length; i++) {
        const prev = row[i - 1];
        const cur  = row[i];
        const minX = prev.x + prev.width / 2 + SIBLING_GAP + cur.width / 2;
        if (cur.x < minX) cur.x = minX;
    }
    // Re-centre
    const minX = row[0].x - row[0].width / 2;
    const last = row[row.length - 1];
    const maxX = last.x + last.width / 2;
    const off  = (minX + maxX) / 2;
    row.forEach(c => { c.x -= off; });
}

function spouseOrder(a, b) {
    const ra = genderRank(a.gender), rb = genderRank(b.gender);
    if (ra !== rb) return ra - rb;
    const ya = parseBirthYear(a), yb = parseBirthYear(b);
    if (ya !== yb) return ya - yb;
    return (a.label || '').localeCompare(b.label || '');
}

function genderRank(g) {
    switch (g?.toLowerCase()) {
        case 'm': case 'male':   return 0;
        case 'f': case 'female': return 1;
        default:                 return 2;
    }
}

function parseBirthYear(node) {
    if (!node?.birth_date) return Infinity;
    const y = parseInt(String(node.birth_date).split('-')[0], 10);
    return isFinite(y) ? y : Infinity;
}

function calcBounds(positions) {
    const nodes = [...positions.values()];
    if (!nodes.length) return { minX: -200, maxX: 200, minY: -100, maxY: 100 };
    return nodes.reduce((b, n) => ({
        minX: Math.min(b.minX, n.x - n.w / 2),
        maxX: Math.max(b.maxX, n.x + n.w / 2),
        minY: Math.min(b.minY, n.y - n.h / 2),
        maxY: Math.max(b.maxY, n.y + n.h / 2)
    }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity });
}

// ═════════════════════════════════════════════════════════════════════════════
// Drawing — generation bands
// ═════════════════════════════════════════════════════════════════════════════

function drawGenerationBands(state) {
    if (!state?.bounds) return;

    const left  = state.bounds.minX - 200;
    const right = state.bounds.maxX + 200;

    const levels = [...new Set(state.couples.map(c => c.level))].sort((a, b) => a - b);

    levels.forEach((lv, idx) => {
        const y = lv * GEN_GAP - NODE_H / 2 - 10;
        const h = GEN_GAP;

        // Alternating subtle band
        if (idx % 2 === 0) {
            const band = svgEl('rect', {
                class: 'gen-band',
                x: left, y,
                width: right - left, height: h
            });
            guideLayer.appendChild(band);
        }

        // Generation label
        const label = svgEl('text', {
            class: 'gen-label',
            x: left + 8,
            y: y + 18
        });
        label.textContent = `Gen ${lv + 1}`;
        guideLayer.appendChild(label);
    });
}

// ═════════════════════════════════════════════════════════════════════════════
// Drawing — connectors
// ═════════════════════════════════════════════════════════════════════════════

function drawConnectors(state) {
    const { couples, positions, spousesOf, nodeMap } = state;
    const drawnMarriages = new Set();

    couples.forEach(couple => {
        // ── Marriage bar between spouses ────────────────────────────────────
        if (couple.memberIds.length >= 2) {
            const sorted = couple.memberIds
                .map(id => positions.get(id))
                .filter(Boolean)
                .sort((a, b) => a.x - b.x);

            if (sorted.length >= 2) {
                const leftPos  = sorted[0];
                const rightPos = sorted[sorted.length - 1];
                const barY     = leftPos.y;   // centre of cards

                // Horizontal marriage line between the two cards
                const line = svgEl('line', {
                    class: 'marriage-bar',
                    x1: leftPos.x + NODE_W / 2,
                    y1: barY,
                    x2: rightPos.x - NODE_W / 2,
                    y2: barY
                });
                edgeLayer.appendChild(line);

                // Marriage ring symbol at midpoint
                const midX = (leftPos.x + rightPos.x) / 2;
                const ring = svgEl('circle', {
                    class: 'marriage-ring',
                    cx: midX,
                    cy: barY,
                    r: 7
                });
                edgeLayer.appendChild(ring);
            }
        }

        // ── Parent → children connector ─────────────────────────────────────
        if (couple.childIds.length === 0) return;

        const memberPositions = couple.memberIds.map(id => positions.get(id)).filter(Boolean);
        if (!memberPositions.length) return;

        const dropX  = avg(memberPositions.map(p => p.x));
        const dropY  = memberPositions[0].y + NODE_H / 2;   // bottom of parent cards
        const juncY  = dropY + MARRIAGE_BAR_H;              // horizontal junction bar Y

        // Vertical drop from couple midpoint to junction
        const stem = svgEl('line', {
            class: 'family-stem',
            x1: dropX, y1: dropY,
            x2: dropX, y2: juncY
        });
        edgeLayer.appendChild(stem);

        // Collect child positions
        const childPositions = couple.childIds
            .map(cid => positions.get(cid))
            .filter(Boolean);

        if (!childPositions.length) return;

        const childXs = childPositions.map(p => p.x);
        const minCX   = Math.min(...childXs);
        const maxCX   = Math.max(...childXs);

        // Horizontal collector bar
        if (childPositions.length > 1) {
            const bar = svgEl('line', {
                class: 'family-bar',
                x1: minCX, y1: juncY,
                x2: maxCX, y2: juncY
            });
            edgeLayer.appendChild(bar);
        }

        // Vertical drops to each child
        childPositions.forEach(cp => {
            const childTopY = cp.y - NODE_H / 2;
            const path = svgEl('path', {
                class: 'child-drop',
                d: `M ${cp.x} ${juncY} V ${childTopY}`
            });
            edgeLayer.appendChild(path);
        });

        // If only one child, extend stem directly
        if (childPositions.length === 1) {
            const cp = childPositions[0];
            // Adjust stem to go to child's x if offset
            if (Math.abs(cp.x - dropX) > 2) {
                const elbow = svgEl('path', {
                    class: 'family-stem',
                    d: `M ${dropX} ${juncY} H ${cp.x}`
                });
                edgeLayer.appendChild(elbow);
            }
        }
    });

    // ── Non-family edges (source, generic) ──────────────────────────────────
    state.rawEdges.forEach(e => {
        if (e.type === 'MARRIED_TO' || e.type === 'PARENT_OF') return;
        const fp = positions.get(e.from);
        const tp = positions.get(e.to);
        if (!fp || !tp) return;

        if (e.type === 'FROM_SOURCE') {
            const path = svgEl('path', {
                class: 'source-edge',
                d: elbowPath(fp, tp)
            });
            edgeLayer.appendChild(path);
        } else {
            const path = svgEl('path', {
                class: 'generic-edge',
                d: elbowPath(fp, tp)
            });
            edgeLayer.appendChild(path);
        }
    });
}

function elbowPath(fp, tp) {
    const fy  = fp.y + (fp.y <= tp.y ?  NODE_H / 2 : -NODE_H / 2);
    const ty  = tp.y + (fp.y <= tp.y ? -NODE_H / 2 :  NODE_H / 2);
    const mid = (fy + ty) / 2;
    return `M ${fp.x} ${fy} V ${mid} H ${tp.x} V ${ty}`;
}

// ═════════════════════════════════════════════════════════════════════════════
// Drawing — person cards
// ═════════════════════════════════════════════════════════════════════════════

function drawCards(state) {
    state.positions.forEach((pos, nodeId) => {
        const node  = state.nodeMap.get(nodeId);
        if (!node) return;

        const isRoot   = nodeId === currentRootId;
        const colors   = cardColors(node);
        const lx       = pos.x - NODE_W / 2;
        const ty       = pos.y - NODE_H / 2;

        const g = svgEl('g', {
            class:      `graph-node${isRoot ? ' root-node' : ''}`,
            transform:  `translate(${lx}, ${ty})`,
            tabindex:   '0',
            role:       'button',
            'data-node-id': nodeId
        });

        // ── Card shadow / background ─────────────────────────────────────────
        const shadow = svgEl('rect', {
            class: 'card-shadow',
            x: 3, y: 4,
            width: NODE_W, height: NODE_H,
            rx: CORNER_R, ry: CORNER_R
        });
        g.appendChild(shadow);

        // ── Card body ────────────────────────────────────────────────────────
        const body = svgEl('rect', {
            class: 'card-body',
            x: 0, y: 0,
            width: NODE_W, height: NODE_H,
            rx: CORNER_R, ry: CORNER_R,
            fill: colors.bg,
            stroke: isRoot ? '#e6a817' : colors.border,
            'stroke-width': isRoot ? 3 : 1.5
        });
        g.appendChild(body);

        // ── Left accent bar ──────────────────────────────────────────────────
        const accent = svgEl('rect', {
            class: 'card-accent',
            x: 0, y: 0,
            width: ACCENT_W, height: NODE_H,
            rx: CORNER_R, ry: CORNER_R,
            fill: colors.accent
        });
        g.appendChild(accent);

        // Clip the right side of accent to be square
        const accentClip = svgEl('rect', {
            x: ACCENT_W / 2, y: 0,
            width: ACCENT_W / 2, height: NODE_H,
            fill: colors.accent
        });
        g.appendChild(accentClip);

        // ── Root star ────────────────────────────────────────────────────────
        if (isRoot) {
            const star = svgEl('text', {
                class: 'card-root-star',
                x: NODE_W - 10, y: 14,
                'text-anchor': 'middle',
                'font-size': '12'
            });
            star.textContent = '★';
            g.appendChild(star);
        }

        // ── Name ─────────────────────────────────────────────────────────────
        const name     = node.label || 'Unknown';
        const nameText = svgEl('text', {
            class: 'card-name',
            x: ACCENT_W + 8,
            y: NODE_H / 2 - 10,
            'dominant-baseline': 'middle'
        });
        nameText.textContent = truncate(name, 20);
        g.appendChild(nameText);

        // ── Years ────────────────────────────────────────────────────────────
        if (node.type === 'Person') {
            const by = extractYear(node.birth_date);
            const dy = extractYear(node.death_date);
            if (by || dy) {
                const years = svgEl('text', {
                    class: 'card-years',
                    x: ACCENT_W + 8,
                    y: NODE_H / 2 + 10,
                    'dominant-baseline': 'middle'
                });
                years.textContent = `${by || '?'} – ${dy || ''}`;
                g.appendChild(years);
            }

            // Birth place (truncated)
            if (node.birth_place) {
                const place = svgEl('text', {
                    class: 'card-place',
                    x: ACCENT_W + 8,
                    y: NODE_H - 10,
                    'dominant-baseline': 'middle'
                });
                place.textContent = truncate(node.birth_place, 22);
                g.appendChild(place);
            }
        } else if (node.type) {
            const typeLabel = svgEl('text', {
                class: 'card-years',
                x: ACCENT_W + 8,
                y: NODE_H / 2 + 10,
                'dominant-baseline': 'middle'
            });
            typeLabel.textContent = node.type;
            g.appendChild(typeLabel);
        }

        // ── Tooltip ──────────────────────────────────────────────────────────
        const title = svgEl('title', {});
        title.textContent = tooltipText(node);
        g.appendChild(title);

        // ── Events ───────────────────────────────────────────────────────────
        g.addEventListener('click', e => { e.stopPropagation(); selectNode(nodeId); showNodeInfo(nodeId); });
        g.addEventListener('dblclick', e => { e.stopPropagation(); setAsRoot(nodeId); });
        g.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectNode(nodeId); showNodeInfo(nodeId); }
        });

        nodeLayer.appendChild(g);
        nodesById.set(nodeId, g);
    });
}

// ─── Card colour scheme ───────────────────────────────────────────────────────

function cardColors(node) {
    if (node.type !== 'Person') {
        return { bg: '#fff8e1', border: '#f9a825', accent: '#f9a825' };
    }
    switch (node.gender?.toLowerCase()) {
        case 'm': case 'male':
            return { bg: '#f0f7ff', border: '#90bce8', accent: '#1565c0' };
        case 'f': case 'female':
            return { bg: '#fff0f5', border: '#e8a0b8', accent: '#ad1457' };
        default:
            return { bg: '#f7f7f7', border: '#bdbdbd', accent: '#757575' };
    }
}

// ═════════════════════════════════════════════════════════════════════════════
// Selection & info panel
// ═════════════════════════════════════════════════════════════════════════════

function selectNode(nodeId) {
    if (selectedNodeId && nodesById.has(selectedNodeId)) {
        nodesById.get(selectedNodeId).classList.remove('selected');
    }
    selectedNodeId = nodeId;
    if (nodesById.has(nodeId)) nodesById.get(nodeId).classList.add('selected');
}

function showNodeInfo(nodeId) {
    const node = allData.nodes.find(n => n.id === nodeId);
    if (!node) return;

    const panel   = document.getElementById('infoPanel');
    const title   = document.getElementById('infoTitle');
    const content = document.getElementById('infoContent');

    title.textContent = node.label || 'Unknown';

    let html = '<div class="info-details">';
    if (node.gender)      html += `<p><strong>${t.gender}:</strong> ${esc(node.gender)}</p>`;
    if (node.birth_date)  html += `<p><strong>${t.birthDate}:</strong> ${esc(node.birth_date)}</p>`;
    if (node.death_date)  html += `<p><strong>${t.deathDate}:</strong> ${esc(node.death_date)}</p>`;
    if (node.birth_place) html += `<p><strong>${t.birthPlace}:</strong> ${esc(node.birth_place)}</p>`;
    if (node.occupation)  html += `<p><strong>${t.occupation}:</strong> ${esc(node.occupation)}</p>`;
    if (node.source)      html += `<p><strong>${t.source}:</strong> ${esc(node.source)}</p>`;

    const rels = allData.edges.filter(e => e.from === nodeId || e.to === nodeId);
    if (rels.length) {
        html += `<p><strong>${t.relationships}:</strong></p><ul class="relationships-list">`;
        rels.forEach(rel => {
            const otherId   = rel.from === nodeId ? rel.to : rel.from;
            const otherNode = allData.nodes.find(n => n.id === otherId);
            if (otherNode) {
                const dir = rel.from === nodeId ? '→' : '←';
                html += `<li>${dir} ${esc(rel.type)}: <span class="person-link" data-person-id="${escAttr(otherId)}">${esc(otherNode.label)}</span></li>`;
            }
        });
        html += '</ul>';
    }
    html += '</div>';

    content.innerHTML = html;
    panel.classList.add('active');

    content.querySelectorAll('.person-link').forEach(link => {
        link.addEventListener('click', function() { handlePersonClick(this.getAttribute('data-person-id')); });
    });
}

function handlePersonClick(personId) {
    if (nodesById.has(personId)) focusNode(personId, 1.4);
    showNodeInfo(personId);
}

function closeInfo() {
    document.getElementById('infoPanel').classList.remove('active');
}

// ═════════════════════════════════════════════════════════════════════════════
// Root / ancestor controls
// ═════════════════════════════════════════════════════════════════════════════

function setAsRoot(nodeId) {
    const node = allData.nodes.find(n => n.id === nodeId);
    if (!node || node.type !== 'Person') return;
    currentRootId = nodeId;
    document.getElementById('rootName').textContent    = node.label;
    document.getElementById('rootIndicator').style.display = 'flex';
    document.getElementById('clearRootBtn').style.display  = 'inline-block';
    loadGraph();
}

function clearRoot() {
    currentRootId = null;
    document.getElementById('rootIndicator').style.display = 'none';
    document.getElementById('clearRootBtn').style.display  = 'none';
    loadGraph();
}

function toggleSourceEdges() {
    if (allData?.nodes?.length) renderGraph(allData);
}

// ═════════════════════════════════════════════════════════════════════════════
// Viewport — pan / zoom / fit
// ═════════════════════════════════════════════════════════════════════════════

function applyTransform() {
    if (!graphLayer) return;
    graphLayer.setAttribute('transform', `translate(${viewTransform.x},${viewTransform.y}) scale(${viewTransform.scale})`);
}

function fitToLayout(animate) {
    if (!layoutState?.bounds) return;
    const container = document.getElementById('graph');
    if (!container || !container.clientWidth) return;

    const { minX, maxX, minY, maxY } = layoutState.bounds;
    const w     = Math.max(1, maxX - minX + FIT_PADDING * 2);
    const h     = Math.max(1, maxY - minY + FIT_PADDING * 2);
    const scale = clamp(Math.min(container.clientWidth / w, container.clientHeight / h), MIN_SCALE, MAX_SCALE);
    const cx    = (minX + maxX) / 2;
    const cy    = (minY + maxY) / 2;

    viewTransform = {
        scale,
        x: container.clientWidth  / 2 - cx * scale,
        y: container.clientHeight / 2 - cy * scale
    };

    if (animate) {
        graphLayer.classList.add('graph-layer-animated');
        setTimeout(() => graphLayer?.classList.remove('graph-layer-animated'), 380);
    }
    applyTransform();
}

function focusNode(nodeId, scale) {
    if (!layoutState?.positions.has(nodeId)) return;
    const container = document.getElementById('graph');
    const pos       = layoutState.positions.get(nodeId);
    const s         = clamp(scale || Math.max(viewTransform.scale, 1.2), MIN_SCALE, MAX_SCALE);
    viewTransform   = { scale: s, x: container.clientWidth / 2 - pos.x * s, y: container.clientHeight / 2 - pos.y * s };
    applyTransform();
    selectNode(nodeId);
}

function resetView() { fitToLayout(true); }

function handleWheel(e) {
    if (!layoutState) return;
    e.preventDefault();
    const rect   = graphSvg.getBoundingClientRect();
    const mx     = e.clientX - rect.left;
    const my     = e.clientY - rect.top;
    const wx     = (mx - viewTransform.x) / viewTransform.scale;
    const wy     = (my - viewTransform.y) / viewTransform.scale;
    const factor = e.deltaY < 0 ? 1.12 : 0.88;
    const ns     = clamp(viewTransform.scale * factor, MIN_SCALE, MAX_SCALE);
    viewTransform = { scale: ns, x: mx - wx * ns, y: my - wy * ns };
    applyTransform();
}

function startPan(e) {
    if (e.button !== 0 || e.target.closest('.graph-node')) return;
    panState = { startX: e.clientX, startY: e.clientY, tx: viewTransform.x, ty: viewTransform.y };
    graphSvg.classList.add('panning');
}

function movePan(e) {
    if (!panState) return;
    viewTransform.x = panState.tx + e.clientX - panState.startX;
    viewTransform.y = panState.ty + e.clientY - panState.startY;
    applyTransform();
}

function endPan() {
    if (!panState) return;
    panState = null;
    graphSvg?.classList.remove('panning');
}

// ═════════════════════════════════════════════════════════════════════════════
// Utilities
// ═════════════════════════════════════════════════════════════════════════════

function avg(arr) { return arr.reduce((s, v) => s + v, 0) / arr.length; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function truncate(s, n) { return s && s.length > n ? s.slice(0, n - 1) + '…' : s; }

function extractYear(d) {
    if (!d) return '';
    const m = String(d).match(/\d{3,4}/);
    return m ? m[0] : '';
}

function tooltipText(node) {
    const parts = [node.label || 'Unknown'];
    if (node.birth_date)  parts.push(`${t.born}: ${node.birth_date}`);
    if (node.death_date)  parts.push(`${t.died}: ${node.death_date}`);
    if (node.birth_place) parts.push(`${t.place}: ${node.birth_place}`);
    if (node.occupation)  parts.push(`${t.occupation}: ${node.occupation}`);
    parts.push(t.doubleClickToSetAsAncestor);
    return parts.join('\n');
}

function esc(v) {
    return String(v ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function escAttr(v) { return esc(v).replace(/`/g, '&#096;'); }

function debounce(fn, ms) {
    let t;
    return function() { clearTimeout(t); t = setTimeout(fn, ms); };
}

// ═════════════════════════════════════════════════════════════════════════════
// Bootstrap
// ═════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initGraph();
    loadGraph();
});
