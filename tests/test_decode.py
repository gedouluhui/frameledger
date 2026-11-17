from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from fixtures import make_video
from frameledger.decode import scan_video
from frameledger.errors import InputError


class DecodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'vfr.mkv'
        self.expected=make_video(self.video)

    def test_real_vfr_nonzero_start(self):
        result=scan_video(self.video)
        self.assertEqual(result.get('frame_count'),12)
        observed=[F(r['pts']*r['time_base']['num'],r['time_base']['den']) for r in result['frames']]
        self.assertEqual(observed,self.expected)
        self.assertEqual(result['source']['stream_index'],0)
        self.assertEqual(len(set(r['rgb_sha256'] for r in result['frames'])),12)

    def test_static_pixels_do_not_erase_frame_identity(self):
        static=self.root/'static.mkv';make_video(static,static=True)
        r=scan_video(static)
        self.assertEqual(r.get('frame_count'),12)
        self.assertEqual(len(set(x['rgb_sha256'] for x in r['frames'])),1)

    def test_budget_and_wrong_stream(self):
        for kwargs in [{'max_frames':3},{'max_pixels':2},{'stream_index':999},{'max_frames':True}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(InputError):scan_video(self.video,**kwargs)

    def test_local_file_only(self):
        for path in ['https://example.invalid/a.mp4',str(self.root),str(self.root/'missing')]:
            with self.subTest(path=path),self.assertRaises(InputError):scan_video(path)
        bad=self.root/'playlist.mkv';bad.write_text('ffconcat version 1.0\nfile https://example.invalid/a.mp4\n')
        with self.assertRaises(InputError):scan_video(bad)

    @unittest.skipUnless(shutil.which('ffprobe'),'optional ffprobe executable not installed')
    def test_ffprobe_observation_agrees_with_authored_timeline(self):
        cmd=['ffprobe','-v','error','-select_streams','v:0','-show_entries',
             'frame=pts:stream=time_base','-of','json',str(self.video)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=20,check=True)
        data=json.loads(p.stdout);tb=F(data['streams'][0]['time_base'])
        expected=[f['pts']*tb for f in data['frames']]
        self.assertEqual(expected,self.expected)
        result=scan_video(self.video)
        self.assertEqual(result.get('frame_count'),len(expected))
        actual=[F(r['media_time']) for r in result['frames']]
        self.assertEqual(actual,expected)


if __name__=='__main__':unittest.main()
