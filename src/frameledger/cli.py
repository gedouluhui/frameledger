import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .errors import InputError
from .local_io import local_path


def main(argv=None):
    parser=argparse.ArgumentParser(prog='frameledger',description='Verify video sampling claims by decoding the source again.')
    parser.add_argument('--version',action='version',version=__version__)
    subs=parser.add_subparsers(dest='command',required=True)
    sample=subs.add_parser('sample',help='Export frames and an exact sampling contract')
    sample.add_argument('video',type=Path);sample.add_argument('--times',required=True)
    sample.add_argument('--policy',choices=['nearest','previous'],default='nearest')
    sample.add_argument('--origin',choices=['media','first-frame'],default='first-frame')
    sample.add_argument('--stream',type=int)
    sample.add_argument('--max-frames',type=int,default=250000)
    sample.add_argument('--out',type=Path,required=True)
    audit=subs.add_parser('audit',help='Re-decode video and verify manifest plus exported PNGs')
    audit.add_argument('video',type=Path);audit.add_argument('manifest',type=Path)
    audit.add_argument('--max-frames',type=int,default=250000)
    audit.add_argument('--out',type=Path,required=True)
    demo=subs.add_parser('demo',help='Create real VFR video and run positive/tampered controls')
    demo.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        args.out=local_path(args.out)
        if args.out.exists():raise InputError('output exists; choose a new directory')
        if args.command=='sample':
            from .manifest import sample_video
            r=sample_video(args.video,args.times.split(','),args.out,policy=args.policy,origin=args.origin,
                           stream_index=args.stream,max_frames=args.max_frames)
            result=dict(status=r['status'],samples=len(r['samples']));code=0
        elif args.command=='audit':
            from .audit import audit_manifest
            from .report import write_report
            r=audit_manifest(args.video,args.manifest,max_frames=args.max_frames);write_report(r,args.out)
            result=dict(status=r['status'],findings=len(r['findings']))
            code={'pass':0,'fail':1,'incomplete':2}[r['status']]
        else:
            from .demo import make_demo
            result=make_demo(args.out);code=0
        result['report']=str(args.out/'index.html')
        print(json.dumps(result,ensure_ascii=True));return code
    except (InputError,OSError) as exc:
        print(f'frameledger: {exc}',file=sys.stderr);return 2
