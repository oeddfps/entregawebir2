import assert from 'node:assert/strict';
import test from 'node:test';

import {
  contractQuestion,
  contractVisualizations,
  coverageRows,
  decimalText,
  graphLayout,
  moneyText,
  wordSize,
} from '../src/web/lib/contract-view.mjs';

test('reads both presentation and complete output question shapes', () => {
  const answer = {question_id: 'price_range', status: 'answered', values: {groups: []}};
  assert.equal(contractQuestion({questions: {price_range: answer}}, 'price_range'), answer);
  assert.deepEqual(contractQuestion({data: {question_results: [answer]}}, 'price_range'), answer);
});

test('keeps missing answers distinct from answered empty collections', () => {
  const rows = coverageRows([{questions: {price_range: {status: 'answered', values: {groups: []}}}}, null]);
  assert.deepEqual(rows[0].statuses, ['answered', 'not_available']);
  assert.equal(rows[1].statuses[0], 'not_available');
});

test('formats received decimals without recomputing them', () => {
  assert.equal(decimalText('1200.50'), '1.200,50');
  assert.equal(decimalText(null), '—');
  assert.equal(moneyText('1200.50', 'UYU', '$'), '$\u00a01.200,50\u00a0UYU');
});

test('finds optional visualizations in supported envelopes', () => {
  const visualizations = {graph: {status: 'ready'}};
  assert.equal(contractVisualizations({visualizations}).graph.status, 'ready');
  assert.equal(contractVisualizations({data: {visualizations}}).graph.status, 'ready');
});

test('lays out only graph edges whose endpoints exist', () => {
  const graph = {
    root_refs: ['category'],
    nodes: [
      {ref: 'category', kind: 'Categoria', label: 'Hidratantes'},
      {ref: 'product', kind: 'Producto', label: 'Crema'},
    ],
    edges: [
      {source_ref: 'product', target_ref: 'category', predicate: 'belongs_to'},
      {source_ref: 'missing', target_ref: 'category', predicate: 'invalid'},
    ],
  };
  const layout = graphLayout(graph);
  assert.equal(layout.nodes.length, 2);
  assert.equal(layout.edges.length, 1);
  assert.equal(layout.nodes.find(node => node.ref === 'category').depth, 0);
});

test('word size is bounded and monotonic', () => {
  assert.equal(wordSize(1, 1, 25), 14);
  assert.equal(wordSize(25, 1, 25), 32);
  assert.ok(wordSize(9, 1, 25) > wordSize(4, 1, 25));
});
