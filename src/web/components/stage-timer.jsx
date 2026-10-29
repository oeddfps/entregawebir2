'use client';

import {useEffect, useState} from 'react';

const TERMINAL=new Set(['done','partial','failed','cancelled','interrupted']);
const formatTime=seconds=>`${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toString().padStart(2,'0')}`;

export default function StageTimer({job}) {
  const timer=job.stage_timer;
  const finished=TERMINAL.has(job.status);
  const [clock,setClock]=useState({local:Date.now(),server:Date.parse(job.server_time)||Date.now()});
  const [tick,setTick]=useState(Date.now());
  useEffect(()=>{
    const local=Date.now();
    setClock({local,server:Date.parse(job.server_time)||local});
    setTick(local);
  },[job.server_time]);
  useEffect(()=>{
    if(finished||!timer)return;
    const interval=setInterval(()=>setTick(Date.now()),250);
    return()=>clearInterval(interval);
  },[finished,timer?.started_at]);
  if(!timer){
    if(finished)return null; // Saved runs from before timers remain readable.
    return <div className="cp-stage-timer cp-timer-pending"><span className="cp-timer-ring" aria-hidden="true"/><div><strong>Preparando</strong><p>El contador comenzará al iniciar la etapa.</p></div></div>;
  }
  const limit=timer.limit_seconds;
  const now=finished?Date.parse(job.finished_at):clock.server+Math.max(0,tick-clock.local);
  const elapsed=Math.max(0,(now-Date.parse(timer.started_at))/1000);
  const remaining=finished?0:Math.max(0,Math.ceil(limit-elapsed));
  const progress=job.status==='done'?1:Math.min(1,elapsed/limit);
  const action=timer.action==='capture'?'Capturar':'Procesar';
  const source=job.sources[timer.source_index];
  const heading=finished?(job.status==='done'?'Finalizado':job.status==='cancelled'?'Cancelado':job.status==='partial'?'Finalizado con resultados parciales':'Detenido'):job.phase==='cancelling'?'Deteniendo':action;
  const radius=42,circumference=2*Math.PI*radius;
  return <div className={'cp-stage-timer'+(finished?' cp-timer-finished':'')}>
    <div className="cp-timer-ring" role="progressbar" aria-label={`${action} · fuente ${'AB'[timer.source_index]} · tiempo de la etapa`} aria-valuemin={0} aria-valuemax={limit} aria-valuenow={finished&&job.status==='done'?limit:Math.min(limit,Math.floor(elapsed))} aria-valuetext={finished?heading:`${formatTime(remaining)} restantes del límite de ${formatTime(limit)}`}>
      <svg viewBox="0 0 100 100" aria-hidden="true"><circle className="cp-timer-track" cx="50" cy="50" r={radius}/><circle className="cp-timer-fill" cx="50" cy="50" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference*(1-progress)}/></svg>
      <span className="cp-timer-value">{formatTime(remaining)}</span>
    </div>
    <div className="cp-timer-copy"><span className="cp-timer-caption">Acción</span><strong aria-live="polite">{heading}</strong><p>{'AB'[timer.source_index]} · {source?.label||'Fuente '+ 'AB'[timer.source_index]}</p><span className="cp-timer-caption">Tiempo restante</span><p>{finished?'Esta ejecución terminó.':remaining===0?'Límite alcanzado; cerrando la etapa…':`${formatTime(remaining)} de un máximo de ${formatTime(limit)}`}</p><small>{finished?`Última acción: ${action}.`:'Cuenta hasta el límite configurado. La etapa puede terminar antes.'}</small></div>
  </div>;
}
