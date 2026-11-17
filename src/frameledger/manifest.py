"""Export a declared sampling contract from real sequential observations."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tempfile
from PIL import Image
from . import __version__
from .decode import scan_video
from .errors import InputError
from .selection import parse_time,select_indices
from .local_io import local_path

MAX_SAMPLES=128


def requested_times(requests,origin,frames):
    if not isinstance(requests,list) or not 0<len(requests)<=MAX_SAMPLES:
        raise InputError('requests must contain 1..128 exact time strings')
    if origin not in ('first-frame','media'):
        raise InputError('origin must be first-frame or media')
    offset=Fraction(frames[0]['media_time']) if origin=='first-frame' else Fraction(0)
    return [parse_time(t)+offset for t in requests]


def dump_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=True,allow_nan=False,indent=2),encoding='utf-8')


def sample_video(path,requests,out_dir,*,policy='nearest',origin='first-frame',stream_index=None,max_frames=250000):
    out_dir=local_path(out_dir)
    if out_dir.exists():raise InputError('output exists; choose a new directory')
    if not isinstance(requests,list) or not 0<len(requests)<=MAX_SAMPLES:
        raise InputError('requests must contain 1..128 exact time strings')
    observation=scan_video(path,stream_index,max_frames=max_frames)
    wanted=requested_times(requests,origin,observation['frames'])
    indices=select_indices([Fraction(f['media_time']) for f in observation['frames']],wanted,policy)
    selected=set(indices)
    out_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frameledger-',dir=out_dir.parent) as temp:
        staging=Path(temp)/'payload';staging.mkdir()
        from .preview import thumbnail_data
        previews={}
        def save(index,rgb):
            if index in selected:
                Image.fromarray(rgb).save(staging/f'frame-{index:06d}.png',format='PNG')
                previews[index]=thumbnail_data(rgb)
        second=scan_video(path,observation['source']['stream_index'],max_frames=max_frames,_on_frame=save)
        if (observation['source']!=second['source'] or observation['index_sha256']!=second['index_sha256'] or
                observation['decoder']!=second['decoder']):
            raise InputError('source or decoder changed between observation and export')
        rows=[]
        for request,index,want in zip(requests,indices,wanted):
            frame=observation['frames'][index]
            filename=f'frame-{index:06d}.png'
            rows.append(dict(frame,request=request,request_media_time=str(want),
                             error_seconds=str(Fraction(frame['media_time'])-want),png=filename,
                             png_sha256=hashlib.sha256((staging/filename).read_bytes()).hexdigest()))
        manifest=dict(schema_version=1,tool_version=__version__,source=observation['source'],decoder=observation['decoder'],
                      index_sha256=observation['index_sha256'],frame_count=observation['frame_count'],
                      origin=origin,policy=policy,requests=requests,samples=rows)
        dump_json(staging/'manifest.json',manifest)
        from .audit import load_manifest
        load_manifest(staging/'manifest.json')  # exported derived fractions must be admissible
        report=dict(schema_version=1,tool_version=__version__,status='sampled',findings=[],
                    source=observation['source'],decoder=observation['decoder'],origin=origin,policy=policy,
                    coverage=observation['coverage'],samples=[dict(r,preview_png=previews[r['index']]) for r in rows])
        from .report import _write_into
        _write_into(report,staging)
        staging.rename(out_dir)
    return report
