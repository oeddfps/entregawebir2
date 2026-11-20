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
  if (!source || broken) return <div className="cp-brand-image-empty" role="img" aria-label="Imagen no disponible"><span>Imagen no disponible</span></div>;
  return <img src={source} alt={alt || 'Producto sin nombre declarado'} loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)}/>;
}

function priceLabel(groups) {
  const group = groups[0];
  if (!group) return {value: 'Precio no declarado', note: ''};
  if (group.minimum != null && group.maximum != null) {
    return {value: `${moneyText(group.minimum, group.currency)} – ${moneyText(group.maximum, group.currency)}`, note: 'Intervalo recibido'};
  }
  const value = group.price_observed ?? group.average;
  return {value: moneyText(value, group.currency, group.offers?.[0]?.currency_symbol), note: group.price_observed != null ? 'Precio observado' : value != null ? 'Media recibida' : ''};
}

function ratingLabel(rating) {
  if (!rating) return 'Valoración no declarada';
  const scale = rating.scale && typeof rating.scale === 'object' && rating.scale.min != null && rating.scale.max != null ? ` de ${rating.scale.max}` : '';
  return `${rating.score ?? '—'}${scale}`;
}

function BrandProduct({entry, designation, onOpen}) {
  const {product, source, image, rating, priceGroups} = entry;
  const price = priceLabel(priceGroups);
  return <article className="cp-brand-product">
    <button type="button" className="cp-brand-product-open" onClick={() => onOpen(source.index, product)} aria-label={`Abrir detalles de ${product.name || 'producto sin nombre'}`}>
      <div className="cp-brand-product-image"><ProductImage src={image} alt={product.name}/><span>{'AB'[source.index] || source.index + 1}</span></div>
      <div className="cp-brand-product-copy">
        <small>{source.label}</small>
        <h3>{product.name || 'Producto sin nombre declarado'}</h3>
        {designation && <strong className="cp-value-tag">{designation}</strong>}
        <dl>
          <div><dt>Precio</dt><dd>{price.value}</dd></div>
          <div><dt>Valoración</dt><dd>{ratingLabel(rating)}</dd></div>
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
      <div><h2 id={`brand-${encodeURIComponent(group.brand)}`}>{group.brand}</h2><p>{group.products.length} producto(s) · {group.sources.length} fuente(s)</p></div>
      <div className="cp-carousel-actions" aria-label={`Navegar na galeria de ${group.brand}`}>
        <button type="button" onClick={() => move(-1)} aria-label={`Productos anteriores de ${group.brand}`}>←</button>
        <button type="button" onClick={() => move(1)} aria-label={`Productos siguientes de ${group.brand}`}>→</button>
      </div>
    </header>
    <div className="cp-brand-carousel" ref={rail} tabIndex="0" aria-label={`Galería de productos de la marca ${group.brand}`}>
      {group.products.map(entry => {const entryKey = `${entry.source.index}:${entry.product.entity_id}`; return <BrandProduct key={entryKey} entry={entry} designation={designations.get(entryKey)} onOpen={onOpen}/>;})}
    </div>
  </section>;
}

export default function BrandGallery({groups, matches, onOpen}) {
  const designations = new Map(matches.flatMap(match => match.designation ? match.entries.map(entry => [`${entry.source.index}:${entry.product.entity_id}`, match.designation]) : []));
  return <section className="cp-brand-gallery" aria-labelledby="brand-gallery-title">
    <header className="cp-brand-section-heading"><div><h2 id="brand-gallery-title">Galería por marca</h2><p>Fotos, nombres, precios y valoraciones permanecen vinculados a la fuente y a los grupos contractuales recibidos.</p></div><span>{groups.length} marca(s)</span></header>
    {!groups.length ? <div className="cp-brand-empty" role="status"><h3>No se encontraron marcas</h3><p>Las marcas aparecerán cuando los datos de la fuente permitan identificarlas.</p></div> : groups.map(group => <BrandRail key={group.brand.toLocaleLowerCase('es')} group={group} designations={designations} onOpen={onOpen}/>)}
  </section>;
}
