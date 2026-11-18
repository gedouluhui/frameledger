import copy
import ctypes
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fixtures import make_video
from frameledger.audit import audit_manifest
from frameledger.manifest import sample_video
from frameledger.local_io import local_path
from frameledger.errors import InputError
from frameledger.report import write_report


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'source.mkv';make_video(self.video)
        sample_video(self.video,['0','0.14'],self.root/'sample')
        self.file=self.root/'sample'/'manifest.json';self.original=json.loads(self.file.read_text())

    @unittest.skipUnless(os.name=='nt','Windows UNC normalization')
    def test_mixed_unc_rejects_before_any_system_query(self):
        for text in ['/\\example.invalid/share/a.mkv','\\/example.invalid/share/a.mkv']:
            with self.subTest(path=text),patch.object(ctypes.windll.kernel32,'GetDriveTypeW',
                    side_effect=AssertionError('network-capable drive query occurred')) as drive:
                with self.assertRaises(InputError):local_path(text)
                drive.assert_not_called()
        self.assertEqual(local_path(self.video),self.video)

    def test_confirmed_failure_dominates_unknown_version(self):
        m=copy.deepcopy(self.original);m['source']['name']='wrong.mkv';m['tool_version']='999'
        self.file.write_text(json.dumps(m));r=audit_manifest(self.video,self.file)
        self.assertEqual(r['status'],'fail')
        self.assertEqual({f['code'] for f in r['findings']},{'source_name','version_incomparable'})
        self.assertEqual(r['samples'],[])

    def test_confirmed_decoder_failure_survives_unknown_version(self):
        m=copy.deepcopy(self.original);m['tool_version']='999';m['decoder']['pixel_format']='rgba'
        self.file.write_text(json.dumps(m));r=audit_manifest(self.video,self.file)
        self.assertEqual(r['status'],'fail')
        self.assertEqual({f['code'] for f in r['findings']},{'decoder_pixel_format','version_incomparable'})
        self.assertEqual(r['samples'],[])

    def test_origin_domain_contradiction_is_reported_failure(self):
        m=copy.deepcopy(self.original);m['origin']='media';self.file.write_text(json.dumps(m))
        try:r=audit_manifest(self.video,self.file)
        except InputError as exc:self.fail('semantic claim escaped without evidence: '+str(exc))
        self.assertEqual(r['status'],'fail')
        self.assertIn('claim_request_domain',{f['code'] for f in r['findings']})
        self.assertEqual(r['samples'],[])

    def test_transient_publish_denial_is_retried(self):
        r=audit_manifest(self.video,self.file);self.assertEqual(r['status'],'pass')
        destination=self.root/'published';original=Path.rename;attempts={'n':0}
        def flaky(path,target):
            attempts['n']+=1
            if attempts['n']<=2:raise PermissionError(13,'Access is denied','payload')
            return original(path,target)
        with patch.object(Path,'rename',flaky):write_report(r,destination)
        self.assertGreaterEqual(attempts['n'],3)
        self.assertTrue((destination/'report.json').exists())
        self.assertTrue((destination/'index.html').exists())

    def test_persistent_publish_denial_leaves_no_output_or_lock(self):
        r=audit_manifest(self.video,self.file);self.assertEqual(r['status'],'pass')
        destination=self.root/'denied'
        with patch.object(Path,'rename',side_effect=PermissionError(13,'Access is denied','payload')):
            with self.assertRaises(PermissionError):write_report(r,destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root/'.denied.lock').exists())

    def test_no_final_pass_report_after_any_write_failure(self):
        r=audit_manifest(self.video,self.file);self.assertEqual(r['status'],'pass')
        original=Path.write_text
        for fail_name in ['report.json','index.html']:
            destination=self.root/fail_name.replace('.','-')
            before={p.name for p in self.root.iterdir()}
            def fail(path,*args,**kwargs):
                if path.name==fail_name:raise OSError('injected report write failure')
                return original(path,*args,**kwargs)
            with patch.object(Path,'write_text',fail),self.assertRaises(OSError):write_report(r,destination)
            self.assertFalse(destination.exists(),fail_name)
            self.assertEqual({p.name for p in self.root.iterdir()},before)
        out=self.root/'good';write_report(r,out)
        self.assertTrue((out/'report.json').exists());self.assertTrue((out/'index.html').exists())
        original_bytes=(out/'report.json').read_bytes()
        with self.assertRaises(InputError):write_report(r,out)
        self.assertEqual((out/'report.json').read_bytes(),original_bytes)


if __name__=='__main__':unittest.main()
