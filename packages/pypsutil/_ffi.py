# pylint: disable=invalid-name
import ctypes
import ctypes.util
import os
from typing import Any, Type, Union, cast  # pylint: disable=unused-import

pid_t = ctypes.c_int
uid_t = ctypes.c_uint32
gid_t = ctypes.c_uint32


_libc = None


def load_libc() -> ctypes.CDLL:
    global _libc  # pylint: disable=global-statement

    if _libc is None:
        libc_path = ctypes.util.find_library("c")
        _libc = ctypes.CDLL(libc_path, use_errno=True)

    return _libc


def build_oserror(
    eno: int,
    filename: Union[str, bytes, None] = None,
    filename2: Union[str, bytes, None] = None,
) -> OSError:
    return OSError(eno, os.strerror(eno), filename, None, filename2)


def ctypes_int_is_signed(int_type: Type["ctypes._SimpleCData[Any]"]) -> bool:
    return cast(bool, int_type(-1).value == -1)


def ctypes_int_min(int_type: Type["ctypes._SimpleCData[Any]"]) -> int:
    if ctypes_int_is_signed(int_type):
        # Signed type
        return cast(int, -(2 ** (ctypes.sizeof(int_type) * 8 - 1)))
    else:
        # Unsigned type
        return 0


def ctypes_int_max(int_type: Type["ctypes._SimpleCData[Any]"]) -> int:
    neg_one = int_type(-1).value

    if neg_one == -1:
        # Signed type
        return cast(int, 2 ** (ctypes.sizeof(int_type) * 8 - 1) - 1)
    else:
        # Unsigned type
        return cast(int, neg_one)
