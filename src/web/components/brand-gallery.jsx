'use client';

import {useEffect, useRef, useState} from 'react';
import {moneyText} from '../lib/contract-view.mjs';

function safeSource(value) {
  if (typeof value !== 'string') return null;
  if (value.startsWith('/compare-assets/')) return value;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function ProductImage({src, alt}) {
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [src]);
  const source = safeSource(src);
  if (!source || broken) return <div className="cp-brand-image-empty" role="img" aria-label="Imagem não disponível"><span>Imagem não disponível</span></div>;
  return <img src={source} alt={alt || 'Produto sem nome declarado'} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)}/>;
}

function priceLabel(groups) {
  const group = groups[0];
  if (!group) return {value: 'Preço não declarado', note: ''};
  if (group.minimum != null && group.maximum != null) {
    return {value: `${moneyText(group.minimum, group.currency)} – ${moneyText(group.maximum, group.currency)}`, note: 'Faixa recebida'};
  }
  const value = group.price_observed ?? group.average;
  return {value: moneyText(value, group.currency, group.offers?.[0]?.currency_symbol), note: group.price_observed != null ? 'Preço observado' : value != null ? 'Média recebida' : ''};
}

function ratingLabel(rating) {
  if (!rating) return 'Avaliação não declarada';
  const scale = rating.scale && typeof rating.scale === 'object' && rating.scale.min != null && rating.scale.max != null ? ` de ${rating.scale.max}` : '';
  return `${rating.score ?? '—'}${scale}`;
}

function BrandProduct({entry, designation, onOpen}) {
  const {product, source, image, rating, priceGroups} = entry;
  const price = priceLabel(priceGroups);
  return <article className="cp-brand-product">
    <button type="button" className="cp-brand-product-open" onClick={() => onOpen(source.index, product)} aria-label={`Abrir detalhes de ${product.name || 'produto sem nome'}`}>
      <div className="cp-brand-product-image"><ProductImage src={image} alt={product.name}/><span>{'AB'[source.index] || source.index + 1}</span></div>
      <div className="cp-brand-product-copy">
        <small>{source.label}</small>
        <h3>{product.name || 'Produto sem nome declarado'}</h3>
        {designation && <strong className="cp-value-tag">{designation}</strong>}
        <dl>
          <div><dt>Preço</dt><dd>{price.value}</dd></div>
          <div><dt>Avaliação</dt><dd>{ratingLabel(rating)}</dd></div>
        </dl>
        {price.note && <p>{price.note}{priceGroups.length > 1 ? ` · mais ${priceGroups.length - 1} grupo(s)` : ''}</p>}
      </div>
    </button>
  </article>;
}

function BrandRail({group, designations, onOpen}) {
  const rail = useRef(null);
  const move = direction => rail.current?.scrollBy({left: direction * Math.max(280, rail.current.clientWidth * .72), behavior: 'smooth'});
  return <section className="cp-brand-group" aria-labelledby={`brand-${encodeURIComponent(group.brand)}`}>
    <header>
      <div><h2 id={`brand-${encodeURIComponent(group.brand)}`}>{group.brand}</h2><p>{group.products.length} produto(s) · {group.sources.length} fonte(s)</p></div>
      <div className="cp-carousel-actions" aria-label={`Navegar na galeria de ${group.brand}`}>
        <button type="button" onClick={() => move(-1)} aria-label={`Produtos anteriores de ${group.brand}`}>←</button>
        <button type="button" onClick={() => move(1)} aria-label={`Próximos produtos de ${group.brand}`}>→</button>
      </div>
    </header>
    <div className="cp-brand-carousel" ref={rail} tabIndex="0" aria-label={`Galeria de produtos da marca ${group.brand}`}>
      {group.products.map(entry => {const entryKey = `${entry.source.index}:${entry.product.entity_id}`; return <BrandProduct key={entryKey} entry={entry} designation={designations.get(entryKey)} onOpen={onOpen}/>;})}
    </div>
  </section>;
}

export default function BrandGallery({groups, matches, onOpen}) {
  const designations = new Map(matches.flatMap(match => match.designation ? match.entries.map(entry => [`${entry.source.index}:${entry.product.entity_id}`, match.designation]) : []));
  return <section className="cp-brand-gallery" aria-labelledby="brand-gallery-title">
    <header className="cp-brand-section-heading"><div><h2 id="brand-gallery-title">Galeria por marca</h2><p>Fotos, nomes, preços e avaliações permanecem ligados à fonte e aos grupos contratuais recebidos.</p></div><span>{groups.length} marca(s)</span></header>
    {!groups.length ? <div className="cp-brand-empty" role="status"><h3>Nenhuma marca encontrada</h3><p>Os produtos aparecerão quando o backend declarar o campo de marca no contrato semântico.</p></div> : groups.map(group => <BrandRail key={group.brand.toLocaleLowerCase('pt-BR')} group={group} designations={designations} onOpen={onOpen}/>)}
  </section>;
}
