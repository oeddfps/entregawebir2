export const QUESTION_DEFINITIONS = [
  {id: 'price_range', label: 'Rango de precios', short: 'Precios'},
  {id: 'visual_presentation', label: 'Presentación visual', short: 'Imágenes'},
  {id: 'keywords', label: 'Términos y temas', short: 'Términos'},
  {id: 'category_opinions', label: 'Opiniones de categoría', short: 'Opiniones'},
];

export const asArray = value => Array.isArray(value) ? value : [];

export function contractQuestions(payload) {
  if (!payload || typeof payload !== 'object') return {};
  const direct = payload.questions || payload.presentation?.questions || payload.data?.questions;
  if (direct && !Array.isArray(direct) && typeof direct === 'object') return direct;
  const rows = asArray(payload.data?.question_results || payload.question_results || direct);
  return Object.fromEntries(rows.filter(row => row?.question_id).map(row => [row.question_id, row]));
}

export function contractVisualizations(payload) {
  if (!payload || typeof payload !== 'object') return {};
  return payload.visualizations || payload.presentation?.visualizations || payload.data?.visualizations || {};
}

export function contractQuestion(payload, questionId) {
  return contractQuestions(payload)[questionId] || null;
}

export function questionStatus(payload, questionId) {
  return contractQuestion(payload, questionId)?.status || 'not_available';
}

export function coverageRows(payloads) {
  return QUESTION_DEFINITIONS.map(question => ({
    ...question,
    statuses: asArray(payloads).map(payload => questionStatus(payload, question.id)),
  }));
}

export function decimalText(value) {
  if (value === null || value === undefined || value === '') return '—';
  const raw = String(value).trim();
  const match = raw.match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match) return raw;
  const [, sign, integer, fraction] = match;
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return sign + grouped + (fraction === undefined ? '' : `,${fraction}`);
}

export function moneyText(value, currency, symbol) {
  if (value === null || value === undefined || value === '') return '—';
  const amount = decimalText(value);
  return `${symbol ? `${symbol}\u00a0` : ''}${amount}${currency ? `\u00a0${currency}` : ''}`;
}

export function valueLabel(value) {
  if (value === null || value === undefined || value === '') return 'No declarado';
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  if (Array.isArray(value)) return value.length ? value.map(valueLabel).join(' · ') : 'Sin condiciones adicionales';
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([key, item]) => `${key.replaceAll('_', ' ')}: ${valueLabel(item)}`).join(' · ') : 'Sin condiciones adicionales';
  }
  return String(value);
}

export function statusCounts(payloads) {
  const counts = {answered: 0, partial: 0, not_answerable: 0, not_available: 0};
  for (const row of coverageRows(payloads)) {
    for (const status of row.statuses) counts[status] = (counts[status] || 0) + 1;
  }
  return counts;
}

export function wordSize(frequency, minimum, maximum) {
  const low = Number(minimum) || 0;
  const high = Math.max(low + 1, Number(maximum) || 1);
  const value = Math.max(low, Number(frequency) || 0);
  const ratio = (Math.sqrt(value) - Math.sqrt(low)) / (Math.sqrt(high) - Math.sqrt(low));
  return Math.round(14 + Math.max(0, Math.min(1, ratio)) * 18);
}

export function graphLayout(graph, width = 760, height = 420) {
  const nodes = asArray(graph?.nodes);
  const edges = asArray(graph?.edges);
  if (!nodes.length) return {nodes: [], edges: []};
  const byRef = new Map(nodes.map(node => [node.ref, node]));
  const adjacency = new Map(nodes.map(node => [node.ref, []]));
  for (const edge of edges) {
    if (!byRef.has(edge.source_ref) || !byRef.has(edge.target_ref)) continue;
    adjacency.get(edge.source_ref).push(edge.target_ref);
    adjacency.get(edge.target_ref).push(edge.source_ref);
  }
  const roots = asArray(graph.root_refs).filter(ref => byRef.has(ref));
  const queue = (roots.length ? roots : [nodes[0].ref]).map(ref => [ref, 0]);
  const depths = new Map();
  for (const [ref, depth] of queue) {
    if (depths.has(ref)) continue;
    depths.set(ref, depth);
    for (const next of adjacency.get(ref) || []) if (!depths.has(next)) queue.push([next, depth + 1]);
  }
  let fallbackDepth = Math.max(0, ...depths.values()) + 1;
  for (const node of nodes) if (!depths.has(node.ref)) depths.set(node.ref, fallbackDepth);
  const rings = new Map();
  for (const node of nodes) {
    const depth = depths.get(node.ref);
    if (!rings.has(depth)) rings.set(depth, []);
    rings.get(depth).push(node);
  }
  const centerX = width / 2, centerY = height / 2;
  const maxDepth = Math.max(1, ...rings.keys());
  const positioned = [];
  for (const [depth, ringNodes] of [...rings.entries()].sort(([a], [b]) => a - b)) {
    const radius = depth === 0 ? Math.min(28, ringNodes.length * 12) : Math.min(width, height) * .41 * depth / maxDepth;
    ringNodes.forEach((node, index) => {
      const angle = depth === 0 ? -Math.PI / 2 + index * Math.PI * 2 / ringNodes.length : -Math.PI / 2 + index * Math.PI * 2 / ringNodes.length + depth * .35;
      positioned.push({...node, depth, x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius});
    });
  }
  const positions = new Map(positioned.map(node => [node.ref, node]));
  return {
    nodes: positioned,
    edges: edges.filter(edge => positions.has(edge.source_ref) && positions.has(edge.target_ref)).map(edge => ({...edge, source: positions.get(edge.source_ref), target: positions.get(edge.target_ref)})),
  };
}
