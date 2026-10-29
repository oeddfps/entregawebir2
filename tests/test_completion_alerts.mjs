import test from 'node:test';
import assert from 'node:assert/strict';
import {CompletionWatcher} from '../src/web/components/completion-alerts.mjs';

const start=Date.parse('2026-10-29T20:00:00Z');
const running={comparison_id:'one',status:'running',sources:[{}],stage_timer:{action:'capture',source_index:0,started_at:new Date(start).toISOString(),limit_seconds:30}};

test('timer wins, then processing and completion cannot repeat the notice',()=>{
  const watcher=new CompletionWatcher();
  assert.equal(watcher.observe(running,start+29000),null);
  assert.equal(watcher.observe(running,start+30000).reason,'timeout');
  assert.equal(watcher.observe({...running,stage_timer:{...running.stage_timer,action:'process'}},start+31000),null);
  assert.equal(watcher.observe({...running,status:'done'},start+32000),null);
});

test('search completion wins before the limit',()=>{
  const watcher=new CompletionWatcher();
  watcher.observe(running,start);
  const notice=watcher.observe({...running,status:'done'},start+5000);
  assert.equal(notice.reason,'finished');
  assert.equal(notice.status,'done');
  assert.equal(watcher.observe({...running,status:'done'},start+6000),null);
});

test('opening old results is silent, but a newly started fast job alerts',()=>{
  const watcher=new CompletionWatcher();
  assert.equal(watcher.observe({...running,status:'done'},start+5000),null);
  watcher.watch('one');
  assert.equal(watcher.observe({...running,status:'done'},start+5000).reason,'finished');
});

test('delivery persists across reload and each new run can alert',()=>{
  const watcher=new CompletionWatcher(['one']);
  assert.equal(watcher.observe(running,start+30000),null);
  assert.equal(watcher.observe({...running,comparison_id:'two'},start+30000).reason,'timeout');
});

test('polling after a timeout transition retains the timeout trigger',()=>{
  const watcher=new CompletionWatcher();
  const job={...running,sources:[{stop_reason:'timeout'}],stage_timer:{...running.stage_timer,action:'process',started_at:new Date(start+30000).toISOString()}};
  const notice=watcher.observe(job,start+31000);
  assert.equal(notice.reason,'timeout');
  assert.equal(notice.action,'capture');
  assert.equal(notice.sourceIndex,0);
});

test('processing timeout and terminal failures give accurate notices',()=>{
  const watcher=new CompletionWatcher();
  const job={...running,stage_timer:{...running.stage_timer,action:'process'}};
  assert.equal(watcher.observe(job,start+30000).action,'process');
  for(const status of ['failed','cancelled','interrupted','partial']){
    const next=new CompletionWatcher();
    next.watch('one');
    assert.equal(next.observe({...running,status},start+1000).status,status);
  }
});
