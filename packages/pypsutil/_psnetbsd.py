# pylint: disable=too-few-public-methods,too-many-lines
import ctypes
import dataclasses
import errno
import functools
import os
import socket
import stat
import time
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

from . import _bsd, _cache, _ffi, _psposix, _util
from ._util import (
    Connection,
    ConnectionStatus,
    ProcessCPUTimes,
    ProcessFd,
    ProcessFdType,
    ProcessSignalMasks,
    ProcessStatus,
)

if TYPE_CHECKING:  # pragma: no cover
    from ._process import Process

CTL_KERN = 1
CTL_VM = 2
CTL_VFS = 3
CTL_HW = 6
CTL_PROC = 10

PROC_PID_LIMIT = 2
PROC_PID_LIMIT_TYPE_SOFT = 1
PROC_PID_LIMIT_TYPE_HARD = 2

KERN_CP_TIME = 51
KERN_BOOTTIME = 83
KERN_PROC2 = 47
KERN_PROC_ARGS = 48
KERN_PROC_ALL = 0
KERN_PROC_PID = 1
KERN_PROC_ARGV = 1
KERN_PROC_ENV = 3
KERN_PROC_PATHNAME = 5
KERN_PROC_CWD = 6
KERN_LWP = 64
KERN_FILE2 = 77
KERN_FILE_BYPID = 2

HW_PHYSMEM64 = 13

PCB_ALL = 0

VM_METER = 1
VM_UVMEXP2 = 5

DTYPE_VNODE = 1
DTYPE_SOCKET = 2
DTYPE_PIPE = 3
DTYPE_KQUEUE = 4
VREG = 1
VDIR = 2
VBLK = 3
VCHR = 4
VLNK = 5
VSOCK = 6
VFIFO = 7

LSIDL = 1
LSRUN = 2
LSSLEEP = 3
LSSTOP = 4
LSZOMB = 5
LSONPROC = 7
LSSUSPENDED = 8

MAXCOMLEN = 16

KI_NGROUPS = 16
KI_MAXCOMLEN = 24
KI_WMESGLEN = 8
KI_MAXLOGNAME = 24
KI_MAXEMULLEN = 16
KI_LNAMELEN = 20

KI_NOCPU = 2**64 - 1

rlim_t = ctypes.c_uint64  # pylint: disable=invalid-name

time_t = ctypes.c_int64  # pylint: disable=invalid-name

sa_family_t = ctypes.c_uint8  # pylint: disable=invalid-name
in_port_t = ctypes.c_uint16  # pylint: disable=invalid-name

rlimit_max_value = _ffi.ctypes_int_max(rlim_t)


def _proc_rlimit_getset(proc: "Process", res: int, new_limit: Optional[int], hard: bool) -> int:
    new_limit_raw = rlim_t(new_limit) if new_limit is not None else None
    old_limit = rlim_t(0)

    _bsd.sysctl(  # pytype: disable=wrong-arg-types
        [
            CTL_PROC,
            proc.pid,
            PROC_PID_LIMIT,
            res + 1,
            (PROC_PID_LIMIT_TYPE_HARD if hard else PROC_PID_LIMIT_TYPE_SOFT),
        ],
        new_limit_raw,  # type: ignore
        old_limit,  # type: ignore
    )

    return old_limit.value


def proc_rlimit(
    proc: "Process", res: int, new_limits: Optional[Tuple[int, int]] = None
) -> Tuple[int, int]:
    _util.check_rlimit_resource(res)

    new_soft: Optional[int]
    new_hard: Optional[int]
    if new_limits is not None:
        new_soft = new_limits[0]
        new_hard = new_limits[1]

        if new_soft > rlimit_max_value or new_hard > rlimit_max_value:
            raise OverflowError("resource limit value is too large")
    else:
        new_soft = None
        new_hard = None

    old_soft: Optional[int]
    try:
        old_soft = _proc_rlimit_getset(proc, res, new_soft, False)
    except OSError as ex:
        if ex.errno == errno.EINVAL and new_soft is not None:
            old_soft = None
        else:
            raise

    old_hard = _proc_rlimit_getset(proc, res, new_hard, True)

    if old_soft is None:
        old_soft = _proc_rlimit_getset(proc, res, new_soft, False)

    return old_soft, old_hard


proc_getrlimit = proc_rlimit


@dataclasses.dataclass
class CPUTimes:
    # The order of these fields must match the order of the numbers returned by the kern.cp_time
    # sysctl
    # https://github.com/IIJ-NetBSD/netbsd-src/blob/master/sys/sys/sched.h#L136
    user: float
    nice: float
    system: float
    irq: float
    idle: float


@dataclasses.dataclass
class VirtualMemoryInfo:  # pylint: disable=too-many-instance-attributes
    total: int
    available: int
    used: int
    free: int
    active: int
    inactive: int
    buffers: int
    cached: int
    shared: int
    wired: int

    @property
    def percent(self) -> float:
        return 100 - self.available * 100.0 / self.total


@dataclasses.dataclass
class ProcessMemoryInfo:
    rss: int
    vms: int
    text: int
    data: int
    stack: int


ProcessOpenFile = _util.ProcessOpenFile
ThreadInfo = _util.ThreadInfo


class Timespec(ctypes.Structure):
    _fields_ = [
        ("tv_sec", time_t),
        ("tv_nsec", ctypes.c_long),
    ]

    def to_float(self) -> float:
        return cast(float, self.tv_sec + (self.tv_nsec / 1000000000.0))


class KiSigset(ctypes.Structure):
    _fields_ = [
        ("bits", (ctypes.c_uint32 * 4)),
    ]

    def pack(self) -> int:
        # https://github.com/IIJ-NetBSD/netbsd-src/blob/e4505e0610ceb1b2db8e2a9ed607b4bfa076aa2f/sys/sys/sigtypes.h

        return cast(int, self.bits[0])


class KinfoProc2(ctypes.Structure):
    _fields_ = [
        ("p_forw", ctypes.c_uint64),
        ("p_back", ctypes.c_uint64),
        ("p_paddr", ctypes.c_uint64),
        ("p_addr", ctypes.c_uint64),
        ("p_fd", ctypes.c_uint64),
        ("p_cwdi", ctypes.c_uint64),
        ("p_stats", ctypes.c_uint64),
        ("p_limit", ctypes.c_uint64),
        ("p_vmspace", ctypes.c_uint64),
        ("p_sigacts", ctypes.c_uint64),
        ("p_sess", ctypes.c_uint64),
        ("p_tsess", ctypes.c_uint64),
        ("p_ru", ctypes.c_uint64),
        ("p_eflag", ctypes.c_int32),
        ("p_exitsig", ctypes.c_int32),
        ("p_flag", ctypes.c_int32),
        ("p_pid", ctypes.c_int32),
        ("p_ppid", ctypes.c_int32),
        ("p_sid", ctypes.c_int32),
        ("p__pgid", ctypes.c_int32),
        ("p_tpgid", ctypes.c_int32),
        ("p_uid", ctypes.c_uint32),
        ("p_ruid", ctypes.c_uint32),
        ("p_gid", ctypes.c_uint32),
        ("p_rgid", ctypes.c_uint32),
        ("p_groups", (ctypes.c_uint32 * KI_NGROUPS)),
        ("p_ngroups", ctypes.c_int16),
        ("p_jobc", ctypes.c_int16),
        ("p_tdev", ctypes.c_uint32),
        ("p_estcpu", ctypes.c_uint32),
        ("p_rtime_sec", ctypes.c_uint32),
        ("p_rtime_usec", ctypes.c_uint32),
        ("p_cpticks", ctypes.c_int32),
        ("p_cptcpu", ctypes.c_uint32),
        ("p_swtime", ctypes.c_uint32),
        ("p_slptime", ctypes.c_uint32),
        ("p_schedflags", ctypes.c_int32),
        ("p_uticks", ctypes.c_uint64),
        ("p_sticks", ctypes.c_uint64),
        ("p_iticks", ctypes.c_uint64),
        ("p_tracep", ctypes.c_uint64),
        ("p_traceflag", ctypes.c_int32),
        ("p_holdcnt", ctypes.c_int32),
        ("p_siglist", KiSigset),
        ("p_sigmask", KiSigset),
        ("p_sigignore", KiSigset),
        ("p_sigcatch", KiSigset),
        ("p_stat", ctypes.c_int8),
        ("p_priority", ctypes.c_uint8),
        ("p_usrpri", ctypes.c_uint8),
        ("p_nice", ctypes.c_uint8),
        ("p_xstat", ctypes.c_uint16),
        ("p_acflag", ctypes.c_uint16),
        ("p_comm", (ctypes.c_char * KI_MAXCOMLEN)),
        ("p_wmesg", (ctypes.c_char * KI_WMESGLEN)),
        ("p_wchan", ctypes.c_uint64),
        ("p_login", (ctypes.c_char * KI_MAXLOGNAME)),
        ("p_vm_rssize", ctypes.c_int32),
        ("p_vm_tsize", ctypes.c_int32),
        ("p_vm_dsize", ctypes.c_int32),
        ("p_vm_ssize", ctypes.c_int32),
        ("p_uvalid", ctypes.c_int64),
        ("p_ustart_sec", ctypes.c_uint32),
        ("p_ustart_usec", ctypes.c_uint32),
        ("p_uutime_sec", ctypes.c_uint32),
        ("p_uutime_usec", ctypes.c_uint32),
        ("p_ustime_sec", ctypes.c_uint32),
        ("p_ustime_usec", ctypes.c_uint32),
        ("p_uru_maxrss", ctypes.c_uint64),
        ("p_uru_ixrss", ctypes.c_uint64),
        ("p_uru_idrss", ctypes.c_uint64),
        ("p_uru_isrss", ctypes.c_uint64),
        ("p_uru_minflt", ctypes.c_uint64),
        ("p_uru_majflt", ctypes.c_uint64),
        ("p_uru_nswap", ctypes.c_uint64),
        ("p_uru_inblock", ctypes.c_uint64),
        ("p_uru_oublock", ctypes.c_uint64),
        ("p_uru_msgsnd", ctypes.c_uint64),
        ("p_uru_msgrcv", ctypes.c_uint64),
        ("p_uru_nsignals", ctypes.c_uint64),
        ("p_uru_nvcsw", ctypes.c_uint64),
        ("p_uru_nivcsw", ctypes.c_uint64),
        ("p_uctime_sec", ctypes.c_uint32),
        ("p_uctime_usec", ctypes.c_uint32),
        ("p_cpuid", ctypes.c_uint64),
        ("p_realflag", ctypes.c_uint64),
        ("p_nlwps", ctypes.c_uint64),
        ("p_nrlwps", ctypes.c_uint64),
        ("p_realstat", ctypes.c_uint64),
        ("p_svuid", ctypes.c_uint64),
        ("p_svgid", ctypes.c_uint64),
        ("p_ename", (ctypes.c_char * KI_MAXEMULLEN)),
        ("p_vm_vsize", ctypes.c_int64),
        ("p_vm_msize", ctypes.c_int64),
    ]

    def get_groups(self) -> List[int]:
        return list(self.p_groups[: self.p_ngroups])


class KinfoLwp(ctypes.Structure):
    _fields_ = [
        ("l_forw", ctypes.c_uint64),
        ("l_back", ctypes.c_uint64),
        ("l_laddr", ctypes.c_uint64),
        ("l_addr", ctypes.c_uint64),
        ("l_lid", ctypes.c_int32),
        ("l_flag", ctypes.c_int32),
        ("l_swtime", ctypes.c_uint32),
        ("l_slptime", ctypes.c_uint32),
        ("l_schedflags", ctypes.c_int32),
        ("l_holdcnt", ctypes.c_int32),
        ("l_priority", ctypes.c_uint8),
        ("l_usrpri", ctypes.c_uint8),
        ("l_stat", ctypes.c_int8),
        ("l_pad1", ctypes.c_int8),
        ("l_pad2", ctypes.c_int32),
        ("l_wmesg", (ctypes.c_char * KI_WMESGLEN)),
        ("l_wchan", ctypes.c_uint64),
        ("l_cpuid", ctypes.c_uint64),
        ("l_rtime_sec", ctypes.c_uint32),
        ("l_rtime_usec", ctypes.c_uint32),
        ("l_cpticks", ctypes.c_uint32),
        ("l_pctcpu", ctypes.c_uint32),
        ("l_pid", ctypes.c_uint32),
        ("l_name", (ctypes.c_char * KI_LNAMELEN)),
    ]


class KinfoFile(ctypes.Structure):
    _fields_ = [
        ("ki_fileaddr", ctypes.c_uint64),
        ("ki_flag", ctypes.c_uint32),
        ("ki_iflags", ctypes.c_uint32),
        ("ki_ftype", ctypes.c_uint32),
        ("ki_count", ctypes.c_uint32),
        ("ki_msgcount", ctypes.c_uint32),
        ("ki_usecount", ctypes.c_uint32),
        ("ki_fucred", ctypes.c_uint64),
        ("ki_fuid", ctypes.c_uint32),
        ("ki_fgid", ctypes.c_uint32),
        ("ki_fops", ctypes.c_uint64),
        ("ki_foffset", ctypes.c_uint64),
        ("ki_fdata", ctypes.c_uint64),
        ("ki_vun", ctypes.c_uint64),
        ("ki_vsize", ctypes.c_uint64),
        ("ki_vtype", ctypes.c_uint32),
        ("ki_vtag", ctypes.c_uint32),
        ("ki_vdata", ctypes.c_uint64),
        ("ki_pid", ctypes.c_uint32),
        ("ki_fd", ctypes.c_int32),
        ("ki_ofileflags", ctypes.c_uint32),
        ("_ki_padto64bits", ctypes.c_uint32),
    ]


class Sockaddr(ctypes.Structure):
    _fields_ = [
        ("sa_len", ctypes.c_uint8),
        ("sa_family", sa_family_t),
        ("sa_data", (ctypes.c_char * 14)),
    ]


class InAddr(ctypes.Structure):
    _fields_ = [
        ("s_addr", ctypes.c_uint32),
    ]


class In6Addr(ctypes.Structure):
    _fields_ = [
        ("s6_addr", (ctypes.c_uint8 * 16)),
    ]

    def pack(self) -> int:
        return sum(val << (120 - i * 8) for i, val in enumerate(self.s6_addr))


class SockaddrIn(ctypes.Structure):
    _fields_ = [
        ("sin_len", ctypes.c_uint8),
        ("sin_family", sa_family_t),
        ("sin_port", in_port_t),
        ("sin_addr", InAddr),
        ("sin_zero", (ctypes.c_int8 * 8)),
    ]

    def to_tuple(self) -> Tuple[str, int]:
        return _util.decode_inet4_full(
            self.sin_addr.s_addr, _util.cvt_endian_ntoh(self.sin_port, ctypes.sizeof(in_port_t))
        )


class SockaddrIn6(ctypes.Structure):
    _fields_ = [
        ("sin6_len", ctypes.c_uint8),
        ("sin6_family", sa_family_t),
        ("sin6_port", in_port_t),
        ("sin6_flowinfo", ctypes.c_uint32),
        ("sin6_addr", In6Addr),
        ("sin6_scope_id", ctypes.c_uint32),
    ]

    def to_tuple(self) -> Tuple[str, int]:
        return _util.decode_inet6_full(
            self.sin6_addr.pack(),
            _util.cvt_endian_ntoh(self.sin6_port, ctypes.sizeof(in_port_t)),
            native=False,
        )


class SockaddrUn(ctypes.Structure):
    _fields_ = [
        ("sun_len", ctypes.c_uint8),
        ("sun_family", sa_family_t),
        ("sun_path", (ctypes.c_char * 104)),
    ]


class KinfoPcbAddr(ctypes.Union):
    _fields_ = [
        ("addr", Sockaddr),
        ("_ki_pad", (ctypes.c_char * (256 + 8))),
    ]

    def to_addr(self, family: int) -> Union[Tuple[str, int], str]:
        if self.addr.sa_family == 0:
            return "" if family == socket.AF_UNIX else ("", 0)

        assert self.addr.sa_family == family
        if family == socket.AF_INET:
            return SockaddrIn.from_buffer(self).to_tuple()
        elif family == socket.AF_INET6:
            return SockaddrIn6.from_buffer(self).to_tuple()
        elif family == socket.AF_UNIX:
            return os.fsdecode(SockaddrUn.from_buffer(self).sun_path)
        else:
            raise ValueError


class KinfoPcb(ctypes.Structure):
    _fields_ = [
        ("ki_pcbaddr", ctypes.c_uint64),
        ("ki_ppcbaddr", ctypes.c_uint64),
        ("ki_sockaddr", ctypes.c_uint64),
        ("ki_family", ctypes.c_uint32),
        ("ki_type", ctypes.c_uint32),
        ("ki_protocol", ctypes.c_uint32),
        ("ki_pflags", ctypes.c_uint32),
        ("ki_sostate", ctypes.c_uint32),
        ("ki_prstate", ctypes.c_uint32),
        ("ki_tstate", ctypes.c_int32),
        ("ki_tflags", ctypes.c_uint32),
        ("ki_rcvq", ctypes.c_uint64),
        ("ki_sndq", ctypes.c_uint64),
        ("ki_s", KinfoPcbAddr),
        ("ki_d", KinfoPcbAddr),
        ("ki_inode", ctypes.c_uint64),
        ("ki_vnode", ctypes.c_uint64),
        ("ki_conn", ctypes.c_uint64),
        ("ki_refs", ctypes.c_uint64),
        ("ki_nextref", ctypes.c_uint64),
    ]


class UvmExpSysctl(ctypes.Structure):
    _fields_ = [
        ("pagesize", ctypes.c_int64),
        ("pagemask", ctypes.c_int64),
        ("pageshift", ctypes.c_int64),
        ("npages", ctypes.c_int64),
        ("free", ctypes.c_int64),
        ("active", ctypes.c_int64),
        ("inactive", ctypes.c_int64),
        ("paging", ctypes.c_int64),
        ("wired", ctypes.c_int64),
        ("zeropages", ctypes.c_int64),
        ("reserve_pagedaemon", ctypes.c_int64),
        ("reserve_kernel", ctypes.c_int64),
        ("freemin", ctypes.c_int64),
        ("freetarg", ctypes.c_int64),
        ("inactarg", ctypes.c_int64),
        ("wiredmax", ctypes.c_int64),
        ("nswapdev", ctypes.c_int64),
        ("swpages", ctypes.c_int64),
        ("swpginuse", ctypes.c_int64),
        ("swpgonly", ctypes.c_int64),
        ("nswget", ctypes.c_int64),
        ("unused1", ctypes.c_int64),
        ("cpuhit", ctypes.c_int64),
        ("cpumiss", ctypes.c_int64),
        ("faults", ctypes.c_int64),
        ("traps", ctypes.c_int64),
        ("intrs", ctypes.c_int64),
        ("swtch", ctypes.c_int64),
        ("softs", ctypes.c_int64),
        ("syscalls", ctypes.c_int64),
        ("pageins", ctypes.c_int64),
        ("swapins", ctypes.c_int64),
        ("swapouts", ctypes.c_int64),
        ("pgswapin", ctypes.c_int64),
        ("pgswapout", ctypes.c_int64),
        ("forks", ctypes.c_int64),
        ("forks_ppwait", ctypes.c_int64),
        ("forks_sharevm", ctypes.c_int64),
        ("pga_zerohit", ctypes.c_int64),
        ("pga_zeromiss", ctypes.c_int64),
        ("zeroaborts", ctypes.c_int64),
        ("fltnoram", ctypes.c_int64),
        ("fltnoanon", ctypes.c_int64),
        ("fltpgwait", ctypes.c_int64),
        ("fltpgrele", ctypes.c_int64),
        ("fltrelck", ctypes.c_int64),
        ("fltrelckok", ctypes.c_int64),
        ("fltanget", ctypes.c_int64),
        ("fltanretry", ctypes.c_int64),
        ("fltamcopy", ctypes.c_int64),
        ("fltnamap", ctypes.c_int64),
        ("fltnomap", ctypes.c_int64),
        ("fltlget", ctypes.c_int64),
        ("fltget", ctypes.c_int64),
        ("flt_anon", ctypes.c_int64),
        ("flt_acow", ctypes.c_int64),
        ("flt_obj", ctypes.c_int64),
        ("flt_prcopy", ctypes.c_int64),
        ("flt_przero", ctypes.c_int64),
        ("pdwoke", ctypes.c_int64),
        ("pdrevs", ctypes.c_int64),
        ("unused4", ctypes.c_int64),
        ("pdfreed", ctypes.c_int64),
        ("pdscans", ctypes.c_int64),
        ("pdanscan", ctypes.c_int64),
        ("pdobscan", ctypes.c_int64),
        ("pdreact", ctypes.c_int64),
        ("pdbusy", ctypes.c_int64),
        ("pdpageouts", ctypes.c_int64),
        ("pdpending", ctypes.c_int64),
        ("pddeact", ctypes.c_int64),
        ("anonpages", ctypes.c_int64),
        ("filepages", ctypes.c_int64),
        ("execpages", ctypes.c_int64),
        ("colorhit", ctypes.c_int64),
        ("colormiss", ctypes.c_int64),
        ("ncolors", ctypes.c_int64),
        ("bootpages", ctypes.c_int64),
        ("poolpages", ctypes.c_int64),
        ("countsyncone", ctypes.c_int64),
        ("countsyncall", ctypes.c_int64),
        ("anonunknown", ctypes.c_int64),
        ("anonclean", ctypes.c_int64),
        ("anondirty", ctypes.c_int64),
        ("fileunknown", ctypes.c_int64),
        ("fileclean", ctypes.c_int64),
        ("filedirty", ctypes.c_int64),
        ("fltup", ctypes.c_int64),
        ("fltnoup", ctypes.c_int64),
    ]


class VmTotal(ctypes.Structure):
    _fields_ = [
        ("t_rq", ctypes.c_int16),
        ("t_dw", ctypes.c_int16),
        ("t_pw", ctypes.c_int16),
        ("t_sl", ctypes.c_int16),
        ("_reserved1", ctypes.c_int16),
        ("t_vm", ctypes.c_int32),
        ("t_avm", ctypes.c_int32),
        ("t_rm", ctypes.c_int32),
        ("t_arm", ctypes.c_int32),
        ("t_vmshr", ctypes.c_int32),
        ("t_avmshr", ctypes.c_int32),
        ("t_rmshr", ctypes.c_int32),
        ("t_armshr", ctypes.c_int32),
        ("t_free", ctypes.c_int32),
    ]


def _get_kinfo_proc2_pid(pid: int) -> KinfoProc2:
    proc_info = KinfoProc2()
    length = _bsd.sysctl(
        [CTL_KERN, KERN_PROC2, KERN_PROC_PID, pid, ctypes.sizeof(proc_info), 1], None, proc_info
    )

    if length == 0:
        raise ProcessLookupError

    return proc_info


@_cache.CachedByProcess
def _get_kinfo_proc2(proc: "Process") -> KinfoProc2:
    return _get_kinfo_proc2_pid(proc.pid)


def _list_kinfo_procs2() -> List[KinfoProc2]:
    kinfo_size = ctypes.sizeof(KinfoProc2)

    while True:
        nprocs = (
            _bsd.sysctl([CTL_KERN, KERN_PROC2, KERN_PROC_ALL, 0, kinfo_size, 1000000], None, None)
            // kinfo_size
        )

        proc_arr = (KinfoProc2 * nprocs)()  # pytype: disable=not-callable

        try:
            nprocs = (
                _bsd.sysctl(
                    [CTL_KERN, KERN_PROC2, KERN_PROC_ALL, 0, kinfo_size, nprocs], None, proc_arr
                )
                // kinfo_size
            )
        except OSError as ex:
            # ENOMEM means a range error; retry
            if ex.errno != errno.ENOMEM:
                raise
        else:
            return proc_arr[:nprocs]


def _list_kinfo_lwps(pid: int) -> List[KinfoLwp]:
    kinfo_size = ctypes.sizeof(KinfoLwp)

    while True:
        nprocs = (
            _bsd.sysctl([CTL_KERN, KERN_LWP, pid, kinfo_size, 1000000], None, None) // kinfo_size
        )

        proc_arr = (KinfoLwp * nprocs)()  # pytype: disable=not-callable

        try:
            nprocs = (
                _bsd.sysctl([CTL_KERN, KERN_LWP, pid, kinfo_size, nprocs], None, proc_arr)
                // kinfo_size
            )
        except OSError as ex:
            # ENOMEM means a range error; retry
            if ex.errno != errno.ENOMEM:
                raise
        else:
            return proc_arr[:nprocs]


def _list_kinfo_files(pid: int) -> List[KinfoFile]:
    if pid == 0:
        return []

    kinfo_file_size = ctypes.sizeof(KinfoFile)

    while True:
        nfiles = (
            _bsd.sysctl(
                [CTL_KERN, KERN_FILE2, KERN_FILE_BYPID, pid, kinfo_file_size, 1000000],
                None,
                None,
            )
            // kinfo_file_size
        )

        if nfiles == 0:
            # Check that the process is alive
            _get_kinfo_proc2_pid(pid)
            return []

        files = (KinfoFile * nfiles)()  # pytype: disable=not-callable

        nfiles = (
            _bsd.sysctl(
                [CTL_KERN, KERN_FILE2, KERN_FILE_BYPID, pid, kinfo_file_size, nfiles],
                None,
                files,
            )
            // kinfo_file_size
        )

        if nfiles == 0:
            # Check that the process is alive
            _get_kinfo_proc2_pid(pid)
            return []
        elif nfiles <= len(files):
            return files[:nfiles]


def iter_pid_raw_create_time(
    *,
    ppids: Optional[Set[int]] = None,
    skip_perm_error: bool = False,  # pylint: disable=unused-argument
) -> Iterator[Tuple[int, float]]:
    for kinfo in _list_kinfo_procs2():
        if ppids is not None and kinfo.ki_ppid not in ppids:
            continue

        yield kinfo.p_pid, cast(float, kinfo.p_ustart_sec + kinfo.p_ustart_usec / 1000000.0)


def iter_pids() -> Iterator[int]:
    for kinfo in _list_kinfo_procs2():
        yield kinfo.p_pid


F = TypeVar("F", bound=Callable[..., Any])  # pylint: disable=invalid-name


def _einval_to_esrch(func: F) -> F:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except OSError as ex:
            if ex.errno == errno.EINVAL:
                raise _ffi.build_oserror(errno.ESRCH) from ex
            else:
                raise

    return cast(F, wrapper)  # pytype: disable=invalid-typevar


def proc_num_fds(proc: "Process") -> int:
    return len(_list_kinfo_files(proc.pid))


@_einval_to_esrch
def proc_open_files(proc: "Process") -> List[ProcessOpenFile]:
    return [
        ProcessOpenFile(fd=kfile.ki_fd, path="")
        for kfile in _list_kinfo_files(proc.pid)
        if kfile.ki_ftype == DTYPE_VNODE and kfile.ki_vtype == VREG
    ]


_VTYPE_TO_ST_MODE = {
    VREG: stat.S_IFREG,
    VDIR: stat.S_IFDIR,
    VBLK: stat.S_IFBLK,
    VCHR: stat.S_IFCHR,
    VLNK: stat.S_IFLNK,
    VSOCK: stat.S_IFSOCK,
}


def proc_iter_fds(proc: "Process") -> Iterator[ProcessFd]:
    kfiles = _list_kinfo_files(proc.pid)

    for kfile in kfiles:
        path = ""
        dev = None
        rdev = None
        ino = None
        mode = None
        size = None
        extra_info: Dict[str, Any] = {}

        procfs_fd_path = os.path.join(
            _util.get_procfs_path(), str(proc.pid), "fd", str(kfile.ki_fd)
        )

        if kfile.ki_ftype == DTYPE_VNODE:
            if kfile.ki_vtype == VFIFO:
                fdtype = ProcessFdType.FIFO
            else:
                fdtype = ProcessFdType.FILE
                size = kfile.ki_vsize

            try:
                fd_stat = os.stat(procfs_fd_path)
            except OSError:
                pass
            else:
                if _VTYPE_TO_ST_MODE.get(kfile.ki_vtype) in (stat.S_IFMT(fd_stat.st_mode), None):
                    dev = fd_stat.st_dev
                    rdev = fd_stat.st_rdev
                    ino = fd_stat.st_ino
                    mode = fd_stat.st_mode
                    size = fd_stat.st_size

            if kfile.ki_vtype == VDIR:
                # NetBSD's procfs allows readlink()ing /proc/$PID/fd/$FD if the file descriptor
                # refers to a directory
                try:
                    path = os.readlink(procfs_fd_path)
                except OSError:
                    pass

        elif kfile.ki_ftype == DTYPE_SOCKET:
            fdtype = ProcessFdType.SOCKET

        elif kfile.ki_ftype == DTYPE_PIPE:
            fdtype = ProcessFdType.PIPE

        elif kfile.ki_ftype == DTYPE_KQUEUE:
            fdtype = ProcessFdType.KQUEUE

        else:
            fdtype = ProcessFdType.UNKNOWN

        # Map F* flags to O_* flags
        flags = kfile.ki_flag & ~os.O_ACCMODE
        if kfile.ki_flag & 3:
            flags |= (kfile.ki_flag & 3) - 1

        if kfile.ki_ofileflags & 1:
            flags |= os.O_CLOEXEC
        else:
            flags &= ~os.O_CLOEXEC

        yield ProcessFd(
            path=path,
            fd=kfile.ki_fd,
            fdtype=fdtype,
            flags=flags,
            position=kfile.ki_foffset,
            dev=dev,
            rdev=rdev,
            ino=ino,
            size=size,
            mode=mode,
            extra_info=extra_info,
        )


def proc_connections(proc: "Process", kind: str) -> Iterator[Connection]:
    return pid_connections(proc.pid, kind)


def net_connections(kind: str) -> Iterator[Connection]:
    return pid_connections(-1, kind)


_TCP_STATES = {
    0: ConnectionStatus.CLOSE,
    1: ConnectionStatus.LISTEN,
    2: ConnectionStatus.SYN_SENT,
    3: ConnectionStatus.SYN_RECV,
    4: ConnectionStatus.ESTABLISHED,
    5: ConnectionStatus.CLOSE_WAIT,
    6: ConnectionStatus.FIN_WAIT1,
    7: ConnectionStatus.CLOSING,
    8: ConnectionStatus.LAST_ACK,
    9: ConnectionStatus.FIN_WAIT2,
    10: ConnectionStatus.TIME_WAIT,
}

_SOCK_TYPES = {
    socket.AF_INET: {
        socket.SOCK_STREAM: "inet.tcp",
        socket.SOCK_DGRAM: "inet.udp",
    },
    socket.AF_INET6: {
        socket.SOCK_STREAM: "inet6.tcp6",
        socket.SOCK_DGRAM: "inet6.udp6",
    },
    socket.AF_UNIX: {
        socket.SOCK_STREAM: "local.stream",
        socket.SOCK_DGRAM: "local.dgram",
        socket.SOCK_SEQPACKET: "local.seqpacket",
    },
}


def pid_connections(pid: int, kind: str) -> Iterator[Connection]:
    allowed_combos = _util.conn_kind_to_combos(kind)
    if not allowed_combos:
        return

    kfiles = {
        kfile.ki_fdata: (kfile.ki_pid, kfile.ki_fd)
        for kfile in _list_kinfo_files(pid)
        if kfile.ki_fd >= 0 and kfile.ki_ftype == DTYPE_SOCKET
    }
    if not kfiles:
        return

    for (family, stype) in allowed_combos:
        base_mib = _bsd.sysctlnametomib(
            f"net.{_SOCK_TYPES[family][stype]}.pcblist",
            maxlen=4,
        )

        mib = [
            *base_mib,
            PCB_ALL,
            0,
            ctypes.sizeof(KinfoPcb),
            1000000,
        ]

        kinfo_pcb_data = _bsd.sysctl_bytes_retry(mib, None)
        for kpcb in (KinfoPcb * (len(kinfo_pcb_data) // ctypes.sizeof(KinfoPcb))).from_buffer_copy(
            kinfo_pcb_data
        ):
            try:
                pid, fd = kfiles.pop(kpcb.ki_sockaddr)
            except KeyError:
                continue

            yield Connection(
                family=socket.AddressFamily(kpcb.ki_family),  # pylint: disable=no-member
                type=socket.SocketKind(kpcb.ki_type),  # pylint: disable=no-member
                laddr=kpcb.ki_s.to_addr(kpcb.ki_family),
                raddr=kpcb.ki_d.to_addr(kpcb.ki_family),
                status=(
                    _TCP_STATES[kpcb.ki_tstate]
                    if kpcb.ki_type == socket.SOCK_STREAM and kpcb.ki_family != socket.AF_UNIX
                    else None
                ),
                fd=fd,
                pid=pid,
            )

            if not kfiles:
                return


def pid_raw_create_time(pid: int) -> float:
    kinfo = _get_kinfo_proc2_pid(pid)
    return cast(float, kinfo.p_ustart_sec + kinfo.p_ustart_usec / 1000000.0)


pid_raw_create_time.works_on_zombies = False  # type: ignore[attr-defined]


def translate_create_time(raw_create_time: float) -> float:
    return raw_create_time


_PROC_STATUSES = {
    LSIDL: ProcessStatus.IDLE,
    LSRUN: ProcessStatus.RUNNING,
    LSSLEEP: ProcessStatus.SLEEPING,
    LSSTOP: ProcessStatus.STOPPED,
    LSZOMB: ProcessStatus.ZOMBIE,
    LSONPROC: ProcessStatus.RUNNING,
    LSSUSPENDED: ProcessStatus.SUSPENDED,
}


def proc_status(proc: "Process") -> ProcessStatus:
    return _PROC_STATUSES[_get_kinfo_proc2(proc).p_stat]


def proc_name(proc: "Process") -> str:
    return cast(str, _get_kinfo_proc2(proc).p_comm.decode())


def proc_uids(proc: "Process") -> Tuple[int, int, int]:
    kinfo = _get_kinfo_proc2(proc)
    return kinfo.p_ruid, kinfo.p_uid, kinfo.p_svuid


def proc_gids(proc: "Process") -> Tuple[int, int, int]:
    kinfo = _get_kinfo_proc2(proc)
    return kinfo.p_rgid, kinfo.p_gid, kinfo.p_svgid


def proc_getgroups(proc: "Process") -> List[int]:
    return _get_kinfo_proc2(proc).get_groups()


def _procfs_readlink(proc: "Process", name: str) -> str:
    try:
        return os.readlink(os.path.join(_util.get_procfs_path(), str(proc.pid), name))
    except FileNotFoundError:
        try:
            assert proc.pid >= 0
            if proc.pid != 0:
                os.kill(proc.pid, 0)
        except PermissionError:
            pass

        # It looks like procfs just isn't mounted
        return ""


def proc_cwd(proc: "Process") -> str:
    try:
        return os.fsdecode(
            _bsd.sysctl_bytes_retry(
                [CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_CWD], None, trim_nul=True
            )
        )
    except OSError as ex:
        if ex.errno == errno.EINVAL:
            # KERN_PROC_CWD was added in NetBSD 9; it may not be available
            return _procfs_readlink(proc, "cwd")
        else:
            raise


def proc_exe(proc: "Process") -> str:
    return os.fsdecode(
        _bsd.sysctl_bytes_retry(
            [CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_PATHNAME], None, trim_nul=True
        )
    )


def proc_root(proc: "Process") -> str:
    return _procfs_readlink(proc, "root")


@_einval_to_esrch
def proc_cmdline(proc: "Process") -> List[str]:
    cmdline_nul = _bsd.sysctl_bytes_retry(
        [CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_ARGV], None
    )
    return _util.parse_cmdline_bytes(cmdline_nul)


@_einval_to_esrch
def proc_environ(proc: "Process") -> Dict[str, str]:
    env_data = _bsd.sysctl_bytes_retry([CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_ENV], None)
    return _util.parse_environ_bytes(env_data)


def proc_sigmasks(proc: "Process", *, include_internal: bool = False) -> ProcessSignalMasks:
    kinfo = _get_kinfo_proc2(proc)

    return ProcessSignalMasks(
        pending=_util.expand_sig_bitmask(kinfo.p_siglist.pack(), include_internal=include_internal),
        blocked=_util.expand_sig_bitmask(kinfo.p_sigmask.pack(), include_internal=include_internal),
        ignored=_util.expand_sig_bitmask(
            kinfo.p_sigignore.pack(), include_internal=include_internal
        ),
        caught=_util.expand_sig_bitmask(kinfo.p_sigcatch.pack(), include_internal=include_internal),
    )


def proc_num_threads(proc: "Process") -> int:
    return sum(kinfo.l_stat != LSZOMB for kinfo in _list_kinfo_lwps(proc.pid))


def proc_threads(proc: "Process") -> List[ThreadInfo]:
    threads = []

    for kinfo in _list_kinfo_lwps(proc.pid):
        if kinfo.l_stat == LSZOMB:
            continue

        rtime = kinfo.l_rtime_sec + kinfo.l_rtime_usec / 1000000
        threads.append(
            ThreadInfo(
                id=kinfo.l_lid,
                user_time=rtime,
                system_time=rtime,
            )
        )

    return threads


def proc_num_ctx_switches(proc: "Process") -> int:
    kinfo = _get_kinfo_proc2(proc)
    return cast(int, kinfo.p_uru_nvcsw + kinfo.p_uru_nivcsw)


def proc_cpu_times(proc: "Process") -> ProcessCPUTimes:
    kinfo = _get_kinfo_proc2(proc)

    return ProcessCPUTimes(
        user=kinfo.p_uutime_sec + kinfo.p_uutime_usec / 1000000,
        system=kinfo.p_ustime_sec + kinfo.p_ustime_usec / 1000000,
        children_user=kinfo.p_uctime_sec + kinfo.p_uctime_usec / 1000000,
        children_system=kinfo.p_uctime_sec + kinfo.p_uctime_usec / 1000000,
    )


def proc_memory_info(proc: "Process") -> ProcessMemoryInfo:
    kinfo = _get_kinfo_proc2(proc)

    return ProcessMemoryInfo(
        rss=kinfo.p_vm_rssize * _util.PAGESIZE,
        vms=kinfo.p_vm_msize * _util.PAGESIZE,
        text=kinfo.p_vm_tsize * _util.PAGESIZE,
        data=kinfo.p_vm_dsize * _util.PAGESIZE,
        stack=kinfo.p_vm_ssize * _util.PAGESIZE,
    )


def proc_ppid(proc: "Process") -> int:
    return cast(int, _get_kinfo_proc2(proc).p_ppid)


def proc_pgid(proc: "Process") -> int:
    if proc.pid == 0 or proc._is_cache_enabled():  # pylint: disable=protected-access
        # Either a) pid=0, so we can't use getpgid() (because for that function
        # pid=0 means the current process) or b) we're in a oneshot() and
        # we should retrieve extra information.
        return cast(int, _get_kinfo_proc2(proc).p__pgid)
    else:
        return _psposix.proc_pgid(proc)


def proc_sid(proc: "Process") -> int:
    if proc.pid == 0 or proc._is_cache_enabled():  # pylint: disable=protected-access
        # Either a) pid=0, so we can't use getsid() (because for that function
        # pid=0 means the current process) or b) we're in a oneshot() and
        # we should retrieve extra information.
        return cast(int, _get_kinfo_proc2(proc).p_sid)
    else:
        return _psposix.proc_sid(proc)


def proc_getpriority(proc: "Process") -> int:
    if proc.pid == 0:
        # We don't call _get_kinfo_proc2() if pid != 0 and the cache is enabled because
        # Process.setpriority() can change the priority and make the cache invalid.
        return cast(int, _get_kinfo_proc2(proc).p_nice)
    else:
        return _psposix.proc_getpriority(proc)


def proc_tty_rdev(proc: "Process") -> Optional[int]:
    tdev = _get_kinfo_proc2(proc).p_tdev
    return tdev if tdev != 2**32 - 1 else None


def proc_cpu_num(proc: "Process") -> int:
    cpuid = _get_kinfo_proc2(proc).p_cpuid
    return cast(int, cpuid if cpuid != KI_NOCPU else -1)


def cpu_times() -> CPUTimes:
    cptimes = (ctypes.c_uint64 * 5)()  # pytype: disable=not-callable
    _bsd.sysctl([CTL_KERN, KERN_CP_TIME], None, cptimes)
    return CPUTimes(*(int(item) / _util.CLK_TCK for item in cptimes))


def percpu_times() -> List[CPUTimes]:
    results: List[CPUTimes] = []

    cptimes = (ctypes.c_uint64 * 5)()  # pytype: disable=not-callable

    while True:
        try:
            _bsd.sysctl([CTL_KERN, KERN_CP_TIME, len(results)], None, cptimes)
        except FileNotFoundError:
            break
        else:
            results.append(CPUTimes(*(int(item) / _util.CLK_TCK for item in cptimes)))

    return results


def _get_uvmexp() -> UvmExpSysctl:
    uvmexp = UvmExpSysctl()
    _bsd.sysctl([CTL_VM, VM_UVMEXP2], None, uvmexp)
    return uvmexp


def cpu_stats() -> Tuple[int, int, int, int]:
    uvmexp = _get_uvmexp()
    return uvmexp.swtch, uvmexp.intrs, uvmexp.softs, uvmexp.syscalls


def virtual_memory_total() -> int:
    return _bsd.sysctl_into([CTL_HW, HW_PHYSMEM64], ctypes.c_int64()).value


def virtual_memory() -> VirtualMemoryInfo:
    uvmexp = _get_uvmexp()
    vmtotal = _bsd.sysctl_into([CTL_VM, VM_METER], VmTotal())

    bufmem = _bsd.sysctlbyname_into("vm.bufmem", ctypes.c_long()).value

    return VirtualMemoryInfo(
        total=virtual_memory_total(),
        available=(uvmexp.inactive + uvmexp.free) * uvmexp.pagesize,
        used=vmtotal.t_rm * uvmexp.pagesize,
        free=uvmexp.free * uvmexp.pagesize,
        active=uvmexp.active * uvmexp.pagesize,
        inactive=uvmexp.inactive * uvmexp.pagesize,
        buffers=bufmem,
        cached=uvmexp.filepages * uvmexp.pagesize,
        shared=(vmtotal.t_vmshr + vmtotal.t_rmshr) * uvmexp.pagesize,
        wired=uvmexp.wired * uvmexp.pagesize,
    )


def swap_memory() -> _util.SwapInfo:
    uvmexp = _get_uvmexp()

    return _util.SwapInfo(
        total=uvmexp.swpages * uvmexp.pagesize,
        used=uvmexp.swpginuse * uvmexp.pagesize,
        sin=uvmexp.pageins,
        sout=uvmexp.pdpageouts,
    )


def boot_time() -> float:
    btime = Timespec()
    _bsd.sysctl([CTL_KERN, KERN_BOOTTIME], None, btime)
    return btime.to_float()


def time_since_boot() -> float:
    # Round the result to reduce small variations
    return round(time.time() - boot_time(), 4)


DiskUsage = _psposix.DiskUsage
disk_usage = _psposix.disk_usage
