"""Bounded sequential CPU observations; no estimated frame-rate indexing."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time
import threading
import av
import numpy as np
from .errors import InputError
from .local_io import local_path

_LOG_LOCK=threading.RLock()

FORMATS='matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,avi,mpegts,ogg'
MAX_SOURCE_BYTES=8*1024**3


def rgb_hash(array):
    a=np.ascontiguousarray(array,dtype=np.uint8)
    h=hashlib.sha256()
    h.update(f'rgb24:{a.shape[1]}x{a.shape[0]}:'.encode('ascii'))
    h.update(a.tobytes())
    return h.hexdigest()


def _hash_file(handle):
    handle.seek(0);h=hashlib.sha256();count=0
    while True:
        block=handle.read(1024*1024)
        if not block:break
        count+=len(block)
        if count>MAX_SOURCE_BYTES:raise InputError('source exceeds 8 GiB byte budget')
        h.update(block)
    handle.seek(0)
    return h.hexdigest()


def _deny_nested(url,flags,options):
    raise InputError('nested media I/O is not supported')


def scan_video(path,stream_index=None,*,max_frames=250000,max_pixels=16777216,max_seconds=120.0,_on_frame=None):
    # PyAV ignores FFmpeg logs by default; truncated demuxers may end iteration
    # without raising. Capture errors and disable coalescing for repeat scans.
    with _LOG_LOCK:
        old_level=av.logging.get_level()
        old_repeats=av.logging.get_skip_repeated()
        try:
            av.logging.set_level(av.logging.ERROR)
            av.logging.set_skip_repeated(False)
            with av.logging.Capture(local=True) as diagnostics:
                result=_scan_video(path,stream_index,max_frames=max_frames,max_pixels=max_pixels,
                                   max_seconds=max_seconds,_on_frame=_on_frame,_diagnostics=diagnostics)
            if any(level<=av.logging.ERROR for level,_,_ in diagnostics):
                raise InputError('FFmpeg error diagnostics: media decode incomplete')
            return result
        finally:
            av.logging.set_level(old_level)
            av.logging.set_skip_repeated(old_repeats)


def _scan_video(path,stream_index=None,*,max_frames=250000,max_pixels=16777216,max_seconds=120.0,_on_frame=None,_diagnostics=()):
    if any(type(n) is not int or n<=0 for n in [max_frames,max_pixels]):
        raise InputError('frame and pixel budgets must be positive integers')
    if not isinstance(max_seconds,(int,float)) or isinstance(max_seconds,bool) or not 0<max_seconds<=86400:
        raise InputError('cooperative time budget must be in (0,86400] seconds')
    if stream_index is not None and (type(stream_index) is not int or stream_index<0):
        raise InputError('stream index must be a nonnegative integer')
    path=local_path(path)
    if not path.is_file():raise InputError('source is not a local regular file')
    if path.stat().st_size>MAX_SOURCE_BYTES:raise InputError('source exceeds 8 GiB byte budget')
    frames=[];previous=None;started=time.monotonic()
    try:
        with path.open('rb') as handle:
            digest=_hash_file(handle)
            options={'protocol_whitelist':'pipe','format_whitelist':FORMATS,'err_detect':'explode'}
            with av.open(handle,'r',options=options,io_open=_deny_nested) as container:
                videos=list(container.streams.video)
                if not videos:raise InputError('no video stream')
                selected=videos[0] if stream_index is None else next((s for s in videos if s.index==stream_index),None)
                if selected is None:raise InputError('requested video stream does not exist')
                if selected.width and selected.height and selected.width*selected.height>max_pixels:
                    raise InputError('declared stream dimensions exceed pixel budget')
                selected.thread_type='SLICE';selected.codec_context.thread_count=1
                chosen=selected.index
                decoder=dict(pyav=av.__version__,ffmpeg_libraries={k:list(v) for k,v in av.library_versions.items()},
                             pixel_format='rgb24',orientation='raw')
                for index,frame in enumerate(container.decode(selected)):
                    if any(level<=av.logging.ERROR for level,_,_ in _diagnostics):
                        raise InputError('FFmpeg error diagnostics: media decode incomplete')
                    if index>=max_frames:raise InputError('decode incomplete: frame budget exceeded')
                    if time.monotonic()-started>max_seconds:raise InputError('decode incomplete: cooperative time budget exceeded')
                    if not frame.width or not frame.height or frame.width*frame.height>max_pixels:
                        raise InputError('frame dimensions exceed pixel budget')
                    if frame.is_corrupt:raise InputError('decoder marked a corrupt frame')
                    if frame.pts is None or frame.time_base is None or frame.time_base<=0:
                        raise InputError('missing valid observed PTS/timebase')
                    stamp=frame.pts*Fraction(frame.time_base)
                    if previous is not None and stamp<=previous:
                        raise InputError('observed PTS are not strictly increasing')
                    previous=stamp
                    rgb=frame.to_ndarray(format='rgb24')
                    row=dict(index=index,pts=frame.pts,
                             time_base=dict(num=frame.time_base.numerator,den=frame.time_base.denominator),
                             media_time=str(stamp),width=frame.width,height=frame.height,rgb_sha256=rgb_hash(rgb))
                    frames.append(row)
                    if _on_frame is not None:_on_frame(index,rgb)
            if not frames:raise InputError('no decoded frames; no evidence')
            if _hash_file(handle)!=digest:raise InputError('source changed during decode')
    except InputError:raise
    except (OSError,av.FFmpegError,ValueError) as exc:
        raise InputError('media decode failed or container is unsupported') from exc
    encoded=json.dumps(frames,sort_keys=True,separators=(',',':')).encode('ascii')
    return dict(source=dict(name=path.name,sha256=digest,stream_index=chosen),decoder=decoder,
                frame_count=len(frames),index_sha256=hashlib.sha256(encoded).hexdigest(),frames=frames,
                coverage='Supplied file decoded to iteration end without FFmpeg error diagnostics. Observed decoder PTS; raw orientation. Not proof the original recording is complete; no audio/HDR/display equivalence claim.')
