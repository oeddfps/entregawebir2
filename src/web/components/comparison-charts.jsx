'use client';

import {useState} from 'react';

const number = value => new Intl.NumberFormat('es-UY').format(value);
const METRICS = [['products','Productos identificados'],['image_uses','Usos de imágenes'],['textual_reviews','Reseñas textuales únicas'],['offers','Ofertas registradas']];

function GroupedChart({title,note,groups,names}) {
  const values=groups.flatMap(g=>g.values).filter(v=>v!=null);
  const rawMax=Math.max(1,...values);
  const step=Math.max(1,10**Math.floor(Math.log10(rawMax))/2);
  const maximum=Math.ceil(rawMax/step)*step;
  const left=48,top=26,height=180,width=560,plot=480;
  const ticks=Math.min(4,maximum);
  const band=plot/Math.max(1,groups.length),bar=Math.min(64,band*.3);
  return <section className="cp-card cp-comparative-chart">
    <header className="cp-card-heading"><div><h2>{title}</h2><p>{note}</p></div></header>
    <div className="cp-chart-legend">{names.map((name,i)=><span key={i} className={'cp-source-'+i}><i className="cp-dot"/>{'AB'[i]} · {name}</span>)}</div>
    {values.length?<svg viewBox={`0 0 ${width} 260`} role="img" aria-label={`${title}. ${groups.map(g=>`${g.label}: ${names.map((n,i)=>`${n}, ${g.values[i]==null?'sin datos':number(g.values[i])}`).join('; ')}`).join('. ')}`}>
      {Array.from({length:ticks+1},(_,t)=>t).map(t=>{const y=top+height-height*t/ticks;return <g key={t}><line x1={left} x2={left+plot} y1={y} y2={y} stroke="#e5e8ed"/><text x={left-8} y={y+4} textAnchor="end" className="cp-axis-text">{number(Math.round(maximum*t/ticks))}</text></g>;})}
      {groups.map((g,j)=><g key={g.label}>{g.values.map((v,i)=>{const x=left+band*(j+.5)+(i-1)*bar+3,y=top+height-(v??0)/maximum*height;return <g key={i} className={'cp-source-'+i}>
        <rect x={x} y={y} width={bar-6} height={v==null?0:Math.max(0,top+height-y)} rx="4" fill="var(--cp-color)"><title>{names[i]} · {g.label}: {v==null?'Sin datos':number(v)}</title></rect>
        <text x={x+(bar-6)/2} y={y-7} textAnchor="middle" className="cp-value-text">{v==null?'—':number(v)}</text>
      </g>;})}<text x={left+band*(j+.5)} y={top+height+25} textAnchor="middle" className="cp-axis-text">{g.label}</text></g>)}
    </svg>:<p className="cp-chart-no-data">Los datos aparecerán cuando termine el procesamiento.</p>}
    <details className="cp-chart-table"><summary>Ver valores de la gráfica</summary><table><thead><tr><th>Indicador</th>{names.map((n,i)=><th key={i}>{n}</th>)}</tr></thead><tbody>{groups.map(g=><tr key={g.label}><th scope="row">{g.label}</th>{g.values.map((v,i)=><td key={i}>{v==null?'Sin datos':number(v)}</td>)}</tr>)}</tbody></table></details>
  </section>;
}

export default function ComparisonCharts({results,names}) {
  const [metric,setMetric]=useState('products');
  const metricTitle=METRICS.find(([key])=>key===metric)[1];
  const count=(result,predicate)=>result?result.products.filter(predicate).length:null;
  const imageGroups=[['Sin imágenes',0,0],['1 imagen',1,1],['2–4 imágenes',2,4],['5 o más',5,Infinity]].map(([title,min,max])=>({label:title,values:results.map(r=>count(r,p=>{const n=p.images?.length||0;return n>=min&&n<=max;}))}));
  const reviewGroups=[{label:'Con reseñas',values:results.map(r=>count(r,p=>p.reviews?.length>0))},{label:'Sin reseñas',values:results.map(r=>count(r,p=>!p.reviews?.length))}];
  return <section className="cp-comparison-charts" aria-label="Gráficas comparativas">
    <div className="cp-graph-heading"><div><h2>Comparación entre fuentes</h2><p>La misma escala y los mismos indicadores para A y B.</p></div><label>Indicador<select aria-label="Indicador de comparación" value={metric} onChange={e=>setMetric(e.target.value)}>{METRICS.map(([key,title])=><option key={key} value={key}>{title}</option>)}</select></label></div>
    <GroupedChart title={metricTitle} note="Cantidades registradas en esta captura. Las identidades de producto son provisionales." groups={[{label:metricTitle,values:results.map(r=>r?.summary?.[metric]??null)}]} names={names}/>
    <div className="cp-chart-grid"><GroupedChart title="Imágenes por producto" note="Distribución de los usos de imágenes asociados a cada identidad." groups={imageGroups} names={names}/><GroupedChart title="Productos con reseñas textuales" note="Presencia de textos asociados; no representa satisfacción ni el total de votos publicados." groups={reviewGroups} names={names}/></div>
    <p className="cp-muted">Se compara la muestra capturada. Los valores cero son distintos de los datos pendientes (—). Las capturas parciales y el contenido externo pueden afectar los resultados.</p>
  </section>;
}
