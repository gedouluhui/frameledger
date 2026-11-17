import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from fixtures import make_video
from frameledger.decode import scan_video
from frameledger.manifest import sample_video
from frameledger.audit import audit_manifest
from frameledger.errors import InputError


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'source.mkv';make_video(self.video)
        self.out=self.root/'sample';sample_video(self.video,['0','0.14'],self.out)
        self.manifest=self.out/'manifest.json';self.m=json.loads(self.manifest.read_text())

    @unittest.skipUnless(shutil.which('ffprobe'),'ffprobe needed for byte truncation fixture')
    def test_truncated_media_must_not_be_certified_complete(self):
        packets=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
             '-show_entries','packet=pos','-of','json',str(self.video)],text=True))['packets']
        cut=self.root/'cut.mkv';cut.write_bytes(self.video.read_bytes()[:int(packets[8]['pos'])])
        import av
        before=(av.logging.get_level(),av.logging.get_skip_repeated())
        for _ in range(2):
            with self.assertRaises(InputError):scan_video(cut)
        self.assertEqual((av.logging.get_level(),av.logging.get_skip_repeated()),before)
        self.assertEqual(scan_video(self.video)['frame_count'],12)

    def test_unc_rejected_before_filesystem_queries(self):
        for name in ['//example.invalid/share/video.mkv',r'\\example.invalid\share\video.mkv']:
            with patch('pathlib.Path.is_file',side_effect=AssertionError('filesystem queried before UNC rejection')):
                with self.assertRaises(InputError):scan_video(name)

    def test_metadata_claims_have_distinct_outcomes(self):
        cases=[('source','name','wrong.mkv','fail'),('root','tool_version','999.0.0','incomplete'),
               ('decoder','orientation','display','fail'),('decoder','pixel_format','rgba','fail')]
        for section,key,value,status in cases:
            m=copy.deepcopy(self.m)
            (m if section=='root' else m[section])[key]=value
            self.manifest.write_text(json.dumps(m))
            r=audit_manifest(self.video,self.manifest)
            self.assertEqual(r['status'],status,(section,key))
            self.assertIn('declared',r)

    def test_mismatched_png_not_labeled_as_verified_source_frame(self):
        first=self.out/self.m['samples'][0]['png'];second=self.out/self.m['samples'][1]['png']
        first.write_bytes(second.read_bytes())
        r=audit_manifest(self.video,self.manifest);row=r['samples'][0]
        self.assertEqual(r['status'],'fail')
        self.assertEqual(row.get('evidence_status'),'mismatch')
        self.assertNotEqual(row['source_frame']['rgb_sha256'],row['png_evidence']['rgb_sha256'])

    def test_admitted_request_has_auditable_derived_fractions(self):
        out=self.root/'rational'
        sample_video(self.video,['140000000000000000/999999999999999989'],out)
        try:r=audit_manifest(self.video,out/'manifest.json')
        except InputError as exc:self.fail('sampler produced unauditable manifest: '+str(exc))
        self.assertEqual(r['status'],'pass')

    def test_budget_stop_returns_structured_incomplete_evidence(self):
        try:r=audit_manifest(self.video,self.manifest,max_frames=2)
        except InputError as exc:self.fail('scan abort lost structured evidence: '+str(exc))
        self.assertEqual(r['status'],'incomplete')
        self.assertEqual(r['samples'],[])
        self.assertTrue(r['findings'])
        self.assertNotIn('Complete sequential',r['coverage'])


if __name__=='__main__':unittest.main()
