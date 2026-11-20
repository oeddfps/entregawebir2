'use client';

import {useEffect, useRef, useState} from 'react';

const endpoint='/api/service/credentials/jev';

export default function JevCredentials({onConfigured}) {
  const [status,setStatus]=useState({configured:false,editable:true}),[key,setKey]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const callback=useRef(onConfigured);
  callback.current=onConfigured;
  async function request(options){
    const response=await fetch(endpoint,{cache:'no-store',...options});
    const data=await response.json().catch(()=>null);
    if(!response.ok||typeof data?.configured!=='boolean'||typeof data?.editable!=='boolean')throw new Error(typeof data?.detail==='string'?data.detail:'No se pudo consultar la configuración de Jev.');
    return data;
  }
  useEffect(()=>{let alive=true;request().then(data=>{if(!alive)return;setStatus(data);if(data.configured)callback.current?.();}).catch(()=>{});return()=>{alive=false;};},[]);
  async function save(event){
    event.preventDefault();event.stopPropagation();if(busy||!key.trim())return;setBusy(true);setError('');setMessage('');
    try{
      const next=await request({method:'PUT',headers:{'Content-Type':'application/json','X-Jev-Configuration':'1'},body:JSON.stringify({api_key:key.trim()})});
      setStatus(next);setKey('');setMessage('Clave guardada. Jev está disponible para las próximas ejecuciones.');callback.current?.();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <section className="jev-credentials panel" aria-label="Configuración de Jev">
    <details open={status&&!status.configured?true:undefined}>
      <summary><strong>Jev</strong> · {status?(status.configured?'Clave configurada':'Configura tu clave API'):'Consultando configuración…'}</summary>
      <p>{status?.configured?'La clave se utiliza en las próximas extracciones y análisis.':'Pega tu clave API para habilitar la interpretación con Jev en las extracciones y comparaciones.'}</p>
      {status?.editable&&<div role="group" aria-label="Credencial de Jev"><label>Clave API de Jev<input type="password" name="jev-api-key" autoComplete="off" spellCheck={false} maxLength={4096} value={key} onChange={event=>setKey(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();event.stopPropagation();if(!event.nativeEvent.isComposing)save(event);}}} placeholder="Pega tu clave API"/></label><button className="primary" type="button" onClick={save} disabled={busy||!key.trim()}>{busy?'Guardando…':status.configured?'Actualizar clave Jev':'Guardar clave Jev'}</button></div>}
      {status&&!status.editable&&<p>La credencial está administrada por el entorno del servidor.</p>}
      <small>Se guarda solo en el servidor, fuera de Git. No se guarda en el almacenamiento del navegador. La validez se comprueba al usar Jev.</small>
    </details>
    {error&&<p className="error-banner" role="alert">{error}</p>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
