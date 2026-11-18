"""Verify claims against a fresh source decode, never against a saved index alone."""
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path, PureWindowsPath
import re
import numpy as np
from PIL import Image
from . import __version__
from .decode import scan_video,rgb_hash
from .errors import InputError
from .manifest import requested_times
from .selection import select_indices,parse_time
from .preview import thumbnail_data
from .local_io import local_path

MAX_MANIFEST_BYTES=16*1024*1024
MAX_PNG_BYTES=64*1024*1024
ROOT_KEYS={'schema_version','tool_version','source','decoder','index_sha256','frame_count','origin','policy','requests','samples'}
ROW_KEYS={'index','pts','time_base','media_time','width','height','rgb_sha256','request','request_media_time','error_seconds','png','png_sha256'}


def _object(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise InputError('duplicate manifest key')
        result[k]=v
    return result


def _float(text):
    value=float(text)
    if not math.isfinite(value):raise InputError('nonfinite manifest number')
    return value


def _hash(value):
    return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None


def _integer(value,minimum=0):
    return type(value) is int and value>=minimum


def load_manifest(path):
    path=local_path(path)
    try:
        with Path(path).open('rb') as file:raw=file.read(MAX_MANIFEST_BYTES+1)
        if len(raw)>MAX_MANIFEST_BYTES:raise InputError('manifest exceeds 16 MiB')
        m=json.loads(raw.decode('utf-8'),object_pairs_hook=_object,parse_float=_float,
                     parse_constant=lambda _:(_ for _ in ()).throw(InputError('nonfinite manifest number')))
    except InputError:raise
    except (OSError,ValueError,UnicodeError,RecursionError) as exc:raise InputError('invalid manifest JSON') from exc
    if not isinstance(m,dict) or set(m)!=ROOT_KEYS or type(m['schema_version']) is not int or m['schema_version']!=1:
        raise InputError('unsupported manifest schema or fields')
    if not isinstance(m['tool_version'],str) or len(m['tool_version'])>64:
        raise InputError('invalid tool version')
    if not isinstance(m['source'],dict) or set(m['source'])!={'name','sha256','stream_index'}:
        raise InputError('invalid source metadata')
    s=m['source']
    if not isinstance(s['name'],str) or len(s['name'])>1024 or not _hash(s['sha256']) or not _integer(s['stream_index']):
        raise InputError('invalid source metadata values')
    if not isinstance(m['decoder'],dict) or set(m['decoder'])!={'pyav','ffmpeg_libraries','pixel_format','orientation'}:
        raise InputError('invalid decoder metadata')
    if not _integer(m['frame_count'],1) or not _hash(m['index_sha256']):raise InputError('invalid index metadata')
    if not isinstance(m['requests'],list) or not 0<len(m['requests'])<=128:raise InputError('invalid request count')
    if not isinstance(m['samples'],list) or len(m['samples'])!=len(m['requests']):raise InputError('sample/request counts differ')
    if m['policy'] not in ('nearest','previous') or m['origin'] not in ('media','first-frame'):raise InputError('unsupported sampling policy/origin')
    for t in m['requests']:parse_time(t)
    for row in m['samples']:
        if not isinstance(row,dict) or set(row)!=ROW_KEYS:raise InputError('invalid sample fields')
        if not all(_integer(row[k]) for k in ['index','width','height']) or not row['width'] or not row['height']:
            raise InputError('invalid sample index/dimensions')
        if type(row['pts']) is not int:raise InputError('invalid sample PTS')
        tb=row['time_base']
        if not isinstance(tb,dict) or set(tb)!={'num','den'} or not all(_integer(tb[k],1) for k in ['num','den']):
            raise InputError('invalid time base')
        parse_time(row['request'])
        for k in ['media_time','request_media_time','error_seconds']:parse_time(row[k],derived=True)
        if not all(_hash(row[k]) for k in ['rgb_sha256','png_sha256']):raise InputError('invalid sample digest')
        if not isinstance(row['png'],str) or len(row['png'])>512:raise InputError('invalid PNG path')
    return m,hashlib.sha256(raw).hexdigest()


def png_path(root,name):
    if not name or '\\' in name or '://' in name or PureWindowsPath(name).drive:
        raise InputError('PNG path must be a confined relative path')
    relative=Path(name)
    if relative.is_absolute() or '..' in relative.parts:raise InputError('PNG path escapes the manifest directory')
    try:
        result=local_path(root/relative).resolve(strict=True)
        result.relative_to(local_path(root).resolve())
        if not result.is_file():raise InputError('PNG evidence is not a regular file')
    except (OSError,ValueError) as exc:raise InputError('PNG evidence missing or outside manifest directory') from exc
    return result


def _png_evidence(path):
    with path.open('rb') as handle:raw=handle.read(MAX_PNG_BYTES+1)
    if len(raw)>MAX_PNG_BYTES:raise InputError('PNG byte budget exceeded')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='PNG' or image.mode!='RGB' or image.width*image.height>16777216:
                raise InputError('unsupported PNG encoding or pixel budget')
            pixels=np.asarray(image)
            return dict(sha256=hashlib.sha256(raw).hexdigest(),rgb_sha256=rgb_hash(pixels),
                        width=image.width,height=image.height,preview_png=thumbnail_data(image))
    except (OSError,ValueError,Image.DecompressionBombError) as exc:
        raise InputError('unreadable PNG evidence') from exc


def _same(a,b):
    # Preserve JSON scalar types: Python's True == 1 is not evidence equality.
    return json.dumps(a,sort_keys=True,separators=(',',':'))==json.dumps(b,sort_keys=True,separators=(',',':'))


def audit_manifest(path,manifest_path,*,max_frames=250000):
    manifest_path=local_path(manifest_path)
    m,manifest_digest=load_manifest(manifest_path)
    evidence=[png_path(manifest_path.parent,r['png']) for r in m['samples']]
    declared=dict(source=m['source'],decoder=m['decoder'],tool_version=m['tool_version'])
    try:
        observed=scan_video(path,m['source']['stream_index'],max_frames=max_frames)
    except InputError as exc:
        return dict(schema_version=1,tool_version=__version__,status='incomplete',samples=[],declared=declared,
                    source=dict(name=Path(path).name,stream_index=m['source']['stream_index'],sha256=None),
                    decoder=None,origin=m['origin'],policy=m['policy'],manifest_sha256=manifest_digest,
                    coverage='Incomplete: source decode did not finish; no sample was verified.',
                    findings=[dict(code='decode_incomplete',detail=str(exc),sample=None)])
    report=dict(schema_version=1,tool_version=__version__,status='pass',findings=[],samples=[],declared=declared,
                source=observed['source'],decoder=observed['decoder'],origin=m['origin'],policy=m['policy'],
                manifest_sha256=manifest_digest,coverage=observed['coverage'])
    def fail(code,detail,sample=None):
        report['findings'].append(dict(code=code,detail=detail,sample=sample))
        report['status']='fail'
    if m['source']['sha256']!=observed['source']['sha256']:
        fail('source_hash','Source bytes differ from the declared SHA256.')
        return report
    if m['source']['name']!=observed['source']['name']:
        fail('source_name','Source basename differs from the declared name; the byte identity is recorded separately.')
    for key in ['orientation','pixel_format']:
        if not _same(m['decoder'][key],observed['decoder'][key]):
            fail('decoder_'+key,'Declared decoding semantics do not match the actual decoding path.')
    version_difference=(m['tool_version']!=__version__ or any(not _same(m['decoder'][k],observed['decoder'][k])
                         for k in ['pyav','ffmpeg_libraries']))
    if version_difference:
        if report['status']!='fail':report['status']='incomplete'
        report['findings'].append(dict(code='version_incomparable',detail='Tool or decoder versions differ; pixel equivalence is not certified.',sample=None))
        return report
    for key in ['frame_count','index_sha256']:
        if not _same(m[key],observed[key]):fail(key,'Full re-decoded index differs from the claim.')
    wanted=requested_times(m['requests'],m['origin'],observed['frames'])
    stamps=[Fraction(r['media_time']) for r in observed['frames']]
    outside=[i for i,t in enumerate(wanted) if not stamps[0]<=t<=stamps[-1]]
    if outside:
        for i in outside:fail('claim_request_domain','Declared request and origin place this sample outside the observed source domain.',i)
        return report
    indices=select_indices(stamps,wanted,m['policy'])
    for n,(claim,index,request,want,file) in enumerate(zip(m['samples'],indices,m['requests'],wanted,evidence)):
        start_findings=len(report['findings'])
        actual=observed['frames'][index]
        expected=dict(actual,request=request,request_media_time=str(want),error_seconds=str(Fraction(actual['media_time'])-want))
        for key,value in expected.items():
            if not _same(claim[key],value):fail('claim_'+key,f'Declared {key} does not match fresh source evidence.',n)
        png=_png_evidence(file)
        if png['sha256']!=claim['png_sha256']:fail('png_bytes','Exported PNG bytes differ from the claim.',n)
        if png['rgb_sha256']!=actual['rgb_sha256']:fail('png_pixels','Exported PNG pixels differ from the selected source frame.',n)
        report['samples'].append(dict(source_frame=actual,png_evidence=dict(png,path=claim['png']),
            request=request,request_media_time=str(want),error_seconds=expected['error_seconds'],
            evidence_status='verified' if len(report['findings'])==start_findings else 'mismatch',claim=claim))
    return report
