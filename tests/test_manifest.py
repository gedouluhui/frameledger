from fractions import Fraction as F
import json
from pathlib import Path
import tempfile
import unittest
from fixtures import make_video
from frameledger.manifest import sample_video
from frameledger.errors import InputError


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'source.mkv';make_video(self.video)

    def test_sample_uses_observed_pts(self):
        out=self.root/'sample'
        result=sample_video(self.video,['0','0.14','0.16'],out)
        self.assertEqual(result.get('status'),'sampled')
        self.assertTrue((out/'manifest.json').exists())
        m=json.loads((out/'manifest.json').read_text())
        self.assertEqual([r['index'] for r in m['samples']],[0,2,2])
        self.assertEqual([F(r['media_time']) for r in m['samples']],[F(5),F(129,25),F(129,25)])
        self.assertTrue(all((out/r['png']).is_file() for r in m['samples']))
        self.assertNotIn(str(self.root),json.dumps(m))

    def test_media_origin_previous(self):
        out=self.root/'sample'
        result=sample_video(self.video,['5.14'],out,policy='previous',origin='media')
        self.assertEqual(result.get('status'),'sampled')
        m=json.loads((out/'manifest.json').read_text())
        self.assertEqual(m['samples'][0]['index'],1)

    def test_no_overwrite_or_invalid_requests(self):
        with self.assertRaises(InputError):sample_video(self.video,['0'],self.root)
        for requests,kw in [([] ,{}),(['1'],{}),(['0'],{'origin':'guess'}),(['0']*129,{})]:
            with self.subTest(kw=kw),self.assertRaises(InputError):
                sample_video(self.video,requests,self.root/'bad',**kw)
            self.assertFalse((self.root/'bad').exists())


if __name__=='__main__':unittest.main()
