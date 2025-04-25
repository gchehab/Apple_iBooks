# pylint: disable=too-few-public-methods,too-many-lines,fixme
import ctypes
import dataclasses
import errno
import os
import socket
import time
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union, cast

from . import _bsd, _cache, _psposix, _util
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

# XXX: time.CLOCK_BOOTTIME and time.CLOCK_UPTIME added in 3.7
CLOCK_BOOTTIME = getattr(time, "CLOCK_BOOTTIME", 6)
CLOCK_UPTIME = getattr(time, "CLOCK_UPTIME", 5)

CTL_KERN = 1
CTL_VM = 2
CTL_HW = 6
CTL_VFS = 10

KERN_CPTIME = 40
KERN_CPTIME2 = 71
KERN_BOOTTIME = 21
KERN_PROC = 66
KERN_PROC_PID = 1
KERN_PROC_KTHREAD = 7
KERN_PROC_SHOW_THREADS = 0x40000000
KERN_PROC_ARGS = 55
KERN_PROC_CWD = 78
KERN_PROC_VMMAP = 80
KERN_PROC_ARGV = 1
KERN_PROC_ENV = 3
KERN_FILE = 73
KERN_FILE_BYPID = 2

UF_EXCLOSE = 0x1

VM_METER = 1
VM_UVMEXP = 4

HW_CPUSPEED = 12
HW_PHYSMEM64 = 19

VFS_GENERIC = 0
VFS_BCACHESTAT = 3

PROT_READ = 0x01
PROT_WRITE = 0x02
PROT_EXEC = 0x04

DTYPE_VNODE = 1
DTYPE_SOCKET = 2
DTYPE_PIPE = 3
DTYPE_KQUEUE = 4
VREG = 1
VFIFO = 7

SIDL = 1
SRUN = 2
SSLEEP = 3
SSTOP = 4
SDEAD = 6
SONPROC = 7

KI_NGROUPS = 16
KI_MAXCOMLEN = 24
KI_WMESGLEN = 8
KI_MAXLOGNAME = 32
KI_EMULNAMELEN = 8

KI_MNAMELEN = 96
KI_UNPPATHLEN = 104

KI_NOCPU = 2**64 - 1

time_t = ctypes.c_int64  # pylint: disable=invalid-name
suseconds_t = ctypes.c_long  # pylint: disable=invalid-name


@dataclasses.dataclass
class CPUTimes:
    # The order of these fields must match the order of the numbers returned by the kern.cp_time
    # sysctl
    # https://github.com/openbsd/src/blob/master/sys/sys/sched.h#L83
    user: float
    nice: float
    system: float
    lock_spin: float
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


@dataclasses.dataclass
class ProcessMemoryMap:  # pylint: disable=too-many-instance-attributes
    addr_start: int
    addr_end: int
    perms: str
    offset: int
    size: int
    wired_count: int


ProcessOpenFile = _util.ProcessOpenFile
ThreadInfo = _util.ThreadInfo


class Timeval(ctypes.Structure):
    _fields_ = [
        ("tv_sec", time_t),
        ("tv_usec", suseconds_t),
    ]

    def to_float(self) -> float:
        return cast(float, self.tv_sec + (self.tv_usec / 1000000.0))


class KinfoProc(ctypes.Structure):
    _fields_ = [
        ("p_forw", ctypes.c_uint64),
        ("p_back", ctypes.c_uint64),
        ("p_paddr", ctypes.c_uint64),
        ("p_addr", ctypes.c_uint64),
        ("p_fd", ctypes.c_uint64),
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
        ("p_siglist", ctypes.c_int32),
        ("p_sigmask", ctypes.c_uint32),
        ("p_sigignore", ctypes.c_uint32),
        ("p_sigcatch", ctypes.c_uint32),
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
        ("p_ustart_sec", ctypes.c_uint64),
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
        ("p_psflags", ctypes.c_uint32),
        ("p_spare", ctypes.c_int32),
        ("p_svuid", ctypes.c_uint32),
        ("p_svgid", ctypes.c_uint32),
        ("p_emul", (ctypes.c_char * KI_EMULNAMELEN)),
        ("p_rlim_rss_cur", ctypes.c_uint64),
        ("p_cpuid", ctypes.c_uint64),
        ("p_vm_map_size", ctypes.c_uint64),
        ("p_tid", ctypes.c_int32),
        ("p_rtableid", ctypes.c_uint32),
        ("p_pledge", ctypes.c_uint64),
    ]

    def create_time(self) -> float:
        return cast(float, self.p_ustart_sec + self.p_ustart_usec / 1000000.0)

    def get_groups(self) -> List[int]:
        return list(self.p_groups[: self.p_ngroups])


class KinfoFile(ctypes.Structure):
    _fields_ = [
        ("f_fileaddr", ctypes.c_uint64),
        ("f_flag", ctypes.c_uint32),
        ("f_iflags", ctypes.c_uint32),
        ("f_type", ctypes.c_uint32),
        ("f_count", ctypes.c_uint32),
        ("f_msgcount", ctypes.c_uint32),
        ("f_usecount", ctypes.c_uint32),
        ("f_ucred", ctypes.c_uint64),
        ("f_uid", ctypes.c_uint32),
        ("f_gid", ctypes.c_uint32),
        ("f_ops", ctypes.c_uint64),
        ("f_offset", ctypes.c_uint64),
        ("f_data", ctypes.c_uint64),
        ("f_rxfer", ctypes.c_uint64),
        ("f_rwfer", ctypes.c_uint64),
        ("f_seek", ctypes.c_uint64),
        ("f_rbytes", ctypes.c_uint64),
        ("f_wbytes", ctypes.c_uint64),
        ("v_un", ctypes.c_uint64),
        ("v_type", ctypes.c_uint32),
        ("v_tag", ctypes.c_uint32),
        ("v_flag", ctypes.c_uint32),
        ("va_rdev", ctypes.c_uint32),
        ("v_data", ctypes.c_uint64),
        ("v_mount", ctypes.c_uint64),
        ("va_fileid", ctypes.c_uint64),
        ("va_size", ctypes.c_uint64),
        ("va_mode", ctypes.c_uint32),
        ("va_fsid", ctypes.c_uint32),
        ("f_mntonname", (ctypes.c_char * KI_MNAMELEN)),
        ("so_type", ctypes.c_uint32),
        ("so_state", ctypes.c_uint32),
        ("so_pcb", ctypes.c_uint64),
        ("so_protocol", ctypes.c_uint32),
        ("so_family", ctypes.c_uint32),
        ("inp_ppcb", ctypes.c_uint64),
        ("inp_lport", ctypes.c_uint32),
        ("inp_laddru", (ctypes.c_uint32 * 4)),
        ("inp_fport", ctypes.c_uint32),
        ("inp_faddru", (ctypes.c_uint32 * 4)),
        ("unp_conn", ctypes.c_uint64),
        ("pipe_peer", ctypes.c_uint64),
        ("pipe_state", ctypes.c_uint32),
        ("kq_count", ctypes.c_uint32),
        ("kq_state", ctypes.c_uint32),
        ("__unused1", ctypes.c_uint32),
        ("p_pid", ctypes.c_uint32),
        ("fd_fd", ctypes.c_int32),
        ("fd_ofileflags", ctypes.c_uint32),
        ("p_uid", ctypes.c_uint32),
        ("p_gid", ctypes.c_uint32),
        ("p_tid", ctypes.c_uint32),
        ("p_comm", (ctypes.c_char * KI_MAXCOMLEN)),
        ("inp_rtableid", ctypes.c_uint32),
        ("so_splice", ctypes.c_uint64),
        ("so_splicelen", ctypes.c_int64),
        ("so_rcv_cc", ctypes.c_uint64),
        ("so_snd_cc", ctypes.c_uint64),
        ("unp_refs", ctypes.c_uint64),
        ("unp_nextref", ctypes.c_uint64),
        ("unp_addr", ctypes.c_uint64),
        ("unp_path", (ctypes.c_char * KI_UNPPATHLEN)),
        ("inp_proto", ctypes.c_uint32),
        ("t_state", ctypes.c_uint32),
        ("t_rcv_wnd", ctypes.c_uint64),
        ("t_snd_wnd", ctypes.c_uint64),
        ("t_snd_cwnd", ctypes.c_uint64),
        ("va_nlink", ctypes.c_uint32),
    ]


class KinfoVmentry(ctypes.Structure):
    _fields_ = [
        ("kve_start", ctypes.c_ulong),
        ("kve_end", ctypes.c_ulong),
        ("kve_guard", ctypes.c_ulong),
        ("kve_fspace", ctypes.c_ulong),
        ("kve_fspace_augment", ctypes.c_ulong),
        ("kve_offset", ctypes.c_uint64),
        ("kve_wired_count", ctypes.c_int),
        ("kve_etype", ctypes.c_int),
        ("kve_protection", ctypes.c_int),
        ("kve_max_protection", ctypes.c_int),
        ("kve_advice", ctypes.c_int),
        ("kve_inheritance", ctypes.c_int),
        ("kve_flags", ctypes.c_uint8),
    ]


class UvmExp(ctypes.Structure):
    _fields_ = [
        ("pagesize", ctypes.c_int),
        ("pagemask", ctypes.c_int),
        ("pageshift", ctypes.c_int),
        ("npages", ctypes.c_int),
        ("free", ctypes.c_int),
        ("active", ctypes.c_int),
        ("inactive", ctypes.c_int),
        ("paging", ctypes.c_int),
        ("wired", ctypes.c_int),
        ("zeropages", ctypes.c_int),
        ("reserve_pagedaemon", ctypes.c_int),
        ("reserve_kernel", ctypes.c_int),
        ("unused01", ctypes.c_int),
        ("vnodepages", ctypes.c_int),
        ("vtextpages", ctypes.c_int),
        ("freemin", ctypes.c_int),
        ("freetarg", ctypes.c_int),
        ("inactarg", ctypes.c_int),
        ("wiredmax", ctypes.c_int),
        ("anonmin", ctypes.c_int),
        ("vtextmin", ctypes.c_int),
        ("vnodemin", ctypes.c_int),
        ("anonminpct", ctypes.c_int),
        ("vtextminpct", ctypes.c_int),
        ("vnodeminpct", ctypes.c_int),
        ("nswapdev", ctypes.c_int),
        ("swpages", ctypes.c_int),
        ("swpginuse", ctypes.c_int),
        ("swpgonly", ctypes.c_int),
        ("nswget", ctypes.c_int),
        ("nanon", ctypes.c_int),
        ("unused05", ctypes.c_int),
        ("unused06", ctypes.c_int),
        ("faults", ctypes.c_int),
        ("traps", ctypes.c_int),
        ("intrs", ctypes.c_int),
        ("swtch", ctypes.c_int),
        ("softs", ctypes.c_int),
        ("syscalls", ctypes.c_int),
        ("pageins", ctypes.c_int),
        ("unused07", ctypes.c_int),
        ("unused08", ctypes.c_int),
        ("pgswapin", ctypes.c_int),
        ("pgswapout", ctypes.c_int),
        ("forks", ctypes.c_int),
        ("forks_ppwait", ctypes.c_int),
        ("forks_sharevm", ctypes.c_int),
        ("pga_zerohit", ctypes.c_int),
        ("pga_zeromiss", ctypes.c_int),
        ("unused09", ctypes.c_int),
        ("fltnoram", ctypes.c_int),
        ("fltnoanon", ctypes.c_int),
        ("fltnoamap", ctypes.c_int),
        ("fltpgwait", ctypes.c_int),
        ("fltpgrele", ctypes.c_int),
        ("fltrelck", ctypes.c_int),
        ("fltrelckok", ctypes.c_int),
        ("fltanget", ctypes.c_int),
        ("fltanretry", ctypes.c_int),
        ("fltamcopy", ctypes.c_int),
        ("fltnamap", ctypes.c_int),
        ("fltnomap", ctypes.c_int),
        ("fltlget", ctypes.c_int),
        ("fltget", ctypes.c_int),
        ("flt_anon", ctypes.c_int),
        ("flt_acow", ctypes.c_int),
        ("flt_obj", ctypes.c_int),
        ("flt_prcopy", ctypes.c_int),
        ("flt_przero", ctypes.c_int),
        ("pdwoke", ctypes.c_int),
        ("pdrevs", ctypes.c_int),
        ("pdswout", ctypes.c_int),
        ("pdfreed", ctypes.c_int),
        ("pdscans", ctypes.c_int),
        ("pdanscan", ctypes.c_int),
        ("pdobscan", ctypes.c_int),
        ("pdreact", ctypes.c_int),
        ("pdbusy", ctypes.c_int),
        ("pdpageouts", ctypes.c_int),
        ("pdpending", ctypes.c_int),
        ("pddeact", ctypes.c_int),
        ("unused11", ctypes.c_int),
        ("unused12", ctypes.c_int),
        ("unused13", ctypes.c_int),
        ("fpswtch", ctypes.c_int),
        ("kmapent", ctypes.c_int),
    ]


class VmTotal(ctypes.Structure):
    _fields_ = [
        ("t_rq", ctypes.c_int16),
        ("t_dw", ctypes.c_int16),
        ("t_pw", ctypes.c_int16),
        ("t_sl", ctypes.c_int16),
        ("t_sw", ctypes.c_int16),
        ("t_vm", ctypes.c_uint32),
        ("t_avm", ctypes.c_uint32),
        ("t_rm", ctypes.c_uint32),
        ("t_arm", ctypes.c_uint32),
        ("t_vmshr", ctypes.c_uint32),
        ("t_avmshr", ctypes.c_uint32),
        ("t_rmshr", ctypes.c_uint32),
        ("t_armshr", ctypes.c_uint32),
        ("t_free", ctypes.c_uint32),
    ]


class BCacheStats(ctypes.Structure):
    _fields_ = [
        ("numbufs", ctypes.c_int64),
        ("numbufpages", ctypes.c_int64),
        ("numdirtypages", ctypes.c_int64),
        ("numcleanpages", ctypes.c_int64),
        ("pendingwrites", ctypes.c_int64),
        ("pendingreads", ctypes.c_int64),
        ("numwrites", ctypes.c_int64),
        ("numreads", ctypes.c_int64),
        ("cachehits", ctypes.c_int64),
        ("busymapped", ctypes.c_int64),
        ("dmapages", ctypes.c_int64),
        ("highpages", ctypes.c_int64),
        ("delwribufs", ctypes.c_int64),
        ("kvaslots", ctypes.c_int64),
        ("kvaslots_avail", ctypes.c_int64),
        ("highflips", ctypes.c_int64),
        ("highflops", ctypes.c_int64),
        ("dmaflips", ctypes.c_int64),
    ]


def _get_kinfo_proc_pid(pid: int) -> KinfoProc:
    proc_info = KinfoProc()
    length = _bsd.sysctl(
        [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid, ctypes.sizeof(proc_info), 1], None, proc_info
    )

    if length == 0:
        raise ProcessLookupError

    return proc_info


@_cache.CachedByProcess
def _get_kinfo_proc(proc: "Process") -> KinfoProc:
    return _get_kinfo_proc_pid(proc.pid)


def _list_kinfo_procs() -> List[KinfoProc]:
    kinfo_size = ctypes.sizeof(KinfoProc)

    while True:
        nprocs = (
            _bsd.sysctl(
                [CTL_KERN, KERN_PROC, KERN_PROC_KTHREAD, 0, kinfo_size, 1000000], None, None
            )
            // kinfo_size
        )

        proc_arr = (KinfoProc * nprocs)()  # pytype: disable=not-callable

        try:
            nprocs = (
                _bsd.sysctl(
                    [CTL_KERN, KERN_PROC, KERN_PROC_KTHREAD, 0, kinfo_size, nprocs], None, proc_arr
                )
                // kinfo_size
            )
        except OSError as ex:
            # ENOMEM means a range error; retry
            if ex.errno != errno.ENOMEM:
                raise
        else:
            return proc_arr[:nprocs]


def _list_kinfo_threads(pid: int) -> List[KinfoProc]:
    kinfo_size = ctypes.sizeof(KinfoProc)

    while True:
        nprocs = (
            _bsd.sysctl(
                [
                    CTL_KERN,
                    KERN_PROC,
                    KERN_PROC_PID | KERN_PROC_SHOW_THREADS,
                    pid,
                    kinfo_size,
                    1000000,
                ],
                None,
                None,
            )
            // kinfo_size
        )

        proc_arr = (KinfoProc * nprocs)()  # pytype: disable=not-callable

        try:
            nprocs = (
                _bsd.sysctl(
                    [
                        CTL_KERN,
                        KERN_PROC,
                        KERN_PROC_PID | KERN_PROC_SHOW_THREADS,
                        pid,
                        kinfo_size,
                        nprocs,
                    ],
                    None,
                    proc_arr,
                )
                // kinfo_size
            )
        except OSError as ex:
            # ENOMEM means a range error; retry
            if ex.errno != errno.ENOMEM:
                raise
        else:
            if nprocs == 0:
                raise ProcessLookupError

            return proc_arr[:nprocs]


def _list_kinfo_files(pid: int) -> List[KinfoFile]:
    if pid == 0:
        return []

    kinfo_file_size = ctypes.sizeof(KinfoFile)

    while True:
        nfiles = (
            _bsd.sysctl(
                [CTL_KERN, KERN_FILE, KERN_FILE_BYPID, pid, kinfo_file_size, 1000000],
                None,
                None,
            )
            // kinfo_file_size
        )

        files = (KinfoFile * nfiles)()  # pytype: disable=not-callable

        try:
            nfiles = (
                _bsd.sysctl(
                    [CTL_KERN, KERN_FILE, KERN_FILE_BYPID, pid, kinfo_file_size, nfiles],
                    None,
                    files,
                )
                // kinfo_file_size
            )
        except OSError as ex:
            # ENOMEM means a range error; retry
            if ex.errno != errno.ENOMEM:
                raise
        else:
            return files[:nfiles]


def iter_pid_raw_create_time(
    *,
    ppids: Optional[Set[int]] = None,
    skip_perm_error: bool = False,  # pylint: disable=unused-argument
) -> Iterator[Tuple[int, float]]:
    for kinfo in _list_kinfo_procs():
        if ppids is not None and kinfo.p_ppid not in ppids:
            continue

        yield kinfo.p_pid, cast(float, kinfo.p_ustart_sec + kinfo.p_ustart_usec / 1000000.0)


def iter_pids() -> Iterator[int]:
    for kinfo in _list_kinfo_procs():
        yield kinfo.p_pid


def proc_num_fds(proc: "Process") -> int:
    return sum(kfile.fd_fd >= 0 for kfile in _list_kinfo_files(proc.pid))


def proc_open_files(proc: "Process") -> List[ProcessOpenFile]:
    return [
        ProcessOpenFile(fd=kfile.fd_fd, path="")
        for kfile in _list_kinfo_files(proc.pid)
        if kfile.fd_fd >= 0 and kfile.f_type == DTYPE_VNODE and kfile.v_type == VREG
    ]


def proc_iter_fds(proc: "Process") -> Iterator[ProcessFd]:
    for kfile in _list_kinfo_files(proc.pid):
        if kfile.fd_fd < 0:
            continue

        # This will succeed if it was properly initialized with a non-NULL fp in fill_file().
        # That should be true since we use KERN_FILE_BYPID and we ignore negative `fd_fd`s.
        assert kfile.f_count != 0

        path = ""
        ino = None
        dev = None
        rdev = None
        mode = None
        size = None

        extra_info = {}
        position = 0
        if kfile.f_offset != -1:
            # All these fields should be initialized properly
            position = kfile.f_offset
            extra_info["rbytes"] = kfile.f_rbytes
            extra_info["wbytes"] = kfile.f_wbytes
            extra_info["rxfer"] = kfile.f_rxfer
            extra_info["rwfer"] = kfile.f_rwfer

        if kfile.f_type == DTYPE_VNODE:
            if kfile.v_type == VFIFO:
                fdtype = ProcessFdType.FIFO
            else:
                fdtype = ProcessFdType.FILE

            if kfile.va_mode != 0:
                # The va_* fields were filled in
                ino = kfile.va_fileid
                mode = kfile.va_mode
                dev = kfile.va_fsid
                # It seems va_rdev may be 0 when it shouldn't be sometimes
                rdev = kfile.va_rdev or None
                size = kfile.va_size
                extra_info["nlink"] = kfile.va_nlink

        elif kfile.f_type == DTYPE_SOCKET:
            fdtype = ProcessFdType.SOCKET
            extra_info["type"] = kfile.so_type
            extra_info["protocol"] = kfile.so_protocol
            extra_info["family"] = kfile.so_family

            if kfile.so_family == socket.AF_UNIX:
                path = os.fsdecode(kfile.unp_path)

            elif kfile.so_family == socket.AF_INET:
                extra_info["local_addr"] = _util.decode_inet4_full(
                    kfile.inp_laddru[0],
                    _util.cvt_endian_ntoh(kfile.inp_lport, ctypes.sizeof(ctypes.c_uint16)),
                )
                extra_info["foreign_addr"] = _util.decode_inet4_full(
                    kfile.inp_faddru[0],
                    _util.cvt_endian_ntoh(kfile.inp_fport, ctypes.sizeof(ctypes.c_uint16)),
                )

            elif kfile.so_family == socket.AF_INET6:
                extra_info["local_addr"] = _util.decode_inet6_full(
                    _pack_addr6(kfile.inp_laddru),
                    _util.cvt_endian_ntoh(kfile.inp_lport, ctypes.sizeof(ctypes.c_uint16)),
                )
                extra_info["foreign_addr"] = _util.decode_inet6_full(
                    _pack_addr6(kfile.inp_faddru),
                    _util.cvt_endian_ntoh(kfile.inp_fport, ctypes.sizeof(ctypes.c_uint16)),
                )

        elif kfile.f_type == DTYPE_PIPE:
            fdtype = ProcessFdType.PIPE

        elif kfile.f_type == DTYPE_KQUEUE:
            fdtype = ProcessFdType.KQUEUE
            extra_info["kq_count"] = kfile.kq_count

        else:
            fdtype = ProcessFdType.UNKNOWN

        # Map F* flags to O_* flags
        flags = kfile.f_flag & ~os.O_ACCMODE
        if kfile.f_flag & 3:
            flags |= (kfile.f_flag & 3) - 1

        if kfile.fd_ofileflags & UF_EXCLOSE:
            flags |= os.O_CLOEXEC
        else:
            flags &= ~os.O_CLOEXEC

        yield ProcessFd(
            path=path,
            fd=kfile.fd_fd,
            fdtype=fdtype,
            flags=flags,
            position=position,
            dev=dev,
            rdev=rdev,
            ino=ino,
            size=size,
            mode=mode,
            extra_info=extra_info,
        )


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


def _pack_addr6(addr: Iterable[int]) -> int:
    return sum(val << (96 - i * 32) for i, val in enumerate(addr))


def proc_connections(proc: "Process", kind: str) -> Iterator[Connection]:
    return pid_connections(proc.pid, kind)


def net_connections(kind: str) -> Iterator[Connection]:
    return pid_connections(-1, kind)


def pid_connections(pid: int, kind: str) -> Iterator[Connection]:
    allowed_combos = _util.conn_kind_to_combos(kind)
    if not allowed_combos:
        return

    for kfile in _list_kinfo_files(pid):
        if kfile.fd_fd < 0 or kfile.f_type != DTYPE_SOCKET:
            continue

        family = socket.AddressFamily(kfile.so_family)  # pylint: disable=no-member
        stype = socket.SocketKind(kfile.so_type)  # pylint: disable=no-member
        if (family, stype) not in allowed_combos:
            continue

        laddr: Union[Tuple[str, int], str]
        raddr: Union[Tuple[str, int], str]
        if family == socket.AF_INET:
            laddr = _util.decode_inet4_full(
                kfile.inp_laddru[0],
                _util.cvt_endian_ntoh(kfile.inp_lport, ctypes.sizeof(ctypes.c_uint16)),
            )
            raddr = _util.decode_inet4_full(
                kfile.inp_faddru[0],
                _util.cvt_endian_ntoh(kfile.inp_fport, ctypes.sizeof(ctypes.c_uint16)),
            )

        elif family == socket.AF_INET6:
            laddr = _util.decode_inet6_full(
                _pack_addr6(kfile.inp_laddru),
                _util.cvt_endian_ntoh(kfile.inp_lport, ctypes.sizeof(ctypes.c_uint16)),
            )
            raddr = _util.decode_inet6_full(
                _pack_addr6(kfile.inp_faddru),
                _util.cvt_endian_ntoh(kfile.inp_fport, ctypes.sizeof(ctypes.c_uint16)),
            )

        elif family == socket.AF_UNIX:
            laddr = os.fsdecode(kfile.unp_path)
            raddr = ""
        else:
            # We shouldn't get here
            continue

        status = None
        if stype == socket.SOCK_STREAM and family != socket.AF_UNIX:
            status = _TCP_STATES[kfile.t_state]

        yield Connection(
            family=family,
            type=stype,
            laddr=laddr,
            raddr=raddr,
            status=status,
            fd=kfile.fd_fd,
            pid=kfile.p_pid,
        )


def pid_raw_create_time(pid: int) -> float:
    return _get_kinfo_proc_pid(pid).create_time()


pid_raw_create_time.works_on_zombies = False  # type: ignore[attr-defined]


def translate_create_time(raw_create_time: float) -> float:
    return raw_create_time


_PROC_STATUSES = {
    SIDL: ProcessStatus.IDLE,
    SRUN: ProcessStatus.RUNNING,
    SSLEEP: ProcessStatus.SLEEPING,
    SSTOP: ProcessStatus.STOPPED,
    SDEAD: ProcessStatus.ZOMBIE,
    SONPROC: ProcessStatus.RUNNING,  # 7 is SONPROC; i.e. actually executing
}


def proc_status(proc: "Process") -> ProcessStatus:
    return _PROC_STATUSES[_get_kinfo_proc(proc).p_stat]


def proc_name(proc: "Process") -> str:
    return cast(str, _get_kinfo_proc(proc).p_comm.decode())


def proc_uids(proc: "Process") -> Tuple[int, int, int]:
    kinfo = _get_kinfo_proc(proc)
    return kinfo.p_ruid, kinfo.p_uid, kinfo.p_svuid


def proc_gids(proc: "Process") -> Tuple[int, int, int]:
    kinfo = _get_kinfo_proc(proc)
    return kinfo.p_rgid, kinfo.p_gid, kinfo.p_svgid


def proc_getgroups(proc: "Process") -> List[int]:
    return _get_kinfo_proc(proc).get_groups()


def proc_cwd(proc: "Process") -> str:
    return os.fsdecode(
        _bsd.sysctl_bytes_retry([CTL_KERN, KERN_PROC_CWD, proc.pid], None, trim_nul=True)
    )


def _skip_ptrs(data: bytes) -> bytes:
    ptrsize = ctypes.sizeof(ctypes.c_void_p)
    i = 0
    while ctypes.c_void_p.from_buffer_copy(data, i).value:
        i += ptrsize
    return data[i + ptrsize:]


def proc_cmdline(proc: "Process") -> List[str]:
    cmdline_nul = _bsd.sysctl_bytes_retry(
        [CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_ARGV], None
    )
    return _util.parse_cmdline_bytes(_skip_ptrs(cmdline_nul))


def proc_environ(proc: "Process") -> Dict[str, str]:
    env_data = _bsd.sysctl_bytes_retry([CTL_KERN, KERN_PROC_ARGS, proc.pid, KERN_PROC_ENV], None)
    return _util.parse_environ_bytes(_skip_ptrs(env_data))


def proc_sigmasks(proc: "Process", *, include_internal: bool = False) -> ProcessSignalMasks:
    kinfo = _get_kinfo_proc(proc)

    return ProcessSignalMasks(
        pending=_util.expand_sig_bitmask(kinfo.p_siglist, include_internal=include_internal),
        blocked=_util.expand_sig_bitmask(kinfo.p_sigmask, include_internal=include_internal),
        ignored=_util.expand_sig_bitmask(kinfo.p_sigignore, include_internal=include_internal),
        caught=_util.expand_sig_bitmask(kinfo.p_sigcatch, include_internal=include_internal),
    )


def proc_num_threads(proc: "Process") -> int:
    return sum(kinfo.p_tid != -1 for kinfo in _list_kinfo_threads(proc.pid))


def proc_threads(proc: "Process") -> List[ThreadInfo]:
    threads = []

    for kinfo in _list_kinfo_threads(proc.pid):
        if kinfo.p_tid == -1:
            continue

        threads.append(
            ThreadInfo(
                id=kinfo.p_tid,
                user_time=kinfo.p_uutime_sec + kinfo.p_uutime_usec / 1000000,
                system_time=kinfo.p_ustime_sec + kinfo.p_ustime_usec / 1000000,
            )
        )

    return threads


def proc_num_ctx_switches(proc: "Process") -> int:
    kinfo = _get_kinfo_proc(proc)
    return cast(int, kinfo.p_uru_nvcsw + kinfo.p_uru_nivcsw)


def proc_cpu_times(proc: "Process") -> ProcessCPUTimes:
    kinfo = _get_kinfo_proc(proc)

    return ProcessCPUTimes(
        user=kinfo.p_uutime_sec + kinfo.p_uutime_usec / 1000000,
        system=kinfo.p_ustime_sec + kinfo.p_ustime_usec / 1000000,
        children_user=kinfo.p_uctime_sec + kinfo.p_uctime_usec / 1000000,
        children_system=kinfo.p_uctime_sec + kinfo.p_uctime_usec / 1000000,
    )


def proc_memory_info(proc: "Process") -> ProcessMemoryInfo:
    kinfo = _get_kinfo_proc(proc)

    return ProcessMemoryInfo(
        rss=kinfo.p_vm_rssize * _util.PAGESIZE,
        # https://github.com/openbsd/src/blob/e30a1d6dd5339d5e891ea059615207830954c502/bin/ps
        # /print.c#L537
        vms=(kinfo.p_vm_tsize + kinfo.p_vm_dsize + kinfo.p_vm_ssize) * _util.PAGESIZE,
        text=kinfo.p_vm_tsize * _util.PAGESIZE,
        data=kinfo.p_vm_dsize * _util.PAGESIZE,
        stack=kinfo.p_vm_ssize * _util.PAGESIZE,
    )


def proc_memory_maps(proc: "Process") -> Iterator[ProcessMemoryMap]:
    while True:
        old_len = _bsd.sysctl([CTL_KERN, KERN_PROC_VMMAP, proc.pid], None, None)

        buf = (
            KinfoVmentry * (old_len // ctypes.sizeof(KinfoVmentry))
        )()  # pytype: disable=not-callable

        try:
            old_len = _bsd.sysctl([CTL_KERN, KERN_PROC_VMMAP, proc.pid], None, buf)
        except OSError as ex:
            if ex.errno != errno.ENOMEM:
                raise
        else:
            kentries = buf[: old_len // ctypes.sizeof(KinfoVmentry)]
            break

    for kentry in kentries:
        perms = (
            ("r" if kentry.kve_protection & PROT_READ else "-")
            + ("w" if kentry.kve_protection & PROT_WRITE else "-")
            + ("x" if kentry.kve_protection & PROT_EXEC else "-")
        )

        yield ProcessMemoryMap(
            addr_start=kentry.kve_start,
            addr_end=kentry.kve_end,
            perms=perms,
            offset=kentry.kve_offset,
            size=(kentry.kve_end - kentry.kve_start),
            wired_count=kentry.kve_wired_count,
        )


def proc_ppid(proc: "Process") -> int:
    return cast(int, _get_kinfo_proc(proc).p_ppid)


def proc_pgid(proc: "Process") -> int:
    if proc.pid != 0 and not proc._is_cache_enabled():  # pylint: disable=protected-access
        try:
            return _psposix.proc_pgid(proc)
        except PermissionError:
            pass

    return cast(int, _get_kinfo_proc(proc).p__pgid)


def proc_sid(proc: "Process") -> int:
    if proc.pid != 0 and not proc._is_cache_enabled():  # pylint: disable=protected-access
        try:
            return _psposix.proc_sid(proc)
        except PermissionError:
            pass

    return cast(int, _get_kinfo_proc(proc).p_sid)


def proc_getpriority(proc: "Process") -> int:
    if proc.pid == 0:
        # We don't call _get_kinfo_proc() if pid != 0 and the cache is enabled because
        # Process.setpriority() can change the priority and make the cache invalid.
        return cast(int, _get_kinfo_proc(proc).p_nice)
    else:
        return _psposix.proc_getpriority(proc)


def proc_tty_rdev(proc: "Process") -> Optional[int]:
    tdev = _get_kinfo_proc(proc).p_tdev
    return tdev if tdev != 2**32 - 1 else None


def proc_cpu_num(proc: "Process") -> int:
    cpuid = _get_kinfo_proc(proc).p_cpuid
    return cast(int, cpuid if cpuid != KI_NOCPU else -1)


def cpu_times() -> CPUTimes:
    cptimes = (ctypes.c_long * 6)()  # pytype: disable=not-callable
    _bsd.sysctl([CTL_KERN, KERN_CPTIME], None, cptimes)
    return CPUTimes(*(int(item) / _util.CLK_TCK for item in cptimes))


def percpu_times() -> List[CPUTimes]:
    results: List[CPUTimes] = []

    cptimes = (ctypes.c_long * 6)()  # pytype: disable=not-callable

    while True:
        try:
            _bsd.sysctl([CTL_KERN, KERN_CPTIME2, len(results)], None, cptimes)
        except FileNotFoundError:
            break
        else:
            results.append(CPUTimes(*(int(item) / _util.CLK_TCK for item in cptimes)))

    return results


def _get_uvmexp() -> UvmExp:
    return _bsd.sysctl_into([CTL_VM, VM_UVMEXP], UvmExp())


def cpu_stats() -> Tuple[int, int, int, int]:
    uvmexp = _get_uvmexp()
    return (
        ctypes.c_uint(uvmexp.swtch).value,
        ctypes.c_uint(uvmexp.intrs).value,
        ctypes.c_uint(uvmexp.softs).value,
        ctypes.c_uint(uvmexp.syscalls).value,
    )


def cpu_freq() -> Optional[Tuple[float, float, float]]:
    try:
        return float(_bsd.sysctl_into([CTL_HW, HW_CPUSPEED], ctypes.c_int()).value), 0.0, 0.0
    except OSError:
        return None


def virtual_memory_total() -> int:
    return _bsd.sysctl_into([CTL_HW, HW_PHYSMEM64], ctypes.c_int64()).value


def virtual_memory() -> VirtualMemoryInfo:
    uvmexp = _get_uvmexp()
    vmtotal = _bsd.sysctl_into([CTL_VM, VM_METER], VmTotal())
    bcstats = _bsd.sysctl_into([CTL_VFS, VFS_GENERIC, VFS_BCACHESTAT], BCacheStats())

    return VirtualMemoryInfo(
        total=virtual_memory_total(),
        available=(uvmexp.inactive + uvmexp.free) * uvmexp.pagesize,
        used=vmtotal.t_rm * uvmexp.pagesize,
        free=uvmexp.free * uvmexp.pagesize,
        active=uvmexp.active * uvmexp.pagesize,
        inactive=uvmexp.inactive * uvmexp.pagesize,
        buffers=bcstats.numbufpages * uvmexp.pagesize,
        cached=0,
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
    btime = Timeval()
    _bsd.sysctl([CTL_KERN, KERN_BOOTTIME], None, btime)
    return btime.to_float()


def time_since_boot() -> float:
    return time.clock_gettime(CLOCK_BOOTTIME)


def uptime() -> float:
    return time.clock_gettime(CLOCK_UPTIME)


DiskUsage = _psposix.DiskUsage
disk_usage = _psposix.disk_usage
