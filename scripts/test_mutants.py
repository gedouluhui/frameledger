"""Run known-bad variants only in private copies, with real passing controls first."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
MUTANTS=[
 ('wrong_tie','selection.py',[("timestamps[left+1]-t<t-timestamps[left]","timestamps[left+1]-t<=t-timestamps[left]")],'test_selection.py'),
 ('ignore_png','audit.py',[("if png['sha256']!=claim['png_sha256']:","if False:"),("if png['rgb_sha256']!=actual['rgb_sha256']:","if False:")],'test_audit.py'),
 ('ignore_versions','audit.py',[("if version_difference:","if False:")],'test_audit.py'),
 ('ignore_ffmpeg_errors','decode.py',[("if any(level<=av.logging.ERROR for level,_,_ in diagnostics):","if False:"),("if any(level<=av.logging.ERROR for level,_,_ in _diagnostics):","if False:")],'test_review_regressions.py'),
]


def run(root,pattern):
 env=dict(os.environ,PYTHONPATH=str(root/'src'))
 return subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'],
                       cwd=root,env=env,capture_output=True,text=True,timeout=90)


def main():
 if not shutil.which('ffprobe'):
  print('INCOMPLETE: ffprobe is required for the truncation mutation control');return 2
 originals={p:p.read_bytes() for p in (ROOT/'src').rglob('*.py')}
 for pattern in sorted({m[3] for m in MUTANTS}):
  p=run(ROOT,pattern)
  if p.returncode:
   print('BASELINE_FAILED',pattern,p.stdout,p.stderr);return 1
 caught=[]
 for name,file,replacements,pattern in MUTANTS:
  with tempfile.TemporaryDirectory(prefix='frameledger-mutant-') as tmp:
   root=Path(tmp)
   for folder in ['src','tests']:
    shutil.copytree(ROOT/folder,root/folder,ignore=shutil.ignore_patterns('__pycache__','*.egg-info'))
   target=root/'src'/'frameledger'/file;before=target.read_text(encoding='utf-8');after=before
   for old,new in replacements:
    if after.count(old)!=1:raise RuntimeError('invalid mutation anchor: '+name)
    after=after.replace(old,new,1)
   if after==before:raise RuntimeError('NOP mutation: '+name)
   target.write_text(after,encoding='utf-8',newline='\n')
   p=run(root,pattern);output=p.stdout+p.stderr
   detected=p.returncode!=0 and 'FAIL: test_' in output and 'AssertionError' in output
   print(('CAUGHT' if detected else 'MISSED'),name)
   if not detected:print(output)
   caught.append(detected)
 if any(p.read_bytes()!=data for p,data in originals.items()):raise RuntimeError('original source changed')
 print(f'{sum(caught)}/{len(caught)} named bad implementations caught; original source unchanged')
 return 0 if all(caught) else 1

if __name__=='__main__':raise SystemExit(main())
