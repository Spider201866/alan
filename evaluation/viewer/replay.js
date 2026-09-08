(() => {
  'use strict';
  const bridge = window.replayBridge;
  const bar = document.createElement('section');
  bar.className = 'replay-bar';
  bar.setAttribute('aria-label', 'Recorded event replay');
  bar.innerHTML = `<button id="replayStart">Replay run</button><button id="replayExport">Export HTML</button><button id="replayPause" disabled>Pause</button>
    <button id="replayPrevious" disabled aria-label="Previous case">Previous</button><button id="replayNext" disabled aria-label="Next case">Next</button>
    <input id="replaySeek" type="range" min="0" max="1" value="0" step="50" aria-label="Replay timeline" disabled>
    <span id="replayClock">0:00 / 0:00</span><label>Speed <select id="replaySpeed"><option>1</option><option selected>2</option><option>5</option><option>10</option><option>25</option><option>50</option><option>100</option><option>200</option><option>500</option><option>1000</option></select>×</label>
    <label><input id="replayQuick" type="checkbox" checked>Short waits</label><label><input id="replayAnimate" type="checkbox" checked>Animated text</label>
    <button id="replayExit" disabled>Back to live</button><p class="replay-note" id="replayNote">New runs save events automatically. Word reveal is an animation, not original token timing.</p><p class="replay-note" id="replayCoverage" hidden></p>`;
  const provenance = document.querySelector('#runProvenance');
  const tools = document.createElement('div');
  tools.className = 'run-tools';
  provenance.before(tools);
  tools.append(provenance, bar);
  const byId = id => document.getElementById(id);
  const heading = document.querySelector('.worker-view-heading');
  const headingText = document.createElement('div');
  headingText.className = 'worker-heading-text';
  while (heading.firstChild) headingText.append(heading.firstChild);
  heading.append(headingText);
  const mini = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  mini.classList.add('mini-system'); mini.setAttribute('viewBox', '0 0 260 166'); mini.setAttribute('role', 'img');
  mini.innerHTML = `<title>Patient and HW exchange replies with Alan. Judge reviews the completed dialogue.</title>
    <path id="miniUp" d="M130 100 V57 M126 63 L130 57 L134 63"/>
    <path id="miniAcross" d="M104 140 H156 M110 136 L104 140 L110 144 M150 136 L156 140 L150 144"/>
    <g data-phase="judge" class="mini-judge"><rect x="84" y="4" width="92" height="47" rx="13"/><text x="130" y="22">Judge</text><text class="mini-sub" id="miniReport" x="130" y="38">Report · Index</text></g>
    <g data-phase="worker" aria-label="Patient, case filter, health worker"><rect x="3" y="83" width="98" height="78" rx="13"/><text class="mini-patient-label" x="52" y="99">Patient</text><rect class="mini-filter-band" x="3" y="109" width="98" height="20"/><text class="mini-filter-label" x="52" y="123">Case filter</text><text x="52" y="149">HW</text></g>
    <g data-phase="alan"><rect x="159" y="83" width="98" height="78" rx="13"/><text x="208" y="119">Alan</text><text class="mini-sub" x="208" y="137">Dialogue</text></g>`;
  tools.prepend(mini);
  const minimap = document.createElement('aside');
  minimap.id = 'replayMinimap';
  minimap.hidden = true;
  minimap.setAttribute('aria-label', 'All cases in this run');
  minimap.innerHTML = '<span class="replay-map-count"></span><div class="replay-map-lines" role="group" aria-label="Choose a recorded case"></div>';
  const caseSection = document.createElement('div');
  caseSection.className = 'replay-case-section';
  const caseGrid = document.getElementById('caseGrid');
  caseGrid.before(caseSection);
  caseSection.append(caseGrid, minimap);
  function positionMinimap() {
    if (minimap.hidden) return;
    const top = Math.max(108, caseSection.getBoundingClientRect().top);
    minimap.style.height = `${Math.min(mapLines.children.length * 4 + 34, Math.max(120, window.innerHeight - top - 16))}px`;
  }
  window.addEventListener('resize', positionMinimap);
  window.addEventListener('scroll', positionMinimap, {passive: true});
  const mapLines = minimap.querySelector('.replay-map-lines');
  function updateMinimap(cases, currentId) {
    minimap.hidden = cases.length < 2;
    document.body.classList.toggle('has-replay-map', cases.length > 1);
    if (mapLines.children.length !== cases.length || mapLines.dataset.run !== run) {
      mapLines.replaceChildren(...cases.map(c => {
        const button = document.createElement('button');
        button.type = 'button'; button.dataset.caseId = c.case_id;
        return button;
      }));
      mapLines.dataset.run = run;
      mapLines.style.gridTemplateRows = `repeat(${cases.length}, minmax(0, 1fr))`;
    }
    cases.forEach((c, index) => {
      const button = mapLines.children[index], current = c.case_id === currentId;
      button.dataset.status = c.status;
      button.setAttribute('aria-current', String(current));
      button.tabIndex = current ? 0 : -1;
      button.title = `${index + 1} · ${c.case_id} · ${current ? 'current case' : c.status === 'complete' ? 'played' : 'not yet played'}`;
      button.setAttribute('aria-label', button.title);
    });
    minimap.querySelector('.replay-map-count').textContent = `${cases.findIndex(c => c.case_id === currentId) + 1}/${cases.length}`;
  }
  mapLines.onclick = e => {
    const button = e.target.closest('button[data-case-id]');
    if (button) seekCase(button.dataset.caseId);
  };
  mapLines.onkeydown = e => {
    const button = e.target.closest('button[data-case-id]');
    if (!button || !['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    const buttons = [...mapLines.children], index = buttons.indexOf(button);
    const next = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, index + (e.key === 'ArrowDown' ? 1 : -1)));
    seekCase(buttons[next].dataset.caseId);
    buttons[next].focus({preventScroll: true});
  };
  let active = false, playing = false, frames = [], payload = null, position = 0, lastTick = 0, lastRender = 0, run = '', loading = false;
  let sidebarSignature = '';
  let finalEvents = new Map();
  const clock = ms => `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;
  function updateMini(item) {
    const phase = item?.status === 'complete' ? 'complete' : item?.hw_view_phase || 'idle';
    for (const node of mini.querySelectorAll('[data-phase]')) node.classList.toggle('active', node.dataset.phase === phase);
    byId('miniAcross').classList.toggle('active-link', phase === 'alan' || phase === 'worker');
    byId('miniUp').classList.toggle('active-link', phase === 'judge');
    byId('miniReport').textContent = phase === 'complete' && item?.quality?.test_check ? item.quality.test_check.outcome.toUpperCase() : phase === 'complete' && item?.quality?.alan_index?.applicable ? `Index ${item.quality.alan_index.score}` : 'Report · Index';
    mini.setAttribute('aria-label', phase === 'complete' ? 'Case complete; judge report ready' : `${phase === 'worker' ? 'Health worker' : phase} active`);
  }
  function controls() {
    for (const id of ['replayPause', 'replayPrevious', 'replayNext', 'replaySeek', 'replayExit']) byId(id).disabled = !active;
    byId('replayPause').textContent = playing ? 'Pause' : 'Play';
    byId('replayStart').disabled = loading || active;
    byId('replaySeek').max = String(frames.at(-1)?.end || 1);
  }
  function render() {
    if (!active) return;
    const event = window.AlanReplayCore.sample(frames, position);
    if (!event) return;
    const signature = `${run}|${event.case_id}|${event.phase === 'complete'}`;
    let sidebar;
    if (signature !== sidebarSignature) {
      const current = payload.cases.findIndex(c => c.case_id === event.case_id);
      sidebar = payload.cases.map((c, index) => {
        const saved = index < current ? finalEvents.get(c.case_id) : index === current ? event : null;
        const metadata = bridge.state()?.cases?.find(item => item.case_id === c.case_id) || {};
        return {case_id:c.case_id, case_index:index + 1, replay:true,
          repeat:metadata.repeat, repeat_position:metadata.repeat_position, source_case_id:metadata.source_case_id,
          status:index < current || (index === current && event.phase === 'complete') ? 'complete' : index === current ? 'running' : 'queued',
          quality:saved?.quality || null, judge:saved?.judge || null,
          diagnosis:index < current ? (window.offlineReplay?.caseTitles?.[c.case_id] || '') : '',
          activity:'Playing recorded dialogue'};
      });
      sidebarSignature = signature;
      updateMinimap(sidebar, event.case_id);
    }
    const item = bridge.render(event, run, sidebar);
    updateMini(item);
    positionMinimap();
    byId('replaySeek').value = String(position);
    byId('replayClock').textContent = `${clock(position)} / ${clock(frames.at(-1).end)}`;
    byId('replayNote').textContent = `Replay · ${run} · ${event.case_id} · recorded events; word reveal is an animation. No models are being called.${event.recovered ? ' Final result recovered from the saved case.' : ''}`;
  }
  function rebuild() {
    const fraction = position / (frames.at(-1)?.end || 1);
    frames = window.AlanReplayCore.buildFrames(payload?.cases || [], byId('replayQuick').checked, byId('replayAnimate').checked);
    position = fraction * (frames.at(-1)?.end || 0);
    controls(); render();
  }
  async function start() {
    if (loading || active) return;
    if (bridge.recording()) { byId('replayNote').textContent = 'Stop screen recording before starting replay.'; return; }
    const selected = bridge.state();
    if (!selected?.run) return;
    if (!window.offlineReplay && (bridge.isRunning?.() || selected.cases?.some(c => c.status === 'running'))) { byId('replayNote').textContent = 'Let the live run finish before replaying it. You can export a clearly labelled partial snapshot meanwhile.'; return; }
    loading = true; controls();
    try {
      let data = window.offlineReplay;
      if (!data) {
        const response = await fetch(`/api/replay?run=${encodeURIComponent(selected.run)}`, {cache: 'no-store'});
        data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Replay could not be loaded');
      }
      if (!window.offlineReplay && data.run_active) throw new Error('Let the live run finish before replaying it.');
      const complete = data.cases.filter(c => c.complete);
      byId('replayCoverage').textContent = window.AlanReplayCore.coverageSummary(data);
      byId('replayCoverage').hidden = false;
      if (!complete.length) throw new Error('No completed recording is available yet. See the case counts below.');
      payload = {...data, cases: complete}; run = data.run; position = 0; frames = [];
      bridge.reserveWorkerView(complete.flatMap(c => c.events.map(e => e.hw_view || [])), run);
      sidebarSignature = '';
      finalEvents = new Map(complete.map(c => [c.case_id, [...c.events].reverse().find(e => e.phase === 'complete')]));
      active = true; playing = true; document.body.classList.add('replay-mode'); lastTick = performance.now(); rebuild();
    } catch (error) { byId('replayNote').textContent = error.message; }
    finally { loading = false; controls(); }
  }
  function seek(value) { position = Math.max(0, Math.min(Number(value), frames.at(-1)?.end || 0)); lastTick = performance.now(); render(); }
  function jump(direction) {
    const event = window.AlanReplayCore.sample(frames, position);
    const ids = payload.cases.map(c => c.case_id);
    const target = ids[Math.max(0, Math.min(ids.length - 1, ids.indexOf(event.case_id) + direction))];
    seek(frames.find(f => f.event.case_id === target).start);
  }
  function seekCase(caseId) {
    if (!active) {
      const button = [...document.querySelectorAll('#caseList [data-select-case]')].find(b => b.dataset.selectCase === caseId);
      button?.click(); return;
    }
    const frame = frames.find(f => f.event.case_id === caseId);
    if (frame) seek(frame.start);
  }
  byId('replayStart').onclick = start;
  byId('replayExport').hidden = Boolean(window.offlineReplay);
  byId('replayExport').onclick = async () => {
    const button = byId('replayExport');
    button.disabled = true;
    try {
      const selectedRun = active ? run : bridge.state()?.run;
      if (!selectedRun) throw new Error('Select a recorded run first.');
      const exported = await window.AlanReplayExport.download(selectedRun);
      byId('replayNote').textContent = `Exported ${exported.count}/${exported.expected} cases as one HTML file.${exported.count < exported.expected ? ' This is a partial export.' : ''} Open it in a browser to replay offline.`;
      byId('replayCoverage').textContent = exported.summary;
      byId('replayCoverage').hidden = false;
    } catch (error) { byId('replayNote').textContent = error.message; }
    finally { button.disabled = false; }
  };
  byId('replayPause').onclick = () => { if (position >= frames.at(-1).end) position = 0; playing = !playing; lastTick = performance.now(); controls(); render(); };
  byId('replayPrevious').onclick = () => jump(-1); byId('replayNext').onclick = () => jump(1);
  byId('replaySeek').oninput = e => seek(e.target.value);
  byId('replayQuick').onchange = () => { if (active) rebuild(); };
  byId('replayAnimate').onchange = () => { if (active) rebuild(); };
  byId('replayExit').onclick = () => { active = false; playing = false; minimap.hidden = true; document.body.classList.remove('replay-mode', 'has-replay-map'); controls(); byId('replayCoverage').hidden = !window.offlineReplay; byId('replayNote').textContent = window.offlineReplay ? 'Saved results · offline snapshot. Replay uses recorded events; no models are called.' : 'Live viewer · new runs save events automatically.'; bridge.exit(); };
  function tick(now) {
    if (active && playing) {
      position = Math.min(frames.at(-1).end, position + (now - lastTick) * Number(byId('replaySpeed').value));
      if (now - lastRender >= 50 || position >= frames.at(-1).end) { render(); lastRender = now; }
      if (position >= frames.at(-1).end) { playing = false; controls(); }
    }
    lastTick = now; requestAnimationFrame(tick);
  }
  window.AlanReplay = {get active() { return active; }, updateLive(item, cases = []) { updateMini(item); updateMinimap(cases, item?.case_id); positionMinimap(); }, seekCase};
  controls(); requestAnimationFrame(tick);
  if (window.offlineReplay) {
    byId('replayExit').textContent = 'View results';
    document.querySelector('#followButton').hidden = true;
    document.querySelector('#runSelect').disabled = true;
    document.querySelector('#runPickerButton').disabled = true;
    start();
  }
})();
