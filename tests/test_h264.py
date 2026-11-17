from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from fixtures import make_video
from frameledger.decode import scan_video
from frameledger.manifest import sample_video
from frameledger.audit import audit_manifest


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'optional FFmpeg tools unavailable')
class H264Tests(unittest.TestCase):
    def test_long_gop_bframes_nonzero_vfr_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.mkv';expected=make_video(source)
            encoded=root/'bframes.mp4'
            p=subprocess.run(['ffmpeg','-v','error','-n','-copyts','-i',str(source),'-fps_mode','passthrough',
                              '-c:v','libx264','-g','12','-bf','2','-pix_fmt','yuv420p',str(encoded)],
                             capture_output=True,text=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr)
            metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
                 '-show_entries','stream=has_b_frames,time_base:frame=pts,pict_type','-of','json',str(encoded)],text=True))
            self.assertGreater(metadata['streams'][0]['has_b_frames'],0)
            self.assertTrue(any(f['pict_type']=='B' for f in metadata['frames']))
            tb=Fraction(metadata['streams'][0]['time_base'])
            times=[f['pts']*tb for f in metadata['frames']]
            self.assertEqual(times,expected)
            observed=scan_video(encoded)
            self.assertEqual([Fraction(f['media_time']) for f in observed['frames']],times)
            sample_video(encoded,['0','0.14','0.80'],root/'sample')
            self.assertEqual(audit_manifest(encoded,root/'sample'/'manifest.json')['status'],'pass')


if __name__=='__main__':unittest.main()
