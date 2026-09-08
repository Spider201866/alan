const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const context = {module: {exports: {}}};
require('node:vm').runInNewContext(fs.readFileSync(path.join(__dirname, '../viewer/replay-core.js'), 'utf8'), context);
const core = context.module.exports;
const opening = {role: 'health_worker', text: 'old man sore'};
const reply = {role: 'alan', text: '**Check the sore** and ask how long.'};
const events = [
  {case_id: 'DER-042', phase: 'alan', elapsed_ms: 0, messages: [opening]},
  {case_id: 'DER-042', phase: 'judge', elapsed_ms: 12000, messages: [opening, reply]},
  {case_id: 'DER-042', phase: 'complete', elapsed_ms: 25000, messages: [opening, reply], quality: {alan_index: {score: 99}}},
];
const before = JSON.stringify(events);
const cases = [{case_id: 'DER-042', events}];
const frames = core.buildFrames(cases, true, true);
assert.ok(frames.at(-1).end < core.buildFrames(cases, false, true).at(-1).end);
assert.equal(core.sample(frames, 0).messages.length, 1);
assert.equal(core.sample(frames, 0).quality, null);
const reveal = frames.find(f => f.reveal && f.event.messages.length === 2);
assert.ok(core.sample(frames, reveal.start + 1).messages.at(-1).text.length < reply.text.length);
assert.equal(core.sample(frames, frames.at(-1).end).quality.alan_index.score, 99);
assert.equal(core.sample(frames, frames.at(-1).end).messages.at(-1).text, reply.text);
assert.equal(core.sample(frames, 0).quality, null); // scrubbing back hides final scores
assert.equal(JSON.stringify(events), before);
assert.equal(core.sample([], 0), null);
const factCases = [{case_id:'FIRST',events:events.map((e,i)=>({...e,case_id:'FIRST',hw_view_active_ids:i===1?['fact-a']:[]}))},
  {case_id:'SECOND',events:events.map((e,i)=>({...e,case_id:'SECOND',hw_view_active_ids:i===1?['fact-b']:[]}))}];
const factSource = JSON.stringify(factCases);
const factFrames = core.buildFrames(factCases);
assert.equal(JSON.stringify(core.sample(factFrames,0).hw_view_active_ids),'[]');
const firstFinal = factFrames.find(f=>f.event.case_id==='FIRST'&&f.event.phase==='complete');
assert.equal(JSON.stringify(core.sample(factFrames,firstFinal.start).hw_view_active_ids),'["fact-a"]');
const secondStart = factFrames.find(f=>f.event.case_id==='SECOND');
assert.equal(JSON.stringify(core.sample(factFrames,secondStart.start).hw_view_active_ids),'[]');
assert.equal(JSON.stringify(core.sample(factFrames,factFrames.at(-1).end).hw_view_active_ids),'["fact-b"]');
assert.equal(JSON.stringify(factCases),factSource);
console.log('Replay core passed: ordering, seeking, text reveal, no future scores and immutable source.');
