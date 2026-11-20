'use client';

import {useState} from 'react';
import JevCredentials from './jev-credentials';

export function settingsSummary(limits, interpreter) {
  return `${limits.capture_seconds} s de captura · ${limits.processing_seconds} s de procesamiento · ${limits.max_pages == null ? 'visitas sin límite' : `${limits.max_pages} visita(s)`} · ${limits.max_hops == null ? 'saltos sin límite' : `${limits.max_hops} salto(s)`} · ${limits.same_host_only ? 'mismo sitio' : 'otros sitios permitidos'} · ${interpreter === 'jev' ? 'Jev' : 'Datos estructurados'}`;
}

export default function ProcessingSettings({limits, interpreter, onConfirm, onClose}) {
  const [draft,setDraft]=useState({...limits});
  const [method,setMethod]=useState(interpreter);
  function update(key,value){setDraft(old=>({...old,[key]:value}));}
  function preset(values){setDraft(old=>({...old,...values}));}
  function confirm(event){event.preventDefault();onConfirm(draft,method);}
  return <div className="cp-overlay cp-settings-overlay" onClick={onClose}>
    <section className="cp-settings" role="dialog" aria-modal="true" aria-labelledby="cp-settings-title" aria-describedby="cp-settings-description" onClick={event=>event.stopPropagation()}>
      <header><div><h2 id="cp-settings-title">Límites y procesamiento</h2><p id="cp-settings-description">Define cuánto explorar y cómo interpretar los datos de cada fuente.</p></div><button type="button" className="cp-secondary" aria-label="Cerrar parámetros sin aplicar" onClick={onClose}>×</button></header>
      <form onSubmit={confirm}>
        <fieldset><legend>1. Alcance de la captura</legend><p>El tiempo máximo cubre todo el recorrido de cada fuente, incluidas sus páginas y expansiones.</p>
          <div className="cp-presets" aria-label="Opciones rápidas">
            <button type="button" className="cp-secondary" onClick={()=>preset({max_pages:1,max_hops:0,same_host_only:true})}>Solo esta página</button>
            <button type="button" className="cp-secondary" onClick={()=>preset({max_pages:null,max_hops:null,capture_seconds:120,same_host_only:true})}>Explorar durante 2 minutos</button>
            <button type="button" className="cp-secondary" onClick={()=>preset({max_pages:null,max_hops:null,capture_seconds:300,same_host_only:true})}>Explorar durante 5 minutos</button>
          </div>
          <div className="cp-option-fields">
            <label>Tiempo máximo de captura (segundos)<input type="number" required min="5" max="600" step="1" value={draft.capture_seconds??''} onChange={e=>update('capture_seconds',e.target.value===''?null:Number(e.target.value))}/><small>Entre 5 y 600 segundos por fuente.</small></label>
            <label>Máximo de visitas<input type="number" min="1" max="100" step="1" placeholder="Sin límite" value={draft.max_pages??''} onChange={e=>update('max_pages',e.target.value===''?null:Number(e.target.value))}/><small>Incluye la URL inicial y las expansiones. Vacío: sin límite.</small></label>
            <label>Máximo de saltos<input type="number" min="0" max="8" step="1" placeholder="Sin límite" value={draft.max_hops??''} onChange={e=>update('max_hops',e.target.value===''?null:Number(e.target.value))}/><small>0: solo la página inicial. Vacío: sin límite.</small></label>
            <label>Enlaces que se pueden seguir<select value={draft.same_host_only?'host':'all'} onChange={e=>update('same_host_only',e.target.value==='host')}><option value="host">Solo el sitio de la URL inicial</option><option value="all">También otros sitios</option></select></label>
          </div>
        </fieldset>
        <fieldset><legend>2. Procesamiento con Clean&Process</legend><p>Se ejecuta después de la captura y tiene su propio límite de tiempo.</p>
          <div className="cp-option-fields">
            <label>Tiempo máximo de procesamiento (segundos)<input type="number" required min="5" max="600" step="1" value={draft.processing_seconds??''} onChange={e=>update('processing_seconds',e.target.value===''?null:Number(e.target.value))}/><small>Entre 5 y 600 segundos por fuente.</small></label>
            <label>Interpretación<select value={method} onChange={e=>setMethod(e.target.value)}><option value="declared">Datos estructurados</option><option value="jev">Jev · interpretar texto libre</option></select><small>Jev requiere credenciales y puede generar consumo.</small></label>
          </div>{method==='jev'&&<JevCredentials/>}<p>Reseñas y valoraciones: vocabulario multilingüe y E5 local cuando está disponible. Las funciones de las imágenes requieren evidencia visual.</p>
        </fieldset>
        <footer><span>Los cambios se aplican al confirmar y se usan en la próxima ejecución.</span><div><button type="button" className="cp-secondary" onClick={onClose}>Cancelar</button><button type="submit" className="cp-primary">Confirmar parámetros</button></div></footer>
      </form>
    </section>
  </div>;
}
