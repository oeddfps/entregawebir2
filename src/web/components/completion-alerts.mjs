const TERMINAL=new Set(['done','partial','failed','cancelled','interrupted']);

export function completionNotice(job, now) {
  if(TERMINAL.has(job.status))return {reason:'finished',status:job.status};
  for(let index=0;index<job.sources.length;index++){
    const source=job.sources[index];
    if(source.stop_reason==='timeout')return {reason:'timeout',action:'capture',sourceIndex:index};
    if(source.processing_stop_reason==='timeout')return {reason:'timeout',action:'process',sourceIndex:index};
  }
  const timer=job.stage_timer;
  if(timer&&now>=Date.parse(timer.started_at)+timer.limit_seconds*1000){
    return {reason:'timeout',action:timer.action,sourceIndex:timer.source_index};
  }
  return null;
}

export class CompletionWatcher {
  constructor(delivered=[]) {this.delivered=new Set(delivered);this.watched=new Set();}
  watch(identity){this.watched.add(identity);}
  observe(job, now){
    const id=job.comparison_id;
    if(!TERMINAL.has(job.status))this.watch(id);
    if(!this.watched.has(id)||this.delivered.has(id))return null;
    const notice=completionNotice(job,now);
    if(!notice)return null;
    this.delivered.add(id);
    return {...notice,comparisonId:id};
  }
}
