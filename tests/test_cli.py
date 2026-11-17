import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fixtures import make_video


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'source.mkv';make_video(self.video)

    def cli(self,*args):
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        return subprocess.run([sys.executable,'-m','frameledger',*map(str,args)],cwd=self.root,env=env,
                              capture_output=True,text=True,timeout=30)

    def test_real_sample_audit_and_tamper_cli(self):
        out=self.root/'samples'
        p=self.cli('sample',self.video,'--times','0,0.14,0.16','--out',out)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue((out/'manifest.json').is_file())
        self.assertTrue((out/'index.html').is_file())
        audit=self.root/'audit'
        p=self.cli('audit',self.video,out/'manifest.json','--out',audit)
        self.assertEqual(p.returncode,0,p.stderr)
        report=json.loads((audit/'report.json').read_text())
        self.assertEqual(report['status'],'pass')
        self.assertTrue(report['samples'][0]['png_evidence'].get('preview_png'))
        m=json.loads((out/'manifest.json').read_text());m['samples'][0]['pts']+=1
        (out/'manifest.json').write_text(json.dumps(m))
        p=self.cli('audit',self.video,out/'manifest.json','--out',self.root/'bad')
        self.assertEqual(p.returncode,1,p.stderr)

    def test_no_overwrite_or_invalid_success(self):
        p=self.cli('sample',self.video,'--times','nan','--out',self.root/'bad')
        self.assertEqual(p.returncode,2)
        self.assertFalse((self.root/'bad').exists())
        self.assertEqual(self.cli('sample',self.video,'--times','0','--out',self.root).returncode,2)

    def test_demo_runs_both_controls(self):
        out=self.root/'demo'
        p=self.cli('demo','--out',out)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue((out/'index.html').exists())
        self.assertTrue((out/'tampered'/'report.json').exists())
        self.assertEqual(json.loads((out/'valid'/'report.json').read_text())['status'],'pass')
        self.assertEqual(json.loads((out/'tampered'/'report.json').read_text())['status'],'fail')
        self.assertEqual(self.cli('demo','--out',out).returncode,2)


if __name__=='__main__':unittest.main()
