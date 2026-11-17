"""Self-authored real video with VFR timing; no downloaded footage."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import av
import numpy as np
from PIL import Image,ImageDraw
from .audit import audit_manifest,load_manifest
from .errors import InputError
from .manifest import sample_video,dump_json
from .report import write_report
from .local_io import local_path


def create_video(path):
    with av.open(str(path),'w',format='matroska') as container:
        stream=container.add_stream('ffv1',rate=25)
        stream.width=384;stream.height=216;stream.pix_fmt='bgr0'
        stream.time_base=Fraction(1,1000);stream.codec_context.time_base=Fraction(1,1000)
        for n in range(12):
            pts=5000+80*n-40*(n%2)
            image=Image.new('RGB',(384,216),(24,38,61));draw=ImageDraw.Draw(image)
            for x in range(0,384,24):draw.line((x,0,x,216),fill=(38,55,79))
            for y in range(0,216,24):draw.line((0,y,384,y),fill=(38,55,79))
            draw.rounded_rectangle((24+n*18,78,88+n*18,142),radius=12,fill=(54,159,176))
            draw.text((24,20),f'FRAME {n:02d} / 11',fill=(240,246,255),font_size=22)
            draw.text((24,176),f'Authored PTS {pts} / 1000 s',fill=(195,211,233),font_size=16)
            frame=av.VideoFrame.from_ndarray(np.asarray(image),format='rgb24')
            frame.pts=pts;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode(None):container.mux(packet)


def make_demo(out_dir):
    out_dir=local_path(out_dir)
    if out_dir.exists():raise InputError('demo output exists; choose a new directory')
    out_dir.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frameledger-demo-',dir=out_dir.parent) as temp:
        root=Path(temp)/'payload';root.mkdir();video=root/'synthetic-vfr.mkv';create_video(video)
        samples=root/'samples'
        sample_video(video,['0','0.14','0.16','0.28','0.42','0.60','0.80'],samples)
        valid=audit_manifest(video,samples/'manifest.json')
        original,_=load_manifest(samples/'manifest.json')
        tampered=copy.deepcopy(original);tampered['samples'][1]['pts']+=40
        tampered_path=samples/'tampered-manifest.json';dump_json(tampered_path,tampered)
        negative=audit_manifest(video,tampered_path)
        if valid['status']!='pass' or negative['status']!='fail':
            raise RuntimeError('demo positive/negative controls failed')
        valid['demo']='Self-authored VFR video; not a model performance measurement.'
        negative['demo']='Deliberately falsified PTS; expected failure.'
        write_report(valid,root/'valid');write_report(negative,root/'tampered')
        (root/'index.html').write_bytes((root/'valid'/'index.html').read_bytes())
        receipt=dict(valid=valid['status'],tampered=negative['status'],source_sha256=valid['source']['sha256'])
        dump_json(root/'demo-receipt.json',receipt)
        root.rename(out_dir)
    return receipt
