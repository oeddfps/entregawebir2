import {asArray, contractQuestion} from './contract-view.mjs';

const PREFERENCE_LABELS = new Map([
  ['featured', 'Produto de Alto Valor'],
  ['preferred', 'Produto de Alto Valor'],
  ['high_value', 'Produto de Alto Valor'],
  ['category_leader', 'Líder da Categoria'],
]);

const text = value => typeof value === 'string' ? value.trim() : '';
const key = value => text(value).toLocaleLowerCase('pt-BR');

function sourceAt(sources, index) {
  const source = sources?.[index] || {};
  const url = source.url || null;
  let domain = null;
  try { domain = new URL(url).hostname || null; } catch {}
  return {index, label: source.label || `Fonte ${'AB'[index] || index + 1}`, url, domain};
}

const sourceKey = source => source.domain || `source-${source.index}`;

function functionCode(value) {
  if (typeof value === 'string') return key(value);
  if (!value || typeof value !== 'object') return '';
  return key(value.code || value.value || value.name || value.function);
}

export function declaredPreferences(product) {
  const found = [];
  for (const use of asArray(product?.images)) {
    if (use?.function_status !== 'declared' || use.visibility === 'hidden') continue;
    for (const raw of asArray(use.functions)) {
      const code = functionCode(raw);
      if (PREFERENCE_LABELS.has(code) && !found.some(item => item.code === code)) {
        found.push({code, label: PREFERENCE_LABELS.get(code), usage_ref: use.usage_ref || null});
      }
    }
  }
  return found;
}

export function productPriceGroups(payload, product) {
  const variants = new Set(asArray(product?.variant_refs));
  if (!variants.size) return [];
  const groups = contractQuestion(payload, 'price_range')?.values?.groups;
  return asArray(groups).filter(group => variants.has(group?.variant_ref));
}

function primaryImage(product) {
  const uses = asArray(product?.images)
    .filter(use => use?.visibility !== 'hidden')
    .sort((left, right) => (left.order ?? Number.MAX_SAFE_INTEGER) - (right.order ?? Number.MAX_SAFE_INTEGER));
  for (const use of uses) {
    const resource = asArray(use.resources).find(value => typeof value === 'string' && value.trim());
    if (resource) return resource;
  }
  return null;
}

function productEntry(payload, product, source) {
  return {
    product,
    source,
    image: primaryImage(product),
    rating: asArray(product?.ratings)[0] || null,
    priceGroups: productPriceGroups(payload, product),
    preferences: declaredPreferences(product),
  };
}

function productsOf(payload) {
  if (Array.isArray(payload?.products)) return payload.products;
  const products = asArray(payload?.data?.products);
  const appearances = asArray(contractQuestion(payload, 'visual_presentation')?.values?.appearances);
  return products.map(product => ({
    ...product,
    images: appearances
      .filter(appearance => asArray(appearance?.subject_refs).includes(product.entity_id))
      .flatMap(appearance => asArray(appearance?.image_uses)),
  }));
}

export function buildBrandGallery(payloads, sources = [], search = '') {
  const groups = new Map();
  const query = key(search);
  asArray(payloads).forEach((payload, index) => {
    if (!payload) return;
    const source = sourceAt(sources, index);
    for (const product of productsOf(payload)) {
      const brand = text(product?.brand) || 'Marca não declarada';
      if (query && !key([brand, product?.name, product?.description, source.label].filter(Boolean).join(' ')).includes(query)) continue;
      const brandKey = key(brand);
      if (!groups.has(brandKey)) groups.set(brandKey, {brand, products: [], sources: new Map()});
      const group = groups.get(brandKey);
      group.products.push(productEntry(payload, product, source));
      group.sources.set(index, source);
    }
  });
  return [...groups.values()]
    .map(group => ({...group, sources: [...group.sources.values()]}))
    .sort((left, right) => left.brand === 'Marca não declarada' ? 1 : right.brand === 'Marca não declarada' ? -1 : left.brand.localeCompare(right.brand, 'pt-BR'));
}

export function buildCompetitiveProducts(payloads, sources = []) {
  const matches = new Map();
  asArray(payloads).forEach((payload, index) => {
    if (!payload) return;
    const source = sourceAt(sources, index);
    for (const product of productsOf(payload)) {
      const gtin = text(product?.gtin);
      if (!gtin || product?.identity_status !== 'resolved') continue;
      if (!matches.has(gtin)) matches.set(gtin, []);
      matches.get(gtin).push(productEntry(payload, product, source));
    }
  });
  return [...matches.entries()].flatMap(([gtin, entries]) => {
    const sourceCount = new Set(entries.map(entry => sourceKey(entry.source))).size;
    if (sourceCount < 2) return [];
    const preferred = entries.filter(entry => entry.preferences.length);
    const leaders = entries.filter(entry => entry.preferences.some(item => item.code === 'category_leader'));
    const preferenceSourceCount = new Set(preferred.map(entry => sourceKey(entry.source))).size;
    const leaderSourceCount = new Set(leaders.map(entry => sourceKey(entry.source))).size;
    const designation = leaderSourceCount >= 2 ? 'Líder da Categoria' : preferenceSourceCount >= 2 ? 'Produto de Alto Valor' : null;
    const assertionRefs = [...new Set(entries.flatMap(entry => asArray(entry.product?.field_assertion_refs?.gtin)))];
    return [{gtin, entries, sourceCount, preferenceSourceCount, designation, assertionRefs}];
  }).sort((left, right) => (right.designation ? 1 : 0) - (left.designation ? 1 : 0) || right.sourceCount - left.sourceCount);
}

function numericDecimal(value) {
  if (value === null || value === undefined || value === '' || !/^-?\d+(?:\.\d+)?$/.test(String(value).trim())) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function groupPoint(group, entry) {
  const raw = group.price_observed ?? group.average;
  const value = numericDecimal(raw);
  const receivedMinimum = numericDecimal(group.minimum);
  const receivedMaximum = numericDecimal(group.maximum);
  const hasRange = receivedMinimum !== null && receivedMaximum !== null;
  if (value === null && !hasRange) return null;
  const low = value ?? receivedMinimum;
  const high = value ?? receivedMaximum;
  return {
    low,
    high,
    raw: value !== null ? String(raw) : null,
    rawMinimum: hasRange ? String(group.minimum) : null,
    rawMaximum: hasRange ? String(group.maximum) : null,
    basis: value !== null ? (group.price_observed != null ? 'Preço observado' : 'Média recebida') : 'Intervalo recebido',
    currency: text(group.currency) || 'Moeda não declarada',
    variant_ref: group.variant_ref,
    conditions: group.conditions,
    comparison_time: asArray(group.comparison_time),
    productName: text(entry.product?.name) || 'Produto sem nome',
    source: entry.source,
  };
}

export function buildBrandPriceSeries(payloads, sources = []) {
  const series = new Map();
  for (const group of buildBrandGallery(payloads, sources)) {
    if (group.brand === 'Marca não declarada') continue;
    for (const entry of group.products) {
      for (const priceGroup of entry.priceGroups) {
        const point = groupPoint(priceGroup, entry);
        if (!point) continue;
        const seriesKey = `${key(group.brand)}\u0000${point.currency}`;
        if (!series.has(seriesKey)) series.set(seriesKey, {brand: group.brand, currency: point.currency, points: []});
        series.get(seriesKey).points.push(point);
      }
    }
  }
  return [...series.values()].filter(item => new Set(item.points.map(point => sourceKey(point.source))).size > 1);
}

export function buildMarketPresence(payloads, sources = []) {
  return buildBrandGallery(payloads, sources)
    .filter(group => group.brand !== 'Marca não declarada')
    .map(group => {
      const captured = new Map();
      const relevant = new Map();
      for (const entry of group.products) {
        captured.set(sourceKey(entry.source), entry.source);
        if (entry.preferences.length) relevant.set(sourceKey(entry.source), entry.source);
      }
      return {brand: group.brand, capturedSources: [...captured.values()], relevantSources: [...relevant.values()]};
    })
    .sort((left, right) => right.relevantSources.length - left.relevantSources.length || right.capturedSources.length - left.capturedSources.length || left.brand.localeCompare(right.brand, 'pt-BR'));
}
