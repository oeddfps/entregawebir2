import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildBrandGallery,
  buildBrandPriceSeries,
  buildCompetitiveProducts,
  buildMarketPresence,
  declaredPreferences,
  productPriceGroups,
} from '../src/web/lib/brand-competitiveness.mjs';

const sources = [{label: 'Loja A', url: 'https://a.example/catalogo'}, {label: 'Loja B', url: 'https://b.example/lista'}];

function result(index, {gtin = '789100000001', preference = 'featured', brand = 'Marca Clara', currency = 'BRL'} = {}) {
  const variant = `variant-${index}`;
  return {
    products: [{
      entity_id: `product-${index}`, identity_status: 'resolved', name: `Produto ${index + 1}`, brand, gtin,
      variant_refs: [variant], field_assertion_refs: {gtin: [`assertion-gtin-${index}`]}, ratings: [{score: String(4 + index / 10), scale: {min: 0, max: 5}}],
      images: [{usage_ref: `use-${index}`, visibility: 'visible', order: 1, resources: [`https://${index}.example/product.jpg`], function_status: 'declared', functions: preference ? [preference] : []}],
    }],
    questions: {price_range: {status: 'answered', values: {groups: [{variant_ref: variant, currency, conditions: {}, comparison_time: [`sample-${index}`], price_observed: String(100 + index * 20), average: String(100 + index * 20)}]}}},
  };
}

test('groups product cards by declared brand and keeps source context', () => {
  const gallery = buildBrandGallery([result(0), result(1)], sources);
  assert.equal(gallery.length, 1);
  assert.equal(gallery[0].brand, 'Marca Clara');
  assert.equal(gallery[0].products.length, 2);
  assert.deepEqual(gallery[0].sources.map(source => source.label), ['Loja A', 'Loja B']);
  assert.equal(gallery[0].products[0].priceGroups[0].price_observed, '100');
});

test('reads products and visual uses from the complete data.question_results envelope', () => {
  const projected = result(0);
  const product = projected.products[0];
  const complete = {data: {
    products: [{...product, images: undefined, ratings: undefined}],
    question_results: [
      {question_id: 'price_range', ...projected.questions.price_range},
      {question_id: 'visual_presentation', status: 'answered', values: {appearances: [{subject_refs: [product.entity_id], image_uses: product.images}]}},
    ],
  }};
  const gallery = buildBrandGallery([complete], sources);
  assert.equal(gallery[0].products[0].image, product.images[0].resources[0]);
  assert.equal(gallery[0].products[0].rating, null);
  assert.equal(gallery[0].products[0].priceGroups[0].price_observed, '100');
  assert.deepEqual(gallery[0].products[0].preferences.map(item => item.code), ['featured']);
});

test('joins price groups only through declared variant references', () => {
  const payload = result(0);
  assert.equal(productPriceGroups(payload, payload.products[0]).length, 1);
  assert.equal(productPriceGroups(payload, {...payload.products[0], variant_refs: ['other']}).length, 0);
});

test('recognizes only declared preference functions on visible image uses', () => {
  const product = result(0).products[0];
  assert.deepEqual(declaredPreferences(product).map(item => item.code), ['featured']);
  assert.deepEqual(declaredPreferences({...product, images: [{...product.images[0], function_status: 'not_interpreted'}]}), []);
  assert.deepEqual(declaredPreferences({...product, images: [{...product.images[0], visibility: 'hidden'}]}), []);
});

test('matches competitors only by resolved exact GTIN and requires multiple sources', () => {
  const matches = buildCompetitiveProducts([result(0), result(1)], sources);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].designation, 'Produto de Alto Valor');
  assert.equal(matches[0].sourceCount, 2);
  assert.deepEqual(matches[0].assertionRefs, ['assertion-gtin-0', 'assertion-gtin-1']);
  const unresolved = result(1);
  unresolved.products[0].identity_status = 'provisional';
  assert.equal(buildCompetitiveProducts([result(0), unresolved], sources).length, 0);
  assert.equal(buildCompetitiveProducts([result(0), result(1, {gtin: 'different'})], sources).length, 0);
});

test('uses the category leader tag only when multiple sources declare it', () => {
  const matches = buildCompetitiveProducts([result(0, {preference: 'category_leader'}), result(1, {preference: 'category_leader'})], sources);
  assert.equal(matches[0].designation, 'Líder da Categoria');
});

test('keeps brand price points separate and never combines currencies or groups', () => {
  const series = buildBrandPriceSeries([result(0), result(1)], sources);
  assert.equal(series.length, 1);
  assert.deepEqual(series[0].points.map(point => point.raw), ['100', '120']);
  assert.deepEqual(series[0].points.map(point => point.source.label), ['Loja A', 'Loja B']);
  assert.equal(buildBrandPriceSeries([result(0), result(1, {currency: 'USD'})], sources).length, 0);
});

test('plots contractual minimum and maximum as a received interval without inventing an average', () => {
  const first = result(0);
  const second = result(1);
  for (const [payload, minimum, maximum] of [[first, '10', '12'], [second, '13', '15']]) {
    const group = payload.questions.price_range.values.groups[0];
    group.price_observed = null;
    group.average = null;
    group.minimum = minimum;
    group.maximum = maximum;
  }
  const series = buildBrandPriceSeries([first, second], sources);
  assert.equal(series.length, 1);
  assert.deepEqual(series[0].points.map(point => [point.low, point.high, point.raw]), [[10, 12, null], [13, 15, null]]);
});

test('counts high-relevance presence only from explicit semantic functions', () => {
  const presence = buildMarketPresence([result(0), result(1, {preference: ''})], sources);
  assert.equal(presence[0].capturedSources.length, 2);
  assert.equal(presence[0].relevantSources.length, 1);
  assert.equal(presence[0].relevantSources[0].label, 'Loja A');
});

test('counts domains instead of duplicate capture rows when source URLs are available', () => {
  const sameDomain = [{label: 'Página A', url: 'https://shop.example/a'}, {label: 'Página B', url: 'https://shop.example/b'}];
  const presence = buildMarketPresence([result(0), result(1)], sameDomain);
  assert.equal(presence[0].capturedSources.length, 1);
  assert.equal(buildCompetitiveProducts([result(0), result(1)], sameDomain).length, 0);
  assert.equal(buildBrandPriceSeries([result(0), result(1)], sameDomain).length, 0);
});

test('requires preference declarations from distinct domains before assigning a designation', () => {
  const domainSources = [
    {label: 'Página A', url: 'https://shop.example/a'},
    {label: 'Página B', url: 'https://shop.example/b'},
    {label: 'Loja C', url: 'https://other.example/product'},
  ];
  const matches = buildCompetitiveProducts([result(0), result(1), result(2, {preference: ''})], domainSources);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].sourceCount, 2);
  assert.equal(matches[0].preferenceSourceCount, 1);
  assert.equal(matches[0].designation, null);
});
