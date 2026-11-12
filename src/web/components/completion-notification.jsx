'use client';

import {useEffect,useRef,useState} from 'react';
import {CompletionWatcher} from './completion-alerts.mjs';

let audioContext;
const STORAGE_KEY='clean-process:completion-notifications';

// Resume synchronously from a user gesture, before a network request or timer.
export function enableCompletionSound(){
  try{
    const AudioContext=window.AudioContext||window.webkitAudioContext;
    if(!AudioContext)return;
    if(!audioContext||audioContext.state==='closed')audioContext=new AudioContext();
    if(audioContext.state==='suspended')void audioContext.resume().catch(()=>{});
  }catch{} // The visible notification remains available if audio is unsupported.
}

function playSound(){
  if(!audioContext||audioContext.state!=='running')return false;
  try{
    const start=audioContext.currentTime;
    [660,880,1100].forEach((frequency,index)=>{
      const oscillator=audioContext.createOscillator(),gain=audioContext.createGain();
      const at=start+index*.18;
      oscillator.type='sine';oscillator.frequency.value=frequency;
      gain.gain.setValueAtTime(0,at);gain.gain.linearRampToValueAtTime(.12,at+.015);
      gain.gain.exponentialRampToValueAtTime(.001,at+.22);
      oscillator.connect(gain);gain.connect(audioContext.destination);
      oscillator.start(at);oscillator.stop(at+.23);
      oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
    });
    return true;
  }catch{return false;}
}

export function useCompletionNotification(job){
  const watcher=useRef(null);
  if(!watcher.current)watcher.current=new CompletionWatcher();
  const [notice,setNotice]=useState(null);
  useEffect(()=>{
    try{for(const id of JSON.parse(sessionStorage.getItem(STORAGE_KEY)||'[]'))watcher.current.delivered.add(id);}catch{}
    const activate=()=>enableCompletionSound();
    window.addEventListener('pointerdown',activate);
    window.addEventListener('keydown',activate);
    return()=>{window.removeEventListener('pointerdown',activate);window.removeEventListener('keydown',activate);};
  },[]);
  useEffect(()=>{
    if(!job)return;
    const serverNow=Date.parse(job.server_time)||Date.now(),observed=performance.now();
    const check=()=>{
      const next=watcher.current.observe(job,serverNow+performance.now()-observed);
      if(!next)return;
      const source=job.sources[next.sourceIndex];
      setNotice({...next,sourceLabel:source?.label||`Fuente ${'AB'[next.sourceIndex]}`,soundPlayed:playSound()});
      try{sessionStorage.setItem(STORAGE_KEY,JSON.stringify([...watcher.current.delivered]));}catch{}
    };
    check();
    if(!job.stage_timer||watcher.current.delivered.has(job.comparison_id))return;
    const delay=Date.parse(job.stage_timer.started_at)+job.stage_timer.limit_seconds*1000-serverNow;
    if(!Number.isFinite(delay)||delay<=0)return;
    const timeout=setTimeout(check,delay+10);
    return()=>clearTimeout(timeout);
  },[job]);
  function watch(identity){watcher.current.watch(identity);setNotice(null);}
  return {notice,watch,dismiss:()=>setNotice(null)};
}

export default function CompletionNotification({notice,onDismiss}){
  const [played,setPlayed]=useState(false);
  useEffect(()=>setPlayed(false),[notice]);
  if(!notice)return null;
  const titles={done:'La búsqueda terminó',partial:'La búsqueda terminó con resultados parciales',failed:'La búsqueda no pudo completarse',cancelled:'Búsqueda cancelada',interrupted:'Búsqueda interrumpida'};
  return <aside className="cp-completion-notice" role="alert" aria-atomic="true">
    <span className="cp-notice-bell" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg></span><div><strong>{notice.reason==='timeout'?'El timer llegó a cero':titles[notice.status]||'La búsqueda terminó'}</strong><p>{notice.reason==='timeout'?`${notice.action==='capture'?'Capturar':'Procesar'} · ${notice.sourceLabel}. Se alcanzó el tiempo máximo; el análisis puede continuar con las siguientes etapas.`:'Puedes consultar el resultado y los diagnósticos de la ejecución.'}</p>
    {!notice.soundPlayed&&!played&&<button type="button" className="cp-text-button" onClick={()=>{enableCompletionSound();if(audioContext)void audioContext.resume().then(()=>setPlayed(playSound())).catch(()=>{});}}>Reproducir aviso sonoro</button>}</div>
    <button type="button" className="cp-secondary" aria-label="Cerrar notificación" onClick={onDismiss}>×</button>
  </aside>;
}
