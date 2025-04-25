import ctypes
import errno
import sys
from typing import Collection, List, Optional, TypeVar, Union

from . import _ffi

libc = _ffi.load_libc()

libc.sysctl.argtypes = (
    ctypes.POINTER(ctypes.c_int),
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_size_t),
    ctypes.c_void_p,
    ctypes.c_size_t,
)
libc.sysctl.restype = ctypes.c_int

if not sys.platform.startswith("openbsd"):
    libc.sysctlbyname.argtypes = (
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
        ctypes.c_size_t,
    )
    libc.sysctlbyname.restype = ctypes.c_int

    libc.sysctlnametomib.argtypes = (
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_size_t),
    )
    libc.sysctlnametomib.restype = ctypes.c_int


def sysctl(
    mib: Collection[int],
    new: Union[None, bytes, ctypes.Array, ctypes.Structure],  # type: ignore
    old: Union[None, ctypes.Array, ctypes.Structure],  # type: ignore
) -> int:
    raw_mib = (ctypes.c_int * len(mib))(*mib)  # pytype: disable=not-callable

    if new is None:
        new_size = 0
        raw_new = None
    elif isinstance(new, bytes):
        new_size = len(new)
        raw_new = ctypes.byref(ctypes.create_string_buffer(new))
    else:
        new_size = ctypes.sizeof(new)
        raw_new = ctypes.byref(new)

    if old is None:
        old_size = ctypes.c_size_t(0)
        raw_old = None
    else:
        old_size = ctypes.c_size_t(ctypes.sizeof(old))
        raw_old = ctypes.byref(old)

    if libc.sysctl(raw_mib, len(mib), raw_old, ctypes.byref(old_size), raw_new, new_size) < 0:
        raise _ffi.build_oserror(ctypes.get_errno())

    return old_size.value


if not sys.platform.startswith("openbsd"):

    def sysctlnametomib(name: str, *, maxlen: Optional[int] = None) -> List[int]:
        miblen = ctypes.c_size_t()

        if maxlen is None:
            if libc.sysctlnametomib(name.encode(), None, ctypes.byref(miblen)) < 0:
                raise _ffi.build_oserror(ctypes.get_errno())

            maxlen = miblen.value

        mib = (ctypes.c_int * maxlen)()
        miblen.value = maxlen

        if libc.sysctlnametomib(name.encode(), mib, ctypes.byref(miblen)) < 0:
            raise _ffi.build_oserror(ctypes.get_errno())

        return mib[: miblen.value]

    def sysctlbyname(
        name: str,
        new: Union[None, bytes, ctypes.Array, ctypes.Structure],  # type: ignore
        old: Union[None, ctypes.Array, ctypes.Structure],  # type: ignore
    ) -> int:
        if new is None:
            new_size = 0
            raw_new = None
        elif isinstance(new, bytes):
            new_size = len(new)
            raw_new = ctypes.byref(ctypes.create_string_buffer(new))
        else:
            new_size = ctypes.sizeof(new)
            raw_new = ctypes.byref(new)

        if old is None:
            old_size = ctypes.c_size_t(0)
            raw_old = None
        else:
            old_size = ctypes.c_size_t(ctypes.sizeof(old))
            raw_old = ctypes.byref(old)

        if libc.sysctlbyname(name.encode(), raw_old, ctypes.byref(old_size), raw_new, new_size) < 0:
            raise _ffi.build_oserror(ctypes.get_errno())

        return old_size.value


def sysctl_bytes_retry(mib: Collection[int], new: Optional[bytes], trim_nul: bool = False) -> bytes:
    while True:
        old_len = sysctl(mib, None, None)

        buf = (ctypes.c_char * old_len)()  # pytype: disable=not-callable

        try:
            old_len = sysctl(mib, new, buf)
        except OSError as ex:
            if ex.errno != errno.ENOMEM:
                raise
        else:
            return (buf.value if trim_nul else buf.raw)[:old_len]


if not sys.platform.startswith("openbsd"):

    def sysctlbyname_bytes_retry(name: str, new: Optional[bytes], trim_nul: bool = False) -> bytes:
        while True:
            old_len = sysctlbyname(name, None, None)

            buf = (ctypes.c_char * old_len)()  # pytype: disable=not-callable

            try:
                old_len = sysctlbyname(name, new, buf)
            except OSError as ex:
                if ex.errno != errno.ENOMEM:
                    raise
            else:
                return (buf.value if trim_nul else buf.raw)[:old_len]


C = TypeVar("C")  # pylint: disable=invalid-name


def sysctl_into(
    mib: Collection[int],
    old: C,
    *,
    new: Union[None, bytes, ctypes.Array, ctypes.Structure] = None,  # type: ignore
) -> C:
    old_len = sysctl(mib, new, old)  # type: ignore

    if old_len != ctypes.sizeof(old):  # type: ignore
        raise _ffi.build_oserror(errno.ENOMEM)

    return old


if not sys.platform.startswith("openbsd"):

    def sysctlbyname_into(
        name: str,
        old: C,
        *,
        new: Union[None, bytes, ctypes.Array, ctypes.Structure] = None,  # type: ignore
    ) -> C:
        old_len = sysctlbyname(name, new, old)  # type: ignore

        if old_len != ctypes.sizeof(old):  # type: ignore
            raise _ffi.build_oserror(errno.ENOMEM)

        return old
