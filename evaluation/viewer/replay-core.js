(function (root) {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  function buildFrames(cases, quick = true, animate = true) {
    const frames = [];
    let end = 0;
    const add = (event, duration, reveal = false) => {
      duration = Math.max(1, duration);
      frames.push({event, start: end, end: end + duration, reveal});
      end += duration;
    };
    for (const item of cases) {
      let previous = null;
      const accessed = new Set();
      for (const recorded of item.events) {
        for (const id of recorded.hw_view_active_ids || []) accessed.add(String(id));
        // Access is cumulative within a case, but never borrowed from a later
        // event or another case. The original recording remains unchanged.
        const event = {...recorded, hw_view_active_ids: [...accessed], hw_view_reply_ids: []};
        if (previous) {
          const gap = Math.max(0, event.elapsed_ms - previous.elapsed_ms);
          if (gap) add(previous, quick ? Math.min(gap, 1600) : gap);
        }
        const before = previous?.messages?.length || 0;
        for (let i = before; i < event.messages.length; i++) {
          const visible = {...event, phase: event.messages[i].role === 'alan' ? 'alan' : 'worker',
            hw_view_reply_ids: event.messages[i].role === 'health_worker' ? (recorded.hw_view_active_ids || []) : [],
            messages: event.messages.slice(0, i + 1), quality: null, judge: null};
          const words = event.messages[i].text.trim().split(/\s+/).length;
          add(visible, animate ? Math.max(500, words * 130) : 700, animate);
        }
        if (event.phase === 'complete') add(event, 4000);
        previous = event;
      }
    }
    return frames;
  }
  function sample(frames, position) {
    if (!frames.length) return null;
    const frame = frames.find(f => position < f.end) || frames.at(-1);
    const event = copy(frame.event);
    if (frame.reveal) {
      const message = event.messages.at(-1);
      // Animation is presentation only, not a claim about token timestamps.
      const text = message.text.replace(/\*\*([^*\n]+)\*\*/g, '$1').replace(/_([^_\n]+)_/g, '$1').replace(/\*([^*\n]+)\*/g, '$1');
      const words = text.trim().split(/\s+/);
      const progress = Math.max(0, Math.min(1, (position - frame.start) / (frame.end - frame.start)));
      const count = Math.max(1, Math.ceil(progress * words.length));
      if (count < words.length) message.text = words.slice(0, count).join(' ');
    }
    return event;
  }
  function coverageSummary(data) {
    const cases = data.cases || [];
    const coverage = data.coverage || {expected: cases.length, complete: cases.filter(c => c.complete).length};
    const omitted = data.omissions || cases.filter(c => !c.complete).map(c => ({case_id:c.case_id, status:c.status || 'unfinished'}));
    return `${coverage.complete}/${coverage.expected} cases recorded${coverage.complete < coverage.expected ? ' · Partial recording' : ''}.`
      + (omitted.length ? ` Excluded: ${omitted.map(c => `${c.case_id} (${c.status})`).join(', ')}.` : '')
      + (coverage.recovered ? ` ${coverage.recovered} final result(s) recovered from saved case results.` : '');
  }
  const api = {buildFrames, sample, coverageSummary};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AlanReplayCore = api;
})(typeof window === 'undefined' ? globalThis : window);
