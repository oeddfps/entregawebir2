'use client';

import BrandGallery from './brand-gallery';
import {moneyText, valueLabel} from '../lib/contract-view.mjs';
import {
  buildBrandGallery,
  buildBrandPriceSeries,
  buildCostBenefitRanking,
  buildCompetitiveProducts,
  buildMarketPresence,
} from '../lib/brand-competitiveness.mjs';

function safeLink(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function rawPrice(group) {
  if (!group) return '—';
  if (group.minimum != null && group.maximum != null) return `${moneyText(group.minimum, group.currency)} – ${moneyText(group.maximum, group.currency)}`;
  return moneyText(group.price_observed ?? group.average, group.currency, group.offers?.[0]?.currency_symbol);
}

function ratingText(rating) {
  if (!rating) return '—';
  const scale = rating.scale && typeof rating.scale === 'object' && rating.scale.max != null ? ` / ${rating.scale.max}` : '';
  return `${rating.score ?? '—'}${scale}`;
}

function CostBenefitRanking({rows}) {
  return <section className="cp-card cp-cost-benefit"><header className="cp-card-heading"><div><h2>Ranking de costo-beneficio</h2><p>Ordena los productos con precio, moneda y valoración declarados. La puntuación es valoración normalizada dividida por precio; no mezcla monedas ni inventa datos.</p></div></header>
    {!rows.length ? <p className="cp-brand-empty">No hay suficientes datos comparables: cada producto necesita precio y valoración con escala declarados.</p> : <div className="cp-cost-benefit-list">{rows.map(row => <article className="cp-cost-benefit-row" key={`${row.source.index}:${row.product.entity_id}`}>
      <strong className="cp-cost-benefit-rank">#{row.rank}</strong>
      <div className="cp-cost-benefit-product"><b>{row.productName}</b><span>{row.brand} · {row.source.label}</span><p>{row.description}</p></div>
      <dl><div><dt>Precio</dt><dd>{moneyText(row.costBenefit.price, row.costBenefit.currency)}</dd></div><div><dt>Valoración</dt><dd>{row.costBenefit.rating} / {row.costBenefit.ratingMaximum}</dd></div></dl>
    </article>)}</div>}
  </section>;
}

function MarketPresence({rows}) {
  return <section className="cp-card cp-market-presence"><header className="cp-card-heading"><div><h2>Presencia en el mercado</h2><p>Fuentes con una función de alta relevancia declarada explícitamente, comparadas con las fuentes donde se capturó la marca.</p></div></header>
    {!rows.length ? <p className="cp-brand-empty">No hay marcas declaradas en los resultados actuales.</p> : <div className="cp-presence-list">{rows.map(row => <article key={row.brand}>
      <div><h3>{row.brand}</h3><strong>{row.relevantSources.length} de {row.capturedSources.length}</strong></div>
      <progress max={Math.max(1, row.capturedSources.length)} value={row.relevantSources.length} aria-label={`${row.brand}: ${row.relevantSources.length} de ${row.capturedSources.length} fontes com alta relevância declarada`}/>
      <p>{row.relevantSources.length ? row.relevantSources.map(source => source.label).join(' · ') : 'Ninguna fuente declaró featured, preferred, high_value o category_leader.'}</p>
    </article>)}</div>}
  </section>;
}

function PriceSeries({series}) {
  const width = 720, left = 170, right = 46, plot = width - left - right;
  const sources = [...new Map(series.points.map(point => [point.source.index, point.source])).values()];
  const values = series.points.flatMap(point => [point.low, point.high]);
  const minimum = Math.min(...values), maximum = Math.max(...values), span = Math.max(1, maximum - minimum);
  const height = 54 + sources.length * 48;
  return <article className="cp-price-series">
    <header><div><h3>{series.brand}</h3><p>{series.currency} · cada ponto é um grupo contratual; sem média entre variantes</p></div><strong>{moneyText(String(minimum), series.currency)} – {moneyText(String(maximum), series.currency)}</strong></header>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${series.brand}, variación de ${minimum} a ${maximum} ${series.currency}`}>
      {sources.map((source, row) => {const y = 30 + row * 48; return <g key={source.index}><text x={left - 14} y={y + 4} textAnchor="end" className="cp-axis-text">{source.label}</text><line x1={left} x2={left + plot} y1={y} y2={y} className="cp-price-axis"/>{series.points.filter(point => point.source.index === source.index).map((point, index) => {const xLow = left + (point.low - minimum) / span * plot; const xHigh = left + (point.high - minimum) / span * plot; const label = point.raw != null ? moneyText(point.raw, point.currency) : `${moneyText(point.rawMinimum, point.currency)} – ${moneyText(point.rawMaximum, point.currency)}`; return <g key={`${point.variant_ref}:${index}`} className={`cp-source-${source.index}`}>{point.low === point.high ? <circle cx={xLow} cy={y} r="6" fill="var(--cp-color)"/> : <><line x1={xLow} x2={xHigh} y1={y} y2={y} className="cp-price-range"/><circle cx={xLow} cy={y} r="4" fill="var(--cp-color)"/><circle cx={xHigh} cy={y} r="4" fill="var(--cp-color)"/></>}<title>{point.productName} · {point.basis}: {label} · {valueLabel(point.conditions)}</title></g>;})}</g>;})}
      <text x={left} y={height - 6} className="cp-axis-text">{moneyText(String(minimum), series.currency)}</text><text x={left + plot} y={height - 6} textAnchor="end" className="cp-axis-text">{moneyText(String(maximum), series.currency)}</text>
    </svg>
  </article>;
}

function BrandPriceVariation({series}) {
  return <section className="cp-card cp-brand-prices"><header className="cp-card-heading"><div><h2>Variación de precios por marca</h2><p>Comparación visual de los grupos de precios recibidos para la misma marca y moneda en fuentes diferentes.</p></div></header>
    {!series.length ? <p className="cp-brand-empty">No hay grupos de la misma marca y moneda en dos fuentes. No se infirió ninguna conversión ni combinación.</p> : <div className="cp-price-series-list">{series.map(item => <PriceSeries key={`${item.brand}:${item.currency}`} series={item}/>)}</div>}
  </section>;
}

function CompetitorMatrix({matches, onOpen, onEvidence}) {
  return <section className="cp-card cp-competitor-matrix"><header className="cp-card-heading"><div><h2>Análisis de productos de alto valor</h2><p>Correspondencia entre sitios solo por GTIN exacto con identidad resuelta. La preferencia debe declararse en al menos dos fuentes.</p></div></header>
    {!matches.length ? <div className="cp-brand-empty" role="status"><h3>Equivalencia no establecida</h3><p>Ningún producto tiene el mismo GTIN resuelto en dos fuentes. Los nombres, fotos y descripciones no se utilizan para presumir identidad.</p></div> : <div className="cp-match-list">{matches.map(match => <article key={match.gtin}>
      <header><div><span>GTIN {match.gtin}</span><h3>{match.entries[0].product.name || 'Producto sin nombre declarado'}</h3></div>{match.designation ? <strong className="cp-value-tag">{match.designation}</strong> : <span className="cp-neutral-tag">Sin preferencia entre sitios declarada</span>}</header>
      <div className="cp-match-table" role="table" aria-label={`Comparación del GTIN ${match.gtin}`}>
        <div className="cp-match-row cp-match-head" role="row"><span role="columnheader">Fuente / página</span><span role="columnheader">Precio</span><span role="columnheader">Valoración</span><span role="columnheader">Señal declarada</span></div>
        {match.entries.map(entry => <div className="cp-match-row" role="row" key={`${entry.source.index}:${entry.product.entity_id}`}>
          <span role="cell"><b>{entry.source.label}</b>{safeLink(entry.product.url || entry.source.url) ? <a href={safeLink(entry.product.url || entry.source.url)} target="_blank" rel="noopener noreferrer">Abrir página</a> : <small>Página no declarada</small>}</span>
          <span role="cell"><b>{rawPrice(entry.priceGroups[0])}</b>{entry.priceGroups.length > 1 && <small>+ {entry.priceGroups.length - 1} grupo(s)</small>}</span>
          <span role="cell"><b>{ratingText(entry.rating)}</b><small>{entry.rating?.count != null ? `${entry.rating.count} registros publicados` : 'Cantidad no declarada'}</small></span>
          <span role="cell"><b>{entry.preferences.map(item => item.label).join(' · ') || 'No declarado'}</b><button type="button" className="cp-text-button" onClick={() => onOpen(entry.source.index, entry.product)}>Ver producto</button>{entry.product.field_assertion_refs?.gtin?.length > 0 && <button type="button" className="cp-text-button" onClick={() => onEvidence(entry.source.index, entry.product.field_assertion_refs.gtin)}>Ver GTIN</button>}</span>
        </div>)}
      </div>
    </article>)}</div>}
  </section>;
}

export default function BrandCompetitiveness({results, sources, search, onOpen, onEvidence}) {
  const gallery = buildBrandGallery(results, sources, search);
  const matches = buildCompetitiveProducts(results, sources);
  const prices = buildBrandPriceSeries(results, sources);
  const presence = buildMarketPresence(results, sources);
  const ranking = buildCostBenefitRanking(results, sources);
  return <div className="cp-brand-intelligence">
    <BrandGallery groups={gallery} matches={matches} onOpen={onOpen}/>
    <CostBenefitRanking rows={ranking}/>
    <div className="cp-brand-analysis-grid"><MarketPresence rows={presence}/><BrandPriceVariation series={prices}/></div>
    <CompetitorMatrix matches={matches} onOpen={onOpen} onEvidence={onEvidence}/>
  </div>;
}
