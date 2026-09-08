"""One explicit public configuration shared by the launcher and viewer."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG_PATH=ROOT/'config.json'
COMPONENTS=('health_worker','runner','clinical_judge_prompt','clinical_scoring','worker_audit','challenge_judge','challenge_scoring','screening_assessment','audit_validator','case_filter','recorder','viewer','spreadsheet')


def load_config(path=None):
    selected=Path(path or CONFIG_PATH).resolve()
    config=json.loads(selected.read_text(encoding='utf-8'))
    if config.get('version')!='1.0.0' or config.get('alan_version')!='0.2.0':
        raise ValueError('Unsupported release configuration')
    for role in ('alan','health_worker','judge'):
        model=config['models'][role]
        if not isinstance(model.get('name'),str) or not model['name'].strip():
            raise ValueError(f'Missing model for {role}')
        if model.get('reasoning') not in {'minimal','low','medium','high','xhigh','max','ultra'}:
            raise ValueError(f'Invalid reasoning setting for {role}')
    for value in [config.get('concurrency'),*config.get('timeouts',{}).values()]:
        if type(value) is not int or value<1: raise ValueError('Concurrency and timeouts must be positive integers')
    if not 1<=config.get('viewer_port',0)<=65535: raise ValueError('Invalid viewer port')
    config['_path']=str(selected)
    config['_runs']=str((selected.parent/config['runs_directory']).resolve())
    return config


def display_config(config):
    versions={'alan':'v0.2.0',**{key:'v1' for key in COMPONENTS}}
    return {'id':'Alan evaluation v1','versions':versions,'display_versions':versions,
            'models':{role:[settings['name'],settings['reasoning']] for role,settings in config['models'].items()},
            'ready_for_full_run':True,'blockers':[]}
