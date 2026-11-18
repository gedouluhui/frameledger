"""Conservative local paths: reject UNC, remote drives and reparse traversal."""
import os
from pathlib import Path, PureWindowsPath
import stat
from .errors import InputError


def local_path(value):
    text=os.fspath(value)
    if not isinstance(text,str) or text.replace('\\','/').startswith('//') or '://' in text:
        raise InputError('network/UNC paths are unsupported; use an ordinary local file')
    path=Path(os.path.abspath(text))  # lexical, no symlink resolution or filesystem I/O
    if str(path).replace('\\','/').startswith('//'):
        raise InputError('normalized UNC paths are unsupported')
    if os.name=='nt':
        import ctypes
        drive=PureWindowsPath(str(path)).drive
        query=ctypes.windll.kernel32.GetDriveTypeW
        query.argtypes=[ctypes.c_wchar_p];query.restype=ctypes.c_uint
        if query(drive+'\\')==4:
            raise InputError('mapped network drives are unsupported')
    # Visit lexical ancestors first, refusing links before following their children.
    for part in [*reversed(path.parents),path]:
        try:info=part.lstat()
        except FileNotFoundError:break
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise InputError('symlinks/reparse points are unsupported for offline evidence')
    return path
