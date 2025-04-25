import sys

LINUX = False
MACOS = False
FREEBSD = False
NETBSD = False
OPENBSD = False
BSD = False

if sys.platform.startswith("linux"):
    from . import _pslinux

    _psimpl = _pslinux

    LINUX = True
elif sys.platform.startswith("freebsd"):
    from . import _psfreebsd

    _psimpl = _psfreebsd

    FREEBSD = True
    BSD = True
elif sys.platform.startswith("netbsd"):
    from . import _psnetbsd

    _psimpl = _psnetbsd

    NETBSD = True
    BSD = True
elif sys.platform.startswith("openbsd"):
    from . import _psopenbsd

    _psimpl = _psopenbsd

    OPENBSD = True
    BSD = True
elif sys.platform.startswith("darwin"):
    from . import _psmacosx

    _psimpl = _psmacosx

    MACOS = True
else:
    raise RuntimeError("Unsupported platform")
