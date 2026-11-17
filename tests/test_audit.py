import copy
import json
from pathlib import Path
import tempfile
import unittest
from fixtures import make_video
from frameledger.manifest import sample_video
from frameledger.audit import audit_manifest
from frameledger.errors import InputError


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'source.mkv';make_video(self.video)
        self.out=self.root/'samples';sample_video(self.video,['0','0.14','0.16'],self.out)
        self.path=self.out/'manifest.json'
        self.original=json.loads(self.path.read_text())

    def save(self,m):self.path.write_text(json.dumps(m),encoding='utf-8')

    def test_fresh_decode_proves_samples(self):
        result=audit_manifest(self.video,self.path)
        self.assertEqual(result.get('status'),'pass')
        self.assertEqual(result['findings'],[])
        self.assertEqual([r['source_frame']['index'] for r in result['samples']],[0,2,2])

    def test_every_claim_is_checked(self):
        changes={'index':1,'pts':5040,'time_base':{'num':1,'den':100},'media_time':'6',
                 'width':32,'height':32,'rgb_sha256':'0'*64,'request':'0.01',
                 'request_media_time':'5.01','error_seconds':'1','png_sha256':'1'*64}
        for key,value in changes.items():
            m=copy.deepcopy(self.original);m['samples'][0][key]=value;self.save(m)
            with self.subTest(key=key):
                self.assertEqual(audit_manifest(self.video,self.path).get('status'),'fail')

    def test_wrong_policy_is_not_trusted(self):
        m=copy.deepcopy(self.original);m['policy']='previous';self.save(m)
        self.assertEqual(audit_manifest(self.video,self.path).get('status'),'fail')

    def test_actual_png_tampering_is_detected(self):
        first=self.out/self.original['samples'][0]['png']
        second=self.out/self.original['samples'][1]['png']
        first.write_bytes(second.read_bytes())
        self.assertEqual(audit_manifest(self.video,self.path).get('status'),'fail')

    def test_source_hash_is_checked(self):
        m=copy.deepcopy(self.original);m['source']['sha256']='0'*64;self.save(m)
        self.assertEqual(audit_manifest(self.video,self.path).get('status'),'fail')

    def test_full_index_digest_and_count_checked(self):
        for key,val in [('index_sha256','0'*64),('frame_count',99)]:
            m=copy.deepcopy(self.original);m[key]=val;self.save(m)
            self.assertEqual(audit_manifest(self.video,self.path).get('status'),'fail')

    def test_version_mismatch_is_incomparable(self):
        m=copy.deepcopy(self.original);m['decoder']['pyav']='0.0';self.save(m)
        self.assertEqual(audit_manifest(self.video,self.path).get('status'),'incomplete')

    def test_path_escape_and_missing_evidence_rejected(self):
        for path in ['../escape.png','/tmp/absolute.png','https://example.invalid/a.png','missing.png']:
            m=copy.deepcopy(self.original);m['samples'][0]['png']=path;self.save(m)
            with self.subTest(path=path),self.assertRaises(InputError):audit_manifest(self.video,self.path)

    def test_malformed_manifest_rejected(self):
        for m in [{},dict(self.original,schema_version=True),dict(self.original,samples=[]),
                  dict(self.original,requests=[]),dict(self.original,frame_count=True)]:
            self.save(m)
            with self.subTest(m=m.keys()),self.assertRaises(InputError):audit_manifest(self.video,self.path)
        self.path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(InputError):audit_manifest(self.video,self.path)

    def test_no_evidence_from_truncated_scan(self):
        report=audit_manifest(self.video,self.path,max_frames=2)
        self.assertEqual(report['status'],'incomplete')
        self.assertEqual(report['samples'],[])
        self.assertEqual(report['findings'][0]['code'],'decode_incomplete')


if __name__=='__main__':unittest.main()
