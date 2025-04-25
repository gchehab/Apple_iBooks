import ctypes
import dataclasses
import enum
import functools
import ipaddress
import os
import resource
import signal
import socket
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from ._errors import AccessDenied, NoSuchProcess

if TYPE_CHECKING:  # pragma: no cover
    from ._process import Process  # pytype: disable=pyi-error

RESOURCE_NUMS = set()
for name in dir(resource):
    if name.startswith("RLIMIT_"):
        RESOURCE_NUMS.add(getattr(resource, name))


CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGESIZE = os.sysconf("SC_PAGESIZE")


@enum.unique
class ProcessStatus(enum.Enum):
    RUNNING = "running"
    SLEEPING = "sleeping"
    DISK_SLEEP = "disk-sleep"
    ZOMBIE = "zombie"
    STOPPED = "stopped"
    TRACING_STOP = "tracing-stop"
    DEAD = "dead"
    WAKE_KILL = "wake-kill"
    WAKING = "waking"
    PARKED = "parked"
    IDLE = "idle"
    LOCKED = "locked"
    WAITING = "waiting"
    SUSPENDED = "suspended"


@dataclasses.dataclass
class ProcessOpenFile:
    path: str
    fd: int


@enum.unique
class ProcessFdType(enum.Enum):
    FILE = "file"
    SOCKET = "socket"
    PIPE = "pipe"
    FIFO = "fifo"

    KQUEUE = "kqueue"
    PROCDESC = "procdesc"

    INOTIFY = "inotify"
    SIGNALFD = "signalfd"
    EPOLL = "epoll"
    TIMERFD = "timerfd"
    PIDFD = "pidfd"
    EVENTFD = "eventfd"

    UNKNOWN = "unknown"


@dataclasses.dataclass
class ProcessFd:  # pylint: disable=too-many-instance-attributes
    path: str
    fd: int
    position: int
    flags: int
    fdtype: ProcessFdType
    dev: Optional[int]
    ino: Optional[int]
    rdev: Optional[int]
    mode: Optional[int]
    size: Optional[int]
    extra_info: Dict[str, str]

    @property
    def open_mode(self) -> Optional[str]:
        return flags_to_mode(self.flags)


@enum.unique
class ConnectionStatus(enum.Enum):
    ESTABLISHED = "ESTABLISHED"
    SYN_SENT = "SYN_SENT"
    SYN_RECV = "SYN_RECV"
    FIN_WAIT1 = "FIN_WAIT1"
    FIN_WAIT2 = "FIN_WAIT2"
    TIME_WAIT = "TIME_WAIT"
    CLOSE = "CLOSE"
    CLOSE_WAIT = "CLOSE_WAIT"
    LAST_ACK = "LAST_ACK"
    LISTEN = "LISTEN"
    CLOSING = "CLOSING"


@dataclasses.dataclass
class Connection:
    fd: int
    family: int
    type: int
    laddr: Union[Tuple[str, int], str]
    raddr: Union[Tuple[str, int], str]
    status: Optional[ConnectionStatus]
    pid: Optional[int]


@dataclasses.dataclass
class ProcessSignalMasks:
    pending: Set[Union[signal.Signals, int]]  # pylint: disable=no-member
    blocked: Set[Union[signal.Signals, int]]  # pylint: disable=no-member
    ignored: Set[Union[signal.Signals, int]]  # pylint: disable=no-member
    caught: Set[Union[signal.Signals, int]]  # pylint: disable=no-member


@dataclasses.dataclass
class ProcessCPUTimes:
    user: float
    system: float
    children_user: float
    children_system: float


@dataclasses.dataclass
class ThreadInfo:
    id: int  # pylint: disable=invalid-name
    user_time: float
    system_time: float


@dataclasses.dataclass
class SwapInfo:
    total: int
    used: int
    sin: int
    sout: int

    @property
    def free(self) -> int:
        return self.total - self.used

    @property
    def percent(self) -> float:
        return self.used * 100.0 / self.total if self.total else 0.0


@enum.unique
class BatteryStatus(enum.Enum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    UNKNOWN = "unknown"


@dataclasses.dataclass
class BatteryInfo:  # pylint: disable=too-many-instance-attributes
    name: str

    status: BatteryStatus
    percent: float

    energy_full: Optional[int]
    energy_now: Optional[int]
    power_now: Optional[int]

    temperature: Optional[float] = None

    _power_plugged: Optional[bool] = None
    _secsleft: Optional[float] = None

    @property
    def temperature_fahrenheit(self) -> Optional[float]:
        return (self.temperature * 1.8 + 32) if self.temperature is not None else None

    @property
    def power_plugged(self) -> Optional[bool]:
        if self.status == BatteryStatus.CHARGING:
            return True
        elif self.status == BatteryStatus.DISCHARGING:
            return False
        else:
            return self._power_plugged

    @property
    def secsleft(self) -> Optional[float]:
        if self.status in (BatteryStatus.FULL, BatteryStatus.CHARGING) or self.power_plugged:
            return float("inf")
        elif (
            self.status == BatteryStatus.DISCHARGING
            and self.energy_now is not None
            and self.power_now is not None
            and self.power_now > 0
        ):
            return self.energy_now * 3600 / self.power_now
        else:
            return self._secsleft

    @property
    def secsleft_full(self) -> Optional[float]:
        if self.status == BatteryStatus.FULL:
            return 0.0
        elif (
            self.status == BatteryStatus.CHARGING
            and self.energy_full is not None
            and self.energy_now is not None
            and self.power_now is not None
            and self.power_now > 0
        ):
            return (self.energy_full - self.energy_now) * 3600 / self.power_now
        else:
            return None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, status={self.status!r}, "
            f"power_plugged={self.power_plugged!r}, percent={self.percent!r}, "
            f"secsleft={self.secsleft!r}, secsleft_full={self.secsleft_full!r})"
        )


@dataclasses.dataclass
class ACPowerInfo:
    name: str
    is_online: bool


@dataclasses.dataclass
class PowerSupplySensorInfo:
    batteries: List[BatteryInfo]
    ac_supplies: List[ACPowerInfo]

    @property
    def is_on_ac_power(self) -> Optional[bool]:
        if any(supply.is_online for supply in self.ac_supplies):
            # If any AC supplies say they're online, we're definitely on AC power.
            return True

        # If we got here, either a) we have no AC supplies or b) all the AC supplies report that
        # they're offline.

        all_batteries_full = True
        for battery in self.batteries:
            if battery.status == BatteryStatus.CHARGING:
                # If any batteries report they're charging, we're almost definitely on AC power.
                return True
            elif battery.status == BatteryStatus.DISCHARGING:
                # And if any batteries report that they're discharging, there's a very good chance
                # we're not on AC power.
                return False
            elif battery.status != BatteryStatus.FULL:
                all_batteries_full = False

        if self.batteries and all_batteries_full:
            # If we have at least one battery, and *all* of them report they're full, then we're
            # probably plugged in.
            return True

        # If any AC supplies are present, then from above we know they're all reporting as offline,
        # so we can be reasonably confident that we're not on AC power.
        # Otherwise, we don't know.
        return False if self.ac_supplies else None


@dataclasses.dataclass
class TempSensorInfo:
    label: str
    current: float
    high: Optional[float]
    critical: Optional[float]

    @property
    def current_fahrenheit(self) -> float:
        return self.current * 1.8 + 32

    @property
    def high_fahrenheit(self) -> Optional[float]:
        return (self.high * 1.8 + 32) if self.high is not None else None

    @property
    def critical_fahrenheit(self) -> Optional[float]:
        return (self.critical * 1.8 + 32) if self.critical is not None else None


@dataclasses.dataclass
class NetIOCounts:  # pylint: disable=too-many-instance-attributes
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

    def _nowrap(self, cacheobj: Optional["NetIOCounts"]) -> "NetIOCounts":
        if cacheobj is None:
            return dataclasses.replace(self)  # Trick to make a copy

        for field in dataclasses.fields(NetIOCounts):
            self_value = getattr(self, field.name)
            cache_value = getattr(cacheobj, field.name)
            if self_value < cache_value:
                setattr(self, field.name, self_value + cache_value)
                setattr(cacheobj, field.name, self_value + cache_value)

        return cacheobj


@dataclasses.dataclass
class NICAddr:
    family: int
    address: str
    netmask: Optional[str]
    broadcast: Optional[str]
    ptp: Optional[str]


@enum.unique
class NICDuplex(enum.Enum):
    UNKNOWN = 0
    HALF = 1
    FULL = 2


@dataclasses.dataclass
class NICStats:
    isup: bool
    duplex: NICDuplex
    speed: int
    mtu: int


def get_procfs_path() -> str:
    return sys.modules[__package__].PROCFS_PATH  # type: ignore


def get_devfs_path() -> str:
    return sys.modules[__package__].DEVFS_PATH  # type: ignore


def check_rlimit_resource(res: int) -> None:
    if res not in RESOURCE_NUMS:
        raise ValueError("invalid resource specified")


def expand_bitmask(mask: int, *, start: int) -> Iterator[int]:
    i = start
    while mask:
        if mask & 1:
            yield i
        mask >>= 1
        i += 1


def expand_sig_bitmask(
    mask: int, *, include_internal: bool = False
) -> Set[Union[signal.Signals, int]]:  # pylint: disable=no-member
    # It seems that every OS uses the same binary representation
    # for signal sets. Only the size varies.

    res: Set[Union[signal.Signals, int]] = set()  # pylint: disable=no-member

    for sig in expand_bitmask(mask, start=1):  # Bit 0 in the mask corresponds to signal 1
        try:
            res.add(signal.Signals(sig))  # pylint: disable=no-member
        except ValueError:
            if include_internal or getattr(signal, "SIGRTMIN", 10000) <= sig <= getattr(
                signal, "SIGRTMAX", -10000
            ):
                res.add(sig)

    return res


def _iter_null_split_pre(data: bytes) -> Iterator[bytes]:
    i = 0
    while i < len(data):
        zero_index = data.find(b"\0", i)
        if zero_index < 0:
            break
        else:
            yield data[i:zero_index]
            i = zero_index + 1


def parse_cmdline_bytes(cmdline: bytes) -> List[str]:
    return [s.decode() for s in _iter_null_split_pre(cmdline)]


def parse_environ_bytes(env: bytes) -> Dict[str, str]:
    res = {}

    for chunk in _iter_null_split_pre(env):
        index = chunk.find(b"=")
        if index >= 0:
            key = chunk[:index].decode()
            value = chunk[index + 1:].decode()
            res[key] = value

    return res


def flags_to_mode(flags: int) -> str:
    if flags & os.O_ACCMODE == os.O_WRONLY:
        if flags & os.O_APPEND == os.O_APPEND:
            return "a"
        else:
            return "w"
    elif flags & os.O_ACCMODE == os.O_RDWR:
        if flags & os.O_APPEND == os.O_APPEND:
            return "a+"
        else:
            return "r+"
    else:
        return "r"


# https://mypy.readthedocs.io/en/stable/generics.html#declaring-decorators
F = TypeVar("F", bound=Callable[..., Any])  # pylint: disable=invalid-name


def translate_proc_errors(func: F) -> F:
    @functools.wraps(func)
    def wrapper(proc: Union[int, "Process"], *args: Any, **kwargs: Any) -> Any:
        if isinstance(proc, int):
            pid = proc
        else:
            pid = proc.pid

        try:
            return func(proc, *args, **kwargs)
        except ProcessLookupError as ex:
            raise NoSuchProcess(pid=pid) from ex
        except PermissionError as ex:
            raise AccessDenied(pid=pid) from ex

    return cast(F, wrapper)  # pytype: disable=invalid-typevar


def read_file(fname: str) -> str:
    """Read the contents of the given file to a string"""
    with open(fname, encoding="utf8", errors="surrogatescape") as file:
        return file.read()


def read_file_first_line(fname: str) -> str:
    """Read the first line of the given file to a string (removing a single trailing newline if
    one is present)"""

    with open(fname, encoding="utf8", errors="surrogatescape") as file:
        line = file.readline()

    return line[:-1] if line.endswith("\n") else line


def iter_packed_structures(
    data: bytes, struct_type: type, len_attr: str
) -> Iterator[ctypes.Structure]:
    struct_size = ctypes.sizeof(struct_type)

    i = 0
    while i < len(data):
        struct_data = data[i: i + struct_size].ljust(struct_size, b"\0")
        item = struct_type.from_buffer_copy(struct_data)  # type: ignore

        length = getattr(item, len_attr)
        if length == 0:
            yield item
            break

        yield item
        i += length


def decode_inet4(addr: int, *, native: bool = True) -> str:
    parts = [
        (addr & 0xFF000000) >> 24,
        (addr & 0xFF0000) >> 16,
        (addr & 0xFF00) >> 8,
        (addr & 0xFF),
    ]

    if native and sys.byteorder == "little":
        parts = parts[::-1]

    return ".".join(map(str, parts))


def decode_inet4_full(addr: int, port: int, *, native: bool = True) -> Tuple[str, int]:
    return ("", 0) if addr == 0 and port == 0 else (decode_inet4(addr, native=native), port)


def decode_inet6(addr: int, *, native: bool = True) -> str:
    parts = [(addr >> (96 - i * 32)) & 0xFFFFFFFF for i in range(4)]

    if native and sys.byteorder == "little":
        parts = [
            (part & 0xFF000000) >> 24
            | (part & 0xFF0000) >> 8
            | (part & 0xFF00) << 8
            | (part & 0xFF) << 24
            for part in parts
        ]

    return str(
        ipaddress.IPv6Address(sum(part << (i * 32) for i, part in enumerate(reversed(parts))))
    )


def decode_inet6_full(addr: int, port: int, *, native: bool = True) -> Tuple[str, int]:
    return ("", 0) if addr == 0 and port == 0 else (decode_inet6(addr, native=native), port)


if sys.byteorder == "big":

    def cvt_endian_hton(hostval: int, widthbytes: int) -> int:  # pylint: disable=unused-argument
        return hostval

else:

    def cvt_endian_hton(hostval: int, widthbytes: int) -> int:
        return int.from_bytes(hostval.to_bytes(widthbytes, "little"), "big")


cvt_endian_ntoh = cvt_endian_hton


_ALL_FAMILIES = [
    socket.AF_INET,
    socket.AF_INET6,
    socket.AF_UNIX,
]
_ALL_STYPES = [socket.SOCK_STREAM, socket.SOCK_DGRAM]


def conn_kind_to_combos(
    kind: str,
) -> Set[Tuple[socket.AddressFamily, socket.SocketKind]]:  # pylint: disable=no-member
    allowed_families = _ALL_FAMILIES
    allowed_types = _ALL_STYPES

    if kind == "all":
        pass

    elif kind == "inet":
        allowed_families = [socket.AF_INET, socket.AF_INET6]
    elif kind == "inet4":
        allowed_families = [socket.AF_INET]
    elif kind == "inet6":
        allowed_families = [socket.AF_INET6]

    elif kind == "tcp":
        allowed_families = [socket.AF_INET, socket.AF_INET6]
        allowed_types = [socket.SOCK_STREAM]
    elif kind == "tcp4":
        allowed_families = [socket.AF_INET]
        allowed_types = [socket.SOCK_STREAM]
    elif kind == "tcp6":
        allowed_families = [socket.AF_INET6]
        allowed_types = [socket.SOCK_STREAM]

    elif kind == "udp":
        allowed_families = [socket.AF_INET, socket.AF_INET6]
        allowed_types = [socket.SOCK_DGRAM]
    elif kind == "udp4":
        allowed_families = [socket.AF_INET]
        allowed_types = [socket.SOCK_DGRAM]
    elif kind == "udp6":
        allowed_families = [socket.AF_INET6]
        allowed_types = [socket.SOCK_DGRAM]

    elif kind == "unix":
        allowed_families = [socket.AF_UNIX]
    else:
        return set()

    allowed_combos = {(family, stype) for family in allowed_families for stype in allowed_types}

    if kind in ("all", "unix"):
        allowed_combos.add((socket.AF_UNIX, socket.SOCK_SEQPACKET))

    return allowed_combos
