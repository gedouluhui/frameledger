from fractions import Fraction
import av
import numpy as np


def frame_pixels(index,static=False):
    a=np.zeros((48,64,3),np.uint8)
    a[:]=((0 if static else index*19)%256,80,160)
    a[8:32,8:40]=((0 if static else index*13)%256,210,40)
    return a


def make_video(path,pts=None,static=False):
    pts=pts if pts is not None else [5000+80*n-40*(n%2) for n in range(12)]
    with av.open(str(path),'w',format='matroska') as c:
        s=c.add_stream('ffv1',rate=25)
        s.width=64;s.height=48;s.pix_fmt='bgr0'
        s.time_base=Fraction(1,1000);s.codec_context.time_base=Fraction(1,1000)
        for i,t in enumerate(pts):
            f=av.VideoFrame.from_ndarray(frame_pixels(i,static),format='rgb24')
            f.pts=t;f.time_base=Fraction(1,1000)
            for packet in s.encode(f):c.mux(packet)
        for packet in s.encode(None):c.mux(packet)
    return [Fraction(t,1000) for t in pts]
