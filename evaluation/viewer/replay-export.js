(() => {
  'use strict';
  function identity(run, state, partial = false) {
    const count = (state.cases || []).length;
    const display = runDisplay({name:run, case_count:count, started_at:state.manifest?.started_at});
    const title = `Alan · ${count} ${count === 1 ? 'case' : 'cases'} · ${display.title}${partial ? ' · Partial replay' : ''}`;
    const date = display.date.replace(/ · run 1$/, '').replace('Sept', 'Sep').replace(/^(\d) /, '0$1 ');
    const clean = text => text.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '').replace(/[·–—]/g, '-').replace(/\s+/g, ' ').trim();
    const filename = `Alan ${count} - ${clean(date)}${partial ? ' - partial' : ''}.html`;
    return {title, filename};
  }
  // Bundle the actual viewer, not a second report implementation.
  async function download(run) {
    async function asset(path, json = false) {
      const response = await fetch(path, {cache:'no-store'});
      if (!response.ok) throw new Error('Could not load the export: ' + path);
      return json ? response.json() : response.text();
    }
    const [data, state, source, css, core, player] = await Promise.all([
      asset(`/api/replay?run=${encodeURIComponent(run)}`, true),
      asset(`/api/state?run=${encodeURIComponent(run)}`, true),
      asset('/index.html'), asset('/replay.css'), asset('/replay-core.js'), asset('/replay.js')
    ]);
    if (state.run !== run || data.run !== run || !state.manifest) throw new Error('Run information changed; please export again.');
    const cases = data.cases.filter(c => c.complete);
    if (!cases.length) throw new Error('No completed recording to export yet.');
    const coverage = data.coverage || {expected:data.cases.length, complete:cases.length};
    const omissions = data.cases.filter(c => !c.complete).map(c => ({case_id:c.case_id,status:c.status || 'unfinished'}));
    // Only display metadata, never local paths, prompts or model call traces.
    const manifest = {};
    for (const key of ['started_at','finished_at','alan_source_type','alan_version','alan_version_date','model','reasoning_effort','model_transport','worker_model','worker_reasoning_effort','worker_transport','judge_model','judge_reasoning_effort','judge_transport','runner_version','scorer_version','worker_prompt_version','judge_prompt_version','route']) {
      if (state.manifest[key] !== undefined) manifest[key] = state.manifest[key];
    }
    manifest.rejudged_saved_dialogues = Boolean(state.manifest.display_consolidation || state.manifest.rejudged_saved_dialogues);
    if (state.manifest.display_consolidation) manifest.display_consolidation = Object.fromEntries(
      ['kind','source_run','changed_cases','clinical_review_prompt_sha256','worker_audit_prompt_sha256','description','rerun_cases','adjudicated_cases','case_sources','assessment_source_run','updated_at'].filter(key => state.manifest.display_consolidation[key] !== undefined).map(key => [key,state.manifest.display_consolidation[key]]));
    manifest.separate_worker_audit = Boolean(state.manifest.separate_worker_audit);
    if (state.manifest.extra_input_sha256?.['worker_audit.txt']) manifest.extra_input_sha256 = {'worker_audit.txt':state.manifest.extra_input_sha256['worker_audit.txt']};
    for (const [name, keys] of [
      ['assessment_contract', ['clinical_judge','screening','diagnostic_cases','screening_cases','headline_denominator']],
      ['explicit_configuration', ['id','sha256','versions','assessment_denominators']]
    ]) {
      if (state.manifest[name]) manifest[name] = Object.fromEntries(keys.filter(key => state.manifest[name][key] !== undefined).map(key => [key,state.manifest[name][key]]));
    }
    manifest.quality_scoring_version = state.manifest.quality_scoring_version;
    manifest.challenge_index_version = state.manifest.challenge_index_version;
    for (const key of ['case_ids','case_count_per_arm','arms','concurrency','cases_sha256','workbook_sha256','alan_prompt_sha256','worker_prompt_sha256','judge_prompt_sha256','worker_prompt_label','worker_guard_sha256']) {
      if (state.manifest[key] !== undefined) manifest[key] = state.manifest[key];
    }
    if (state.manifest.evaluation_profile) {
      manifest.evaluation_profile = Object.fromEntries(['name','alan','worker','runner','clinical_scorer','challenge_judge','challenge_scorer','cohort'].filter(key => typeof state.manifest.evaluation_profile[key] === 'string').map(key => [key, state.manifest.evaluation_profile[key]]));
    }
    const comparison = state.manifest.hw_comparison || state.manifest.evaluation_profile?.hw_comparison;
    if (comparison) {
      manifest.hw_comparison = Object.fromEntries(
        ['arm','candidate_schema_strategy','policy','adapter_sha256','plan_sha256']
          .filter(key => typeof comparison[key] === 'string').map(key => [key, comparison[key]]));
      if (Number.isInteger(comparison.repeat)) manifest.hw_comparison.repeat = comparison.repeat;
    }
    // Retain the same public result view as the live page, including invalidity.
    // Exclude raw traces, local file paths and unused model-call metadata.
    const reviewCases = (state.cases || []).map(item => {
      const safe = {};
      for (const key of ['case_id','case_index','case_total','repeat','repeat_position','source_case_id','domain','diagnosis','status','quality','judge','hw_view','hw_view_active_ids','hw_view_phase','hw_view_turn','hw_view_reason','turns','duration_ms','activity','active_since','started_at','stop_reason','modified']) {
        if (item[key] !== undefined) safe[key] = item[key];
      }
      safe.messages = (item.messages || []).map(({role,text,opening,scripted_challenge}) => ({role,text,opening,scripted_challenge}));
      safe.retries = [];
      if (item.case_review) safe.case_review = Object.fromEntries(
        ['status','owner','finding','action','decision'].filter(key => typeof item.case_review[key] === 'string')
          .map(key => [key, item.case_review[key]]));
      safe.failure = item.failure ? 'Runner failure — see the original run log for details.' : null;
      return safe;
    });
    const payload = {...data, cases, coverage, omissions, omitted:coverage.expected-cases.length,
      theme: document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
      exported_at: new Date().toISOString(),
      caseTitles:Object.fromEntries((state.cases || []).filter(c => c.status === 'complete').map(c => [c.case_id,c.diagnosis || ''])),
      viewerState:{next_configuration:state.next_configuration || null,worker_view_layout:state.worker_view_layout || [],run,manifest,runner_defaults:manifest,runs:[{name:run}],cases:reviewCases,status_counts:state.status_counts || {},recording:null,
        invalid:Boolean(state.invalid),stop_requested:Boolean(state.stop_requested),last_activity_at:state.last_activity_at,generated_at:state.generated_at}
    };
    const viewer = new DOMParser().parseFromString(source, 'text/html');
    const exportedIdentity = identity(run, state, payload.omitted > 0);
    viewer.title = exportedIdentity.title;
    const fontResponse = await fetch('/fonts/Quicksand-Variable.ttf', {cache:'no-store'});
    if (!fontResponse.ok) throw new Error('Could not load the Alan logo font.');
    const fontBlob = await fontResponse.blob();
    const fontData = await new Promise((resolve,reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject;
      reader.readAsDataURL(fontBlob);
    });
    for (const style of viewer.querySelectorAll('style')) style.textContent = style.textContent.replaceAll('./fonts/Quicksand-Variable.ttf', fontData);
    const policy = viewer.createElement('meta');
    policy.httpEquiv = 'Content-Security-Policy';
    policy.content = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; font-src data:; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'";
    viewer.head.prepend(policy);
    for (const link of viewer.querySelectorAll('link[rel="stylesheet"]')) {
      if (!link.getAttribute('href').includes('replay.css')) throw new Error('An unbundled viewer stylesheet was found.');
      const style = viewer.createElement('style'); style.textContent = css; link.replaceWith(style);
    }
    const mainScript = viewer.querySelector('script:not([src])');
    const recorded = viewer.createElement('script'); recorded.type = 'application/json'; recorded.id = 'recordedData';
    recorded.textContent = JSON.stringify(payload).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
    const bootstrap = viewer.createElement('script');
    bootstrap.textContent = "window.offlineReplay = JSON.parse(document.getElementById('recordedData').textContent);";
    mainScript.before(recorded, bootstrap);
    for (const script of viewer.querySelectorAll('script[src]')) {
      const src = script.getAttribute('src').split('?')[0];
      if (src === '/replay-export.js') {script.remove(); continue;}
      const text = src === '/replay-core.js' ? core : src === '/replay.js' ? player : null;
      if (text === null) throw new Error('An unbundled viewer script was found.');
      script.removeAttribute('src'); script.textContent = text.replace(/<\/script/gi,'<\\/script');
    }
    const html = '<!doctype html>\n' + viewer.documentElement.outerHTML;
    const url = URL.createObjectURL(new Blob([html], {type:'text/html;charset=utf-8'}));
    const a = document.createElement('a');
    a.href = url; a.download = exportedIdentity.filename;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url),60000);
    return {count:cases.length,expected:coverage.expected,summary:window.AlanReplayCore.coverageSummary(payload)};
  }
  window.AlanReplayExport = {download, identity};
})();
