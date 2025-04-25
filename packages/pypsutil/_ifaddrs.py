# mypy gets upset on Linux because the Sockaddr* structs are not defined there
# mypy: ignore-errors
# pylint: disable=no-member,protected-access
import ctypes
import ipaddress
import socket
from typing import Dict, List, Optional

from . import _detect, _ffi
from ._util import NICAddr


class IfAddrs(ctypes.Structure):  # pylint: disable=too-few-public-methods
    _fields_ = [
        ("ifa_next", ctypes.c_void_p),
        ("ifa_name", ctypes.c_char_p),
        ("ifa_flags", ctypes.c_uint),
        ("ifa_addr", ctypes.c_void_p),
        ("ifa_netmask", ctypes.c_void_p),
        ("ifa_dstaddr", ctypes.c_void_p),
        ("ifa_data", ctypes.c_void_p),
    ]

    if _detect.NETBSD:
        _fields_.append(("ifa_addrflags", ctypes.c_uint))


libc = _ffi.load_libc()

libc.getifaddrs.argtypes = (ctypes.POINTER(ctypes.POINTER(IfAddrs)),)
libc.getifaddrs.restype = ctypes.c_int

libc.freeifaddrs.argtypes = (ctypes.POINTER(IfAddrs),)
libc.freeifaddrs.restype = None


def net_if_addrs() -> Dict[str, List[NICAddr]]:
    all_ifaddrs = ctypes.POINTER(IfAddrs)()
    if libc.getifaddrs(ctypes.byref(all_ifaddrs)) < 0:
        raise _ffi.build_oserror(ctypes.get_errno())

    try:
        if not all_ifaddrs:
            return {}
        ifaddrs = all_ifaddrs.contents

        results: Dict[str, List[NICAddr]] = {}
        while True:
            name = ifaddrs.ifa_name.decode()
            results.setdefault(name, [])

            addr = get_sockaddr(ifaddrs.ifa_addr)
            assert addr is not None
            netmask = get_sockaddr(ifaddrs.ifa_netmask)

            broadaddr = None
            dstaddr = None
            if ifaddrs.ifa_flags & _detect._psimpl.IFF_BROADCAST:
                broadaddr = get_sockaddr(ifaddrs.ifa_dstaddr)
            elif ifaddrs.ifa_flags & _detect._psimpl.IFF_POINTOPOINT:
                dstaddr = get_sockaddr(ifaddrs.ifa_dstaddr)

            addr_str = addr_to_string(addr)
            netmask_str = addr_to_string(netmask) if netmask is not None else None
            broadaddr_str = (
                addr_to_string(broadaddr)
                if broadaddr is not None and broadaddr.ss_family != socket.AF_UNSPEC
                else None
            )
            dstaddr_str = (
                addr_to_string(dstaddr)
                if dstaddr is not None and dstaddr.ss_family != socket.AF_UNSPEC
                else None
            )

            assert broadaddr_str is None or dstaddr_str is None

            if addr.ss_family == socket.AF_INET6 and ipaddress.IPv6Address(addr_str).is_link_local:
                addr_str += "%" + name

            results[name].append(
                NICAddr(
                    family=socket.AddressFamily(addr.ss_family),
                    address=addr_str,
                    netmask=netmask_str,
                    broadcast=broadaddr_str,
                    ptp=dstaddr_str,
                )
            )

            if not ifaddrs.ifa_next:
                break
            ifaddrs = ctypes.cast(ifaddrs.ifa_next, ctypes.POINTER(IfAddrs)).contents
    finally:
        libc.freeifaddrs(all_ifaddrs)

    for nicaddrs in results.values():
        nicaddrs.sort(key=lambda nicaddr: nicaddr.family)

    return results


def get_sockaddr(address: int) -> Optional["_detect._psimpl.SockaddrStorage"]:
    return _detect._psimpl.SockaddrStorage.from_address(address) if address else None


def addr_to_string(addr: "_detect._psimpl.SockaddrStorage") -> str:
    if addr.ss_family == socket.AF_INET:
        return _detect._psimpl.SockaddrIn.from_buffer(addr).to_tuple()[0]
    elif addr.ss_family == socket.AF_INET6:
        return _detect._psimpl.SockaddrIn6.from_buffer(addr).to_tuple()[0]
    elif addr.ss_family == socket.AF_LINK:
        sdl = _detect._psimpl.SockaddrDl.from_buffer(addr)
        return ":".join(
            f"{byte:02x}" for byte in sdl.sdl_data[sdl.sdl_nlen: sdl.sdl_nlen + sdl.sdl_alen]
        )
    else:
        raise ValueError
