#!/usr/bin/env python3
"""Alan evaluation v1: check, run, resume and view recorded evaluations."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
try:
    import runner
    from case_bank import load_cases, select_cases
    from release_config import load_config, display_config
except ModuleNotFoundError as exc:
    raise SystemExit('Missing dependency. Run: python -m pip install -r requirements.txt') from exc


def run_path(config, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name):
        raise ValueError('Use letters, digits, hyphens or underscores for the run name')
    parent=Path(config['_runs']).resolve()
    dest=(parent/name).resolve()
    if not dest.is_relative_to(parent): raise ValueError('Run path leaves the configured runs folder')
    return dest


def check(config, require_codex=False):
    cases=load_cases()
    for name in ('health_worker','judge','worker_audit','challenge_judge'):
        prompt=ROOT/'prompts'/f'{name}.txt'
        schema=ROOT/'schemas'/f'{name}.json'
        if not prompt.read_text(encoding='utf-8').strip(): raise ValueError(f'Empty {prompt.name}')
        if json.loads(schema.read_text(encoding='utf-8')).get('type')!='object': raise ValueError(f'Invalid {schema.name}')
    if not (ROOT/'prompts/alan.txt').read_text(encoding='utf-8').strip(): raise ValueError('Empty Alan prompt')
    print('Case bank: 250 unique cases (200 clinical + 50 challenge)')
    print('Prompts and schemas: present; worker view excludes gold fields')
    print('Alan v0.2.0; harness components v1; recording enabled')
    codex=shutil.which('codex.cmd') or shutil.which('codex')
    if not codex:
        if require_codex: raise ValueError('Codex CLI is missing. Install it and sign in before running cases.')
        print('Codex CLI: not installed; offline viewer and local tests remain available')
        return
    # Help and sign-in checks do not invoke a model or read credentials.
    version=subprocess.run([codex,'--version'],capture_output=True,text=True,timeout=20)
    help_result=subprocess.run([codex,'exec','--help'],capture_output=True,text=True,timeout=20)
    required=('--ignore-user-config','--ignore-rules','--output-schema','--ephemeral')
    missing=[flag for flag in required if flag not in help_result.stdout]
    if missing: raise ValueError('This Codex CLI lacks required isolation features: '+', '.join(missing)+'. Update Codex; do not disable the checks.')
    print('Codex CLI: '+version.stdout.strip())
    auth=subprocess.run([codex,'login','status'],capture_output=True,text=True,timeout=20)
    if auth.returncode:
        if require_codex: raise ValueError('Codex is not signed in. Run codex login first.')
        print('Codex sign-in: needed before a live run')
    else: print('Codex sign-in: available')
    print('Model access is checked by a live preflight, not inferred from sign-in.')


def engine_arguments(config, command, cases_path=None, dest=None):
    args=[command,'--alan-prompt',str(ROOT/'prompts/alan.txt'),'--no-alan-github-refresh',
          '--worker-prompt',str(ROOT/'prompts/health_worker.txt'),
          '--worker-schema',str(ROOT/'schemas/health_worker.json'),
          '--judge-prompt',str(ROOT/'prompts/judge.txt'),'--judge-schema',str(ROOT/'schemas/judge.json'),
          '--challenge-judge-prompt',str(ROOT/'prompts/challenge_judge.txt'),
          '--challenge-judge-schema',str(ROOT/'schemas/challenge_judge.json'),
          '--raw-prompt',str(ROOT/'prompts/raw.txt')]
    for role,model_flag,reason_flag in [('alan','--model','--reasoning'),('health_worker','--worker-model','--worker-reasoning'),('judge','--judge-model','--judge-reasoning')]:
        settings=config['models'][role]
        args += [model_flag, settings['name'], reason_flag, settings['reasoning']]
    if cases_path: args += ['--cases',str(cases_path)]
    if dest: args += ['--run-dir' if command=='run' else '--output-dir',str(dest)]
    args += ['--timeout',str(config['timeouts']['alan']),'--worker-timeout',str(config['timeouts']['health_worker'])]
    if command=='run':
        args += ['--judge-timeout',str(config['timeouts']['judge']),'--concurrency',str(config['concurrency']),'--separate-worker-audit']
    return args


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=ROOT/'config.json')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('check',help='Check files, case bank and local Codex setup; no model calls')
    pre=sub.add_parser('preflight',help='Check the configured model routes using live calls')
    r=sub.add_parser('run',help='Start a new recorded run')
    r.add_argument('--cases',default='all',help='all, clinical, challenge or comma-separated case IDs')
    r.add_argument('--repeat',type=int,default=1)
    r.add_argument('--name',help='New run name; an existing run is never overwritten')
    resume=sub.add_parser('resume',help='Continue unfinished cases using their frozen inputs')
    resume.add_argument('name')
    stop=sub.add_parser('stop',help='Stop after the current model reply')
    stop.add_argument('name')
    v=sub.add_parser('view',help='Start the local viewer')
    v.add_argument('--port',type=int)
    v.add_argument('--run',help='Print a link for this saved run, with Follow latest on')
    validate=sub.add_parser('validate',help='Audit one recorded run without calling models')
    validate.add_argument('name')
    args=p.parse_args(argv)
    config=load_config(args.config)
    if args.command=='check': check(config);return 0
    if args.command=='view':
        import release_config
        release_config.CONFIG_PATH=args.config.resolve()
        sys.path.insert(0,str(ROOT/'viewer'))
        import monitor_server
        monitor_server.RUNS=Path(config['_runs'])
        monitor_server.CURRENT_RUNNER_ROUTE.update({key:value for key,value in {
            'model':config['models']['alan']['name'],'reasoning_effort':config['models']['alan']['reasoning'],
            'worker_model':config['models']['health_worker']['name'],'worker_reasoning_effort':config['models']['health_worker']['reasoning'],
            'judge_model':config['models']['judge']['name'],'judge_reasoning_effort':config['models']['judge']['reasoning']}.items()})
        port=args.port or config['viewer_port']
        suffix='?run='+run_path(config,args.run).name if args.run else ''
        print(f'Alan viewer: http://127.0.0.1:{port}/{suffix}',flush=True)
        server=monitor_server.ThreadingHTTPServer(('127.0.0.1',port),monitor_server.MonitorHandler)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
        return 0
    if args.command in ('stop','validate'):
        dest=run_path(config,args.name)
        if not (dest/'run_manifest.json').is_file(): raise ValueError('Run not found')
        if args.command=='stop':
            manifest=json.loads((dest/'run_manifest.json').read_text(encoding='utf-8'))
            if manifest.get('finished_at'): raise ValueError('This run has already finished')
            (dest/'STOP_REQUESTED').write_text(runner.utc_now()+'\n',encoding='utf-8')
            print('Stop requested after the current model reply.');return 0
        import validate_run
        report=validate_run.validate(dest)
        print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report.get('status')=='PASS' else 1
    if not __debug__: raise ValueError("Run without Python optimisation so input checks stay enabled")
    check(config,require_codex=True)
    if args.command=='resume':
        dest=run_path(config,args.name)
        parsed=runner.make_parser().parse_args(engine_arguments(config,'run',dest=dest)+['--resume'])
        return runner.command_run(parsed)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    work=ROOT/'work'/stamp
    work.mkdir(parents=True,exist_ok=False)
    selection=getattr(args,'cases','EYE-001,EXT-E01')
    cases=select_cases(load_cases(),selection,getattr(args,'repeat',1))
    source=work/'cases.json'
    runner.write_json(source,{'format':'alan-case-bank-v1','case_count':len(cases),'cases':cases,
                              'source_workbook_sha256':runner.sha256_file(ROOT/'data/cases.xlsx')})
    if args.command=='preflight':
        parsed=runner.make_parser().parse_args(engine_arguments(config,'preflight',source,work/'preflight'))
        return runner.command_preflight(parsed)
    name=args.name or f'alan_{len(cases)}_{stamp}'
    dest=run_path(config,name)
    if dest.exists(): raise ValueError('Run already exists. Choose a new name or use resume.')
    parsed=runner.make_parser().parse_args(engine_arguments(config,'run',source,dest))
    parsed.release_configuration=display_config(config)
    parsed.release_configuration['sha256']=hashlib.sha256(Path(config['_path']).read_bytes()).hexdigest()
    print(f'Recording {len(cases)} cases to {dest}\nViewer: http://127.0.0.1:{config["viewer_port"]}/?run={name}',flush=True)
    return runner.command_run(parsed)


if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,OSError,AssertionError,runner.CodexError) as exc:
        print('Error: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
