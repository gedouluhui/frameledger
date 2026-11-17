import json
from importlib.resources import files
from pathlib import Path
from .errors import InputError
from .local_io import local_path


def _web(value):
    if type(value) is int and abs(value)>2**53-1:return str(value)
    if isinstance(value,list):return [_web(v) for v in value]
    if isinstance(value,dict):return {k:_web(v) for k,v in value.items()}
    return value


def _write_into(report,directory):
    archive=json.dumps(report,ensure_ascii=True,allow_nan=False,indent=2)
    data=json.dumps(_web(report),ensure_ascii=True,allow_nan=False,separators=(',',':')).replace('<','\\u003c')
    html=files('frameledger').joinpath('templates/report.html').read_text(encoding='utf-8').replace('__REPORT_DATA__',data)
    (Path(directory)/'report.json').write_text(archive,encoding='utf-8')
    (Path(directory)/'index.html').write_text(html,encoding='utf-8')


def write_report(report,out_dir):
    out_dir=local_path(out_dir)
    if out_dir.exists():raise InputError('output exists; choose a new directory')
    out_dir.mkdir(parents=True,exist_ok=False)
    _write_into(report,out_dir)
