'use client';

import {useMemo, useState} from 'react';
import {
  QUESTION_DEFINITIONS,
  asArray,
  contractQuestion,
  contractVisualizations,
  coverageRows,
  decimalText,
  graphLayout,
  moneyText,
  statusCounts,
  valueLabel,
  wordSize,
} from '../lib/contract-view.mjs';

const STATUS_LABELS = {
  answered: 'Con información',
  partial: 'Cobertura parcial',
  not_answerable: 'Sin información suficiente',
  not_available: 'Todavía no disponible',
  ready: 'Disponible',
  not_available_visualization: 'No disponible',
};

const OFFER_KINDS = {exact: 'Exacto', from: 'Desde', until: 'Hasta', previous: 'Anterior', installment: 'Cuota'};
const DISCOUNT = {discount: 'Con descuento', no_discount: 'Sin descuento', unknown: 'No determinado', conflict: 'Datos en conflicto'};
const VOICES = {brand: 'Marca', seller: 'Vendedor', consumer: 'Consumidores', unknown: 'Autoría desconocida', all: 'Todas las voces'};
const SENTIMENTS = {favorable: 'Favorable', unfavorable: 'Desfavorable', mixed: 'Mixta', neutral: 'Neutral', indeterminate: 'Indeterminada'};
const BASES = {explicit_category_opinion: 'Opinión explícita de categoría', product_reviews_in_category: 'Reseñas de productos en la categoría'};

const safeUrl = value => {
  if (typeof value !== 'string') return undefined;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
};

function StatusMark({status}) {
  return <span className={`cp-contract-status cp-contract-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

function SourceHeading({index, name, question, title}) {
  return <header className="cp-contract-source-heading">
    <div><span className="cp-contract-source-letter">{'AB'[index]}</span><div><h2>{title || name}</h2>{title && <p>{name}</p>}</div></div>
    <StatusMark status={question?.status || 'not_available'}/>
  </header>;
}

function EvidenceButton({index, refs, onEvidence, children = 'Ver evidencia'}) {
  return asArray(refs).length && onEvidence ? <button className="cp-text-button" onClick={() => onEvidence(index, refs)}>{children}</button> : null;
}

function ContractEmpty({children}) {
  return <div className="cp-contract-empty" role="status"><strong>Sin resultados utilizables</strong><p>{children}</p></div>;
}

function CoverageNote({question}) {
  if (!question || question.status === 'answered') return null;
  return <div className={`cp-contract-notice cp-contract-notice-${question.status}`} role="status">
    <strong>{question.status === 'partial' ? 'La cobertura es incompleta.' : 'La fuente no permitió responder esta pregunta.'}</strong>
    <span>{asArray(question.exclusions).length ? `${question.exclusions.length} elemento(s) quedaron fuera del resultado.` : 'Los campos desconocidos se mantienen como no disponibles.'}</span>
  </div>;
}

export function CoverageMatrix({results, names, onOpen}) {
  const rows = coverageRows(results);
  const counts = statusCounts(results);
  const total = Math.max(1, asArray(results).length * QUESTION_DEFINITIONS.length);
  return <section className="cp-coverage" aria-labelledby="contract-coverage-title">
    <header className="cp-section-heading">
      <div><h2 id="contract-coverage-title">Cobertura del contrato</h2><p>Las respuestas se resuelven por <code>question_id</code>; parcial no equivale a vacío.</p></div>
      <p className="cp-coverage-summary"><strong>{counts.answered}</strong> de {total} respondidas{counts.partial ? ` · ${counts.partial} parciales` : ''}</p>
    </header>
    <div className="cp-coverage-table" role="table" aria-label="Cobertura por pregunta y fuente">
      <div className="cp-coverage-row cp-coverage-head" role="row">
        <span role="columnheader">Pregunta contractual</span>
        {names.map((name, index) => <span role="columnheader" key={index}>{'AB'[index]} · {name}</span>)}
      </div>
      {rows.map(row => <div className="cp-coverage-row" role="row" key={row.id}>
        <button role="rowheader" onClick={() => onOpen?.(row.id)} disabled={!onOpen}><strong>{row.label}</strong><span>Ver respuesta</span></button>
        {row.statuses.map((status, index) => <div role="cell" key={index}><StatusMark status={status}/></div>)}
      </div>)}
    </div>
  </section>;
}

function Exclusions({items}) {
  const rows = asArray(items);
  if (!rows.length) return null;
  return <details className="cp-contract-exclusions"><summary>{rows.length} exclusión(es) documentadas</summary><ul>{rows.map((item, index) => <li key={item?.ref || item?.offer_ref || index}>{valueLabel(item)}</li>)}</ul></details>;
}

function OfferTable({group, sourceIndex, onEvidence}) {
  const offers = asArray(group.offers);
  if (!offers.length) return <ContractEmpty>El grupo existe, pero no contiene ofertas para mostrar.</ContractEmpty>;
  return <div className="cp-contract-table-wrap"><table className="cp-contract-table">
    <thead><tr><th>Vendedor</th><th>Importe</th><th>Tipo</th><th>Descuento</th><th>Vigencia</th><th><span className="cp-sr-only">Evidencia</span></th></tr></thead>
    <tbody>{offers.map((offer, index) => <tr key={offer.offer_ref || index}>
      <td data-label="Vendedor"><strong>{offer.seller || 'No declarado'}</strong></td>
      <td data-label="Importe" className="cp-num">{moneyText(offer.amount, group.currency, offer.currency_symbol)}</td>
      <td data-label="Tipo">{OFFER_KINDS[offer.kind] || offer.kind || 'No declarado'}</td>
      <td data-label="Descuento">{DISCOUNT[offer.discount_status] || 'No determinado'}{offer.previous_amount != null && <small>Antes: {moneyText(offer.previous_amount, group.currency, offer.currency_symbol)}</small>}</td>
      <td data-label="Vigencia">{valueLabel(offer.valid_period)}</td>
      <td><EvidenceButton index={sourceIndex} refs={offer.assertion_refs} onEvidence={onEvidence}/></td>
    </tr>)}</tbody>
  </table></div>;
}

function PriceGroup({group, result, sourceIndex, onEvidence}) {
  const symbol = asArray(group.offers).find(offer => offer.currency_symbol)?.currency_symbol;
  const label = result?.labels?.[group.variant_ref] || 'Variante sin etiqueta';
  return <article className="cp-price-contract-group">
    <header><div><h3>{label}</h3><p>{group.currency || 'Moneda no declarada'} · {group.range_basis === 'exact_comparable_offers' ? 'Ofertas exactas comparables' : 'Sin rango observado'}</p></div><code title={group.variant_ref}>{group.variant_ref || 'sin referencia'}</code></header>
    <dl className="cp-price-facts">
      <div className="cp-price-lead"><dt>Promedio recibido</dt><dd>{moneyText(group.average, group.currency, symbol)}</dd></div>
      <div><dt>Precio observado</dt><dd>{moneyText(group.price_observed, group.currency, symbol)}</dd></div>
      <div><dt>Mínimo</dt><dd>{moneyText(group.minimum, group.currency, symbol)}</dd></div>
      <div><dt>Máximo</dt><dd>{moneyText(group.maximum, group.currency, symbol)}</dd></div>
    </dl>
    <div className="cp-contract-meta"><span><b>Condiciones</b>{valueLabel(group.conditions)}</span><span><b>Período de comparación</b>{valueLabel(group.comparison_time)}</span></div>
    <OfferTable group={group} sourceIndex={sourceIndex} onEvidence={onEvidence}/>
  </article>;
}

export function PriceRangeResults({results, names, onEvidence}) {
  return <div className="cp-contract-stack">{results.map((result, index) => {
    const question = contractQuestion(result, 'price_range');
    const groups = asArray(question?.values?.groups);
    return <section className="cp-contract-panel" key={index}>
      <SourceHeading index={index} name={names[index]} question={question} title="Rango de precios"/>
      <CoverageNote question={question}/>
      {groups.length ? groups.map((group, groupIndex) => <PriceGroup key={group.variant_ref || groupIndex} group={group} result={result} sourceIndex={index} onEvidence={onEvidence}/>) : <ContractEmpty>No se formó ningún grupo comparable de variante, moneda, condiciones y período.</ContractEmpty>}
      <Exclusions items={question?.exclusions}/>
    </section>;
  })}</div>;
}

function ImageUse({use, subjectLabel}) {
  const resource = asArray(use.resources).find(safeUrl);
  return <article className="cp-image-use">
    <div className="cp-image-use-media">{resource ? <img src={resource} alt={`Recurso asociado a ${subjectLabel}`} loading="lazy" referrerPolicy="no-referrer"/> : <span>Recurso no disponible</span>}</div>
    <div className="cp-image-use-copy">
      <div><strong>{use.order == null ? 'Orden no declarado' : `Posición ${use.order}`}</strong><StatusMark status={use.visibility || 'not_available'}/></div>
      <dl><div><dt>Contexto</dt><dd>{valueLabel(use.context)}</dd></div><div><dt>Funciones</dt><dd>{asArray(use.functions).length ? asArray(use.functions).map(valueLabel).join(' · ') : 'No interpretadas'}</dd></div><div><dt>Estado de función</dt><dd>{use.function_status === 'declared' ? 'Declarada por la fuente' : 'No interpretada'}</dd></div></dl>
      <code title={use.usage_ref}>{use.usage_ref || 'uso sin referencia'}</code>
    </div>
  </article>;
}

export function VisualPresentationResults({results, names, onEvidence}) {
  return <div className="cp-contract-stack">{results.map((result, index) => {
    const question = contractQuestion(result, 'visual_presentation');
    const appearances = asArray(question?.values?.appearances);
    return <section className="cp-contract-panel" key={index}>
      <SourceHeading index={index} name={names[index]} question={question} title="Presentación visual"/>
      <CoverageNote question={question}/>
      <p className="cp-contract-rule">Una imagen se muestra como recurso asociado a un uso. La interfaz no infiere portada, envase ni banner.</p>
      {appearances.length ? <div className="cp-appearance-list">{appearances.map((appearance, appearanceIndex) => {
        const subjects = asArray(appearance.subject_refs).map(ref => result?.labels?.[ref] || ref);
        return <article className="cp-appearance" key={appearance.appearance_ref || appearanceIndex}>
          <header><div><h3>{subjects.join(', ') || 'Entidad sin etiqueta'}</h3><p>{asArray(appearance.image_uses).length} uso(s) de imagen</p></div><code>{appearance.appearance_ref}</code></header>
          <div className="cp-image-use-grid">{asArray(appearance.image_uses).map((use, useIndex) => <ImageUse key={use.usage_ref || useIndex} use={use} subjectLabel={subjects[0] || 'la entidad'}/>)}</div>
        </article>;
      })}</div> : <ContractEmpty>No se registraron apariciones con usos de imagen asociados.</ContractEmpty>}
      <EvidenceButton index={index} refs={question?.supporting_assertion_ids} onEvidence={onEvidence} children="Ver respaldo de la respuesta"/>
      <Exclusions items={question?.exclusions}/>
    </section>;
  })}</div>;
}

const unique = values => [...new Set(values.filter(value => value !== null && value !== undefined && value !== ''))];

function KeywordBucket({rows, sourceIndex, onEvidence}) {
  const maximum = Math.max(1, ...rows.map(row => Number(row.expression_occurrences) || 0));
  return <div className="cp-keyword-bucket">
    <header><h3>{rows[0].kind === 'topic' ? 'Temas' : 'Palabras repetidas'}</h3><p>{rows[0].language || 'Idioma no declarado'} · {rows[0].corpus_id || 'Corpus no declarado'}</p></header>
    <div className="cp-term-list">{rows.map((row, index) => <div className="cp-term-row" key={`${row.label}-${index}`}>
      <div><strong>{row.label}</strong><span>{VOICES[row.voice] || row.voice} · {row.unique_content_units} unidad(es) de contenido · {row.independent_authors == null ? 'independencia no establecida' : `${row.independent_authors} autor(es) independiente(s)`}</span></div>
      <div className="cp-term-measure"><span style={{width: `${Math.max(2, Number(row.expression_occurrences) / maximum * 100)}%`}}/><b>{decimalText(row.expression_occurrences)}</b></div>
      <EvidenceButton index={sourceIndex} refs={row.assertion_refs} onEvidence={onEvidence}/>
    </div>)}</div>
  </div>;
}

export function KeywordsResults({results, names, onEvidence}) {
  const allGroups = results.flatMap(result => asArray(contractQuestion(result, 'keywords')?.values?.groups));
  const kinds = unique(allGroups.map(group => group.kind));
  const voices = unique(allGroups.map(group => group.voice));
  const languages = unique(allGroups.map(group => group.language));
  const [kind, setKind] = useState('all');
  const [voice, setVoice] = useState('all');
  const [language, setLanguage] = useState('all');
  return <div className="cp-contract-stack">
    <div className="cp-contract-filters" aria-label="Filtros de términos">
      <label>Tipo<select value={kind} onChange={event => setKind(event.target.value)}><option value="all">Todos</option>{kinds.map(value => <option key={value} value={value}>{value === 'keyword' ? 'Palabras' : 'Temas'}</option>)}</select></label>
      <label>Voz<select value={voice} onChange={event => setVoice(event.target.value)}><option value="all">Todas</option>{voices.map(value => <option key={value} value={value}>{VOICES[value] || value}</option>)}</select></label>
      <label>Idioma<select value={language} onChange={event => setLanguage(event.target.value)}><option value="all">Todos, separados</option>{languages.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
    </div>
    {results.map((result, index) => {
      const question = contractQuestion(result, 'keywords');
      const definition = question?.values?.definition || 'Definición no declarada';
      const filtered = asArray(question?.values?.groups).filter(group => (kind === 'all' || group.kind === kind) && (voice === 'all' || group.voice === voice) && (language === 'all' || group.language === language));
      const buckets = new Map();
      for (const row of filtered) {
        const key = `${row.kind}|${row.language || ''}|${row.corpus_id || ''}`;
        if (!buckets.has(key)) buckets.set(key, []);
        buckets.get(key).push(row);
      }
      for (const rows of buckets.values()) rows.sort((a, b) => b.expression_occurrences - a.expression_occurrences || a.label.localeCompare(b.label));
      return <section className="cp-contract-panel" key={index}>
        <SourceHeading index={index} name={names[index]} question={question} title="Términos y temas"/>
        <CoverageNote question={question}/>
        <p className="cp-contract-rule">Definición: <code>{definition}</code>. Las frecuencias se mantienen separadas por definición, corpus e idioma.</p>
        {buckets.size ? [...buckets.values()].map((rows, bucketIndex) => <KeywordBucket key={bucketIndex} rows={rows} sourceIndex={index} onEvidence={onEvidence}/>) : <ContractEmpty>No hay términos para los filtros seleccionados.</ContractEmpty>}
        <Exclusions items={question?.exclusions}/>
      </section>;
    })}
  </div>;
}

function PublishedAggregates({aggregates, result, sourceIndex, onEvidence}) {
  const rows = asArray(aggregates);
  if (!rows.length) return null;
  return <section className="cp-published-aggregates"><header><h3>Puntuaciones agregadas publicadas</h3><p>Se conservan la escala y el conteo originales; escalas distintas no se comparan.</p></header><div className="cp-contract-table-wrap"><table className="cp-contract-table"><thead><tr><th>Sujeto</th><th>Puntuación</th><th>Escala</th><th>Conteo publicado</th><th><span className="cp-sr-only">Evidencia</span></th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.aggregate_ref || index}><td data-label="Sujeto">{asArray(row.subject_refs).map(ref => result?.labels?.[ref] || ref).join(', ')}</td><td data-label="Puntuación" className="cp-num">{decimalText(row.rating)}</td><td data-label="Escala">{valueLabel(row.scale)}</td><td data-label="Conteo" className="cp-num">{decimalText(row.published_count)} <small>{row.count_kind || 'tipo no especificado'}</small></td><td><EvidenceButton index={sourceIndex} refs={row.assertion_refs} onEvidence={onEvidence}/></td></tr>)}</tbody></table></div></section>;
}

function OpinionGroups({groups, sourceIndex, onEvidence}) {
  const rows = asArray(groups);
  if (!rows.length) return null;
  return <div className="cp-opinion-groups">{rows.map((group, index) => <article className="cp-opinion" key={`${group.category_ref}-${group.aspect}-${index}`}>
    <header><div><h3>{valueLabel(group.aspect)}</h3><p>{BASES[group.basis] || group.basis}</p></div><span className={`cp-sentiment cp-sentiment-${group.sentiment}`}>{SENTIMENTS[group.sentiment] || group.sentiment}</span></header>
    <p>{VOICES[group.voice] || group.voice} · {decimalText(group.unique_opinions)} opinión(es) única(s) · independencia {group.independence === 'known' ? 'conocida' : 'no establecida'}</p>
    {asArray(group.quotes).map((quote, quoteIndex) => <blockquote key={quoteIndex}>{quote}</blockquote>)}
    <EvidenceButton index={sourceIndex} refs={group.assertion_refs} onEvidence={onEvidence}/>
  </article>)}</div>;
}

export function OpinionsResults({results, names, onEvidence}) {
  return <div className="cp-contract-stack">{results.map((result, index) => {
    const question = contractQuestion(result, 'category_opinions');
    const groups = asArray(question?.values?.groups);
    const aggregates = asArray(question?.values?.published_aggregates);
    const findings = asArray(result?.findings);
    return <section className="cp-contract-panel" key={index}>
      <SourceHeading index={index} name={names[index]} question={question} title="Opiniones de categoría"/>
      <CoverageNote question={question}/>
      {!groups.length && !aggregates.length ? <ContractEmpty>No hay opiniones de categoría ni agregados publicados utilizables.</ContractEmpty> : <><OpinionGroups groups={groups} sourceIndex={index} onEvidence={onEvidence}/><PublishedAggregates aggregates={aggregates} result={result} sourceIndex={index} onEvidence={onEvidence}/></>}
      {findings.length > 0 && <section className="cp-contract-findings"><header><h3>Señales que merecen atención</h3><p>Una señal individual no demuestra causalidad ni un efecto general.</p></header>{findings.map((finding, findingIndex) => <article key={finding.finding_id || findingIndex}><strong>{finding.extent === 'pattern' ? 'Patrón en la muestra' : finding.extent === 'individual' ? 'Experiencia individual' : 'Discrepancia'}</strong>{asArray(finding.quotes)[0] && <blockquote>{finding.quotes[0]}</blockquote>}<p>{asArray(finding.aspects).map(valueLabel).join(' · ')} · {decimalText(finding.unique_opinions)} opinión(es)</p><EvidenceButton index={index} refs={finding.assertion_refs} onEvidence={onEvidence}/></article>)}</section>}
      <Exclusions items={question?.exclusions}/>
    </section>;
  })}</div>;
}

function KnowledgeGraph({graph, sourceName}) {
  const layout = useMemo(() => graphLayout(graph), [graph]);
  const initial = asArray(graph?.root_refs)[0] || layout.nodes[0]?.ref;
  const [selectedRef, setSelectedRef] = useState(initial);
  const selected = layout.nodes.find(node => node.ref === selectedRef) || layout.nodes[0];
  if (!layout.nodes.length) return <ContractEmpty>El backend no entregó nodos para esta visualización.</ContractEmpty>;
  return <section className="cp-graph-panel">
    <header className="cp-section-heading"><div><h2>Grafo de conocimiento · {sourceName}</h2><p>Relaciones recibidas en <code>edges</code>; la interfaz no deduce vínculos por etiqueta.</p></div><StatusMark status={graph.status || 'not_available'}/></header>
    {graph.truncated && <div className="cp-contract-notice cp-contract-notice-partial" role="status"><strong>Subgrafo truncado.</strong><span>La vista no representa todo el grafo disponible.</span></div>}
    <div className="cp-graph-layout"><svg viewBox="0 0 760 420" role="img" aria-label={`Grafo RDF con ${layout.nodes.length} nodos y ${layout.edges.length} relaciones`}>
      <g className="cp-graph-edges">{layout.edges.map((edge, index) => <g key={`${edge.source_ref}-${edge.target_ref}-${index}`}><line x1={edge.source.x} y1={edge.source.y} x2={edge.target.x} y2={edge.target.y}/><title>{edge.label || edge.predicate}</title></g>)}</g>
      <g className="cp-graph-nodes">{layout.nodes.map(node => <g key={node.ref} className={`${node.depth === 0 ? 'root ' : ''}${node.ref === selected?.ref ? 'selected' : ''}`} transform={`translate(${node.x} ${node.y})`} role="button" tabIndex="0" aria-label={`${node.label}, ${node.kind}`} onClick={() => setSelectedRef(node.ref)} onKeyDown={event => {if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); setSelectedRef(node.ref);}}}>
        <circle r={node.depth === 0 ? 27 : 21}/><text y="4" textAnchor="middle">{String(node.kind || '?').slice(0, 1)}</text><text className="cp-graph-label" y={node.depth === 0 ? 43 : 37} textAnchor="middle">{String(node.label || node.ref).slice(0, 22)}</text>
      </g>)}</g>
    </svg>
    <aside className="cp-node-detail"><span>{selected?.kind || 'Entidad'}</span><h3>{selected?.label || 'Sin etiqueta'}</h3><code>{selected?.ref}</code><dl><div><dt>Identidad</dt><dd>{selected?.identity_status || 'No declarada'}</dd></div>{Object.entries(selected?.properties || {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{valueLabel(value)}</dd></div>)}</dl></aside></div>
    <details className="cp-graph-relations"><summary>Ver las {layout.edges.length} relaciones como lista</summary><ul>{layout.edges.map((edge, index) => <li key={index}><strong>{edge.source.label}</strong><span>{edge.label || edge.predicate}</span><strong>{edge.target.label}</strong></li>)}</ul></details>
  </section>;
}

export function GraphResults({results, names}) {
  const rows = results.map((result, index) => ({index, graph: contractVisualizations(result).graph})).filter(row => row.graph);
  if (!rows.length) return null;
  return <div className="cp-contract-stack">{rows.map(row => <KnowledgeGraph key={row.index} graph={row.graph} sourceName={names[row.index]}/>)}</div>;
}

function WordCloud({cloud, sourceName}) {
  const terms = asArray(cloud?.terms);
  if (!terms.length) return <ContractEmpty>La visualización no contiene términos para mostrar.</ContractEmpty>;
  const frequencies = terms.map(term => Number(term.frequency) || 0);
  const minimum = Math.min(...frequencies), maximum = Math.max(...frequencies);
  return <section className="cp-word-cloud-panel">
    <header className="cp-section-heading"><div><h2>Nube de categoría · {sourceName}</h2><p>{VOICES[cloud.voice] || cloud.voice} · {cloud.language || 'Idioma no declarado'} · tamaño por {cloud.count_basis || 'frecuencia'}</p></div><StatusMark status={cloud.status || 'not_available'}/></header>
    <div className="cp-word-cloud" role="img" aria-label={`Nube de ${terms.length} términos`}>{terms.map((term, index) => <span key={`${term.text}-${index}`} style={{fontSize: `${wordSize(term.frequency, minimum, maximum)}px`}} title={`${term.frequency} ocurrencias en ${term.content_units} unidades`}>{term.text}<small>{decimalText(term.frequency)}</small></span>)}</div>
    <details><summary>Ver valores exactos</summary><div className="cp-contract-table-wrap"><table className="cp-contract-table"><thead><tr><th>Término</th><th>Frecuencia</th><th>Unidades de contenido</th></tr></thead><tbody>{terms.map((term, index) => <tr key={index}><td>{term.text}</td><td className="cp-num">{decimalText(term.frequency)}</td><td className="cp-num">{decimalText(term.content_units)}</td></tr>)}</tbody></table></div></details>
  </section>;
}

export function WordCloudResults({results, names}) {
  const rows = results.map((result, index) => ({index, cloud: contractVisualizations(result).category_word_cloud})).filter(row => row.cloud);
  if (!rows.length) return null;
  return <div className="cp-contract-stack">{rows.map(row => <WordCloud key={row.index} cloud={row.cloud} sourceName={names[row.index]}/>)}</div>;
}
