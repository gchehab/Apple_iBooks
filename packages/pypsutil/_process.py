# Type checkers don't like the wrapper names not existing.
# pylint: disable=too-many-lines
# mypy: ignore-errors
# pytype: disable=module-attr
import collections
import contextlib
import dataclasses
import datetime
import os
import pwd
import resource
import select
import shutil
import signal
import subprocess
import threading
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union, cast

from . import _system, _util
from ._detect import _psimpl
from ._errors import AccessDenied, NoSuchProcess, TimeoutExpired, ZombieProcess
from ._util import translate_proc_errors

ThreadInfo = _util.ThreadInfo

ProcessStatus = _psimpl.ProcessStatus
ProcessSignalMasks = _psimpl.ProcessSignalMasks
ProcessCPUTimes = _psimpl.ProcessCPUTimes
ProcessMemoryInfo = _psimpl.ProcessMemoryInfo
ProcessOpenFile = _psimpl.ProcessOpenFile
ProcessFd = _psimpl.ProcessFd
ProcessFdType = _psimpl.ProcessFdType
Connection = _util.Connection
ConnectionStatus = _util.ConnectionStatus
Uids = collections.namedtuple("Uids", ["real", "effective", "saved"])
Gids = collections.namedtuple("Gids", ["real", "effective", "saved"])

if hasattr(_psimpl, "ProcessMemoryMap"):
    ProcessMemoryMap = _psimpl.ProcessMemoryMap
if hasattr(_psimpl, "ProcessMemoryMapGrouped"):
    ProcessMemoryMapGrouped = _psimpl.ProcessMemoryMapGrouped

if hasattr(_psimpl, "ProcessMemoryFullInfo"):
    ProcessMemoryFullInfo = _psimpl.ProcessMemoryFullInfo
else:
    ProcessMemoryFullInfo = ProcessMemoryInfo


if getattr(_psimpl.pid_raw_create_time, "works_on_zombies", True):

    def raw_create_times_eq(time1: float, time2: float) -> bool:
        return time1 == time2

else:

    def raw_create_times_eq(time1: float, time2: float) -> bool:
        return time1 == time2 or time1 == 0 or time2 == 0


if hasattr(_psimpl, "virtual_memory_total"):
    virtual_memory_total = _psimpl.virtual_memory_total
else:

    def virtual_memory_total() -> int:
        return _system.virtual_memory().total


class Process:  # pylint: disable=too-many-instance-attributes
    _raw_create_time: Optional[float] = None
    _create_time: Optional[float] = None

    def __init__(self, pid: Optional[int] = None) -> None:
        if pid is None:
            pid = os.getpid()

        if pid < 0:
            raise NoSuchProcess(pid=pid)

        self._pid = pid
        self._dead = False
        self._cache_storage = threading.local()
        self._lock = threading.RLock()

        # Code that retrieves self._exitcode must hold both self._lock and self._exitcode_lock.
        # Code that performs a *non-blocking* operation and then may assign to self._exitcode
        # must hold self._lock.
        # Code that performs a *blocking* operation and then may assign to self._exitcode must hold
        # self._exitcode_lock.
        self._exitcode: Optional[int] = None
        self._exitcode_lock = threading.RLock()

        self.raw_create_time()

    @classmethod
    def _create(cls, pid: int, raw_create_time: float) -> "Process":
        proc = object.__new__(cls)
        proc._raw_create_time = raw_create_time  # pylint: disable=protected-access
        proc.__init__(pid)  # pylint: disable=unnecessary-dunder-call
        return cast(Process, proc)

    def _get_cache(self, name: str) -> Any:
        try:
            return self._cache_storage.data[name]
        except AttributeError:
            raise KeyError  # pylint: disable=raise-missing-from

    def _set_cache(self, name: str, value: Any) -> None:
        try:
            self._cache_storage.data[name] = value
        except AttributeError:
            pass

    def _is_cache_enabled(self) -> bool:
        return hasattr(self._cache_storage, "data")

    @property
    def pid(self) -> int:
        return self._pid

    @translate_proc_errors
    def ppid(self) -> int:
        return _psimpl.proc_ppid(self)

    def _parent_unchecked(self) -> Optional["Process"]:
        ppid = self.ppid()
        if ppid <= 0:
            return None

        try:
            return Process(ppid)
        except NoSuchProcess:
            return None

    def parent(self) -> Optional["Process"]:
        self._check_running()
        return self._parent_unchecked()

    def parents(self) -> List["Process"]:
        self._check_running()

        proc = self
        parents: List[Process] = []

        while True:
            proc = proc._parent_unchecked()  # type: ignore  # pylint: disable=protected-access
            if proc is None:
                return parents

            parents.append(proc)

    if hasattr(_psimpl, "proc_child_pids"):

        def children(self, *, recursive: bool = False) -> List["Process"]:
            self._check_running()

            if recursive:
                search_parents = {self}
                children = []
                children_set = set()

                while True:
                    new_search_parents = set()

                    for parent in search_parents:
                        for child_pid in _psimpl.proc_child_pids(parent):
                            try:
                                proc = Process(child_pid)
                            except NoSuchProcess:
                                pass
                            else:
                                if proc not in children_set:
                                    children.append(proc)
                                    children_set.add(proc)
                                    # Look for its children next round
                                    new_search_parents.add(proc)

                    search_parents = new_search_parents
                    if not search_parents:
                        break

            else:
                children = []

                for child_pid in _psimpl.proc_child_pids(self):
                    try:
                        children.append(Process(child_pid))
                    except NoSuchProcess:
                        pass

            return children

    else:

        def children(self, *, recursive: bool = False) -> List["Process"]:
            self._check_running()

            if recursive:
                search_ppids = {self._pid}
                children = []
                children_set = set()

                while True:
                    new_search_ppids = set()

                    # Loop through every process
                    for proc in _process_iter_impl(ppids=search_ppids):
                        if proc not in children_set:
                            children.append(proc)
                            children_set.add(proc)
                            # Look for its children next round
                            new_search_ppids.add(proc.pid)

                    search_ppids = new_search_ppids
                    if not search_ppids:
                        break

                return children

            else:
                return list(_process_iter_impl(ppids={self._pid}))

    @translate_proc_errors
    def raw_create_time(self) -> float:
        if self._raw_create_time is None:
            self._raw_create_time = _psimpl.pid_raw_create_time(self._pid)

        return self._raw_create_time

    def create_time(self) -> float:
        if self._create_time is None:
            self._create_time = _psimpl.translate_create_time(self.raw_create_time())

        return self._create_time

    @translate_proc_errors
    def pgid(self) -> int:
        return _psimpl.proc_pgid(self)

    @translate_proc_errors
    def sid(self) -> int:
        return _psimpl.proc_sid(self)

    @translate_proc_errors
    def status(self) -> ProcessStatus:
        return _psimpl.proc_status(self)

    @translate_proc_errors
    def name(self) -> str:
        return _psimpl.proc_name(self)

    @translate_proc_errors
    def exe(self, *, fallback_cmdline: bool = True) -> str:
        if hasattr(_psimpl, "proc_exe"):
            return _psimpl.proc_exe(self)
        elif fallback_cmdline:
            cmdline = self.cmdline()

            if cmdline:
                lookup_path: Optional[str]
                try:
                    lookup_path = self.environ()["PATH"]
                except (OSError, KeyError, AccessDenied, ZombieProcess):
                    lookup_path = None

                exe = shutil.which(cmdline[0], path=lookup_path)
                if exe:
                    return exe

        return ""

    @translate_proc_errors
    def cmdline(self) -> List[str]:
        return _psimpl.proc_cmdline(self)

    @translate_proc_errors
    def cwd(self) -> str:
        return _psimpl.proc_cwd(self)

    if hasattr(_psimpl, "proc_root"):

        @translate_proc_errors
        def root(self) -> str:
            return _psimpl.proc_root(self)

    @translate_proc_errors
    def environ(self) -> Dict[str, str]:
        return _psimpl.proc_environ(self)

    @translate_proc_errors
    def uids(self) -> Uids:
        return Uids(*_psimpl.proc_uids(self))

    @translate_proc_errors
    def gids(self) -> Gids:
        return Gids(*_psimpl.proc_gids(self))

    @translate_proc_errors
    def getgroups(self) -> List[int]:
        return _psimpl.proc_getgroups(self)

    if hasattr(_psimpl, "proc_fsuid"):

        @translate_proc_errors
        def fsuid(self) -> int:
            return _psimpl.proc_fsuid(self)

    if hasattr(_psimpl, "proc_fsgid"):

        @translate_proc_errors
        def fsgid(self) -> int:
            return _psimpl.proc_fsgid(self)

    def username(self) -> str:
        ruid = self.uids()[0]

        try:
            return pwd.getpwuid(ruid).pw_name
        except KeyError:
            return str(ruid)

    if hasattr(_psimpl, "proc_umask"):

        @translate_proc_errors
        def umask(self) -> Optional[int]:
            return _psimpl.proc_umask(self)

    @translate_proc_errors
    def sigmasks(self, *, include_internal: bool = False) -> ProcessSignalMasks:
        return _psimpl.proc_sigmasks(self, include_internal=include_internal)

    if hasattr(_psimpl, "proc_rlimit"):

        @translate_proc_errors
        def rlimit(self, res: int, new_limits: Optional[Tuple[int, int]] = None) -> Tuple[int, int]:
            if new_limits is not None:
                self._check_running()

                soft, hard = new_limits

                if soft < 0:
                    soft = resource.RLIM_INFINITY
                if hard < 0:
                    hard = resource.RLIM_INFINITY

                if hard != resource.RLIM_INFINITY and (
                    soft > hard or soft == resource.RLIM_INFINITY
                ):
                    raise ValueError("current limit exceeds maximum limit")

                new_limits = (soft, hard)

            return _psimpl.proc_rlimit(self, res, new_limits)

        rlimit.is_atomic = getattr(_psimpl.proc_rlimit, "is_atomic", False)

    if hasattr(_psimpl, "proc_getrlimit"):

        @translate_proc_errors
        def getrlimit(self, res: int) -> Tuple[int, int]:
            return _psimpl.proc_getrlimit(self, res)

        getrlimit.is_atomic = getattr(_psimpl.proc_getrlimit, "is_atomic", False)

    def iter_fds(self) -> Iterator[ProcessFd]:
        try:
            yield from _psimpl.proc_iter_fds(self)
        except ProcessLookupError as ex:
            raise NoSuchProcess(pid=self.pid) from ex
        except PermissionError as ex:
            raise AccessDenied(pid=self.pid) from ex

    if hasattr(_psimpl, "proc_connections"):

        @translate_proc_errors
        def connections(self, kind: str = "inet") -> List[Connection]:
            return list(_psimpl.proc_connections(self, kind))

    @translate_proc_errors
    def num_fds(self) -> int:
        return _psimpl.proc_num_fds(self)

    @translate_proc_errors
    def open_files(self) -> List[ProcessOpenFile]:
        return _psimpl.proc_open_files(self)

    @translate_proc_errors
    def num_threads(self) -> int:
        return _psimpl.proc_num_threads(self)

    @translate_proc_errors
    def threads(self) -> List[ThreadInfo]:
        return _psimpl.proc_threads(self)

    @translate_proc_errors
    def has_terminal(self) -> bool:
        return _psimpl.proc_tty_rdev(self) is not None

    @translate_proc_errors
    def terminal(self) -> Optional[str]:
        tty_rdev = _psimpl.proc_tty_rdev(self)

        if tty_rdev is not None:
            try:
                with os.scandir(os.path.join(_util.get_devfs_path(), "pts")) as pts_names:
                    for entry in pts_names:
                        try:
                            if entry.stat().st_rdev == tty_rdev:
                                return entry.path  # pytype: disable=bad-return-type
                        except OSError:
                            pass
            except OSError:
                pass

            try:
                with os.scandir(_util.get_devfs_path()) as dev_names:
                    for entry in dev_names:
                        if entry.name.startswith("tty") and len(entry.name) > 3:
                            try:
                                if entry.stat().st_rdev == tty_rdev:
                                    return entry.path  # pytype: disable=bad-return-type
                            except OSError:
                                pass
            except OSError:
                pass

            return ""
        else:
            return None

    @translate_proc_errors
    def num_ctx_switches(self) -> int:
        return _psimpl.proc_num_ctx_switches(self)

    if hasattr(_psimpl, "proc_cpu_num"):

        @translate_proc_errors
        def cpu_num(self) -> int:
            return _psimpl.proc_cpu_num(self)

    @translate_proc_errors
    def cpu_times(self) -> ProcessCPUTimes:
        return _psimpl.proc_cpu_times(self)

    if hasattr(_psimpl, "proc_cpu_getaffinity"):

        @translate_proc_errors
        def cpu_getaffinity(self) -> Set[int]:
            return _psimpl.proc_cpu_getaffinity(self)

    if hasattr(_psimpl, "proc_cpu_setaffinity"):

        @translate_proc_errors
        def cpu_setaffinity(self, cpus: Iterable[int]) -> None:
            self._check_running()
            _psimpl.proc_cpu_setaffinity(self, list(cpus))

    @translate_proc_errors
    def memory_info(self) -> ProcessMemoryInfo:
        return _psimpl.proc_memory_info(self)

    if hasattr(_psimpl, "proc_memory_full_info"):

        @translate_proc_errors
        def memory_full_info(self) -> ProcessMemoryFullInfo:
            return _psimpl.proc_memory_full_info(self)

    else:

        def memory_full_info(self) -> ProcessMemoryFullInfo:
            return self.memory_info()

    def memory_percent(self, memtype: str = "rss") -> float:
        if any(field.name == memtype for field in dataclasses.fields(ProcessMemoryInfo)):
            proc_meminfo = self.memory_info()
        elif any(field.name == memtype for field in dataclasses.fields(ProcessMemoryFullInfo)):
            proc_meminfo = self.memory_full_info()
        else:
            raise ValueError(
                f"Bad process memory type {memtype!r} (valid types: "
                f"{[field.name for field in dataclasses.fields(ProcessMemoryFullInfo)]})"
            )

        return getattr(proc_meminfo, memtype) * 100.0 / virtual_memory_total()

    if hasattr(_psimpl, "proc_memory_maps"):

        @translate_proc_errors
        def memory_maps(self) -> List[_psimpl.ProcessMemoryMap]:
            return list(_psimpl.proc_memory_maps(self))

        if hasattr(_psimpl, "group_memory_maps"):

            @translate_proc_errors
            def memory_maps_grouped(self) -> List[_psimpl.ProcessMemoryMapGrouped]:
                maps = self.memory_maps()
                return [
                    _psimpl.group_memory_maps([mmap for mmap in maps if mmap.path == path])
                    for path in {mmap.path for mmap in maps}
                ]

    @translate_proc_errors
    def getpriority(self) -> int:
        return _psimpl.proc_getpriority(self)

    @translate_proc_errors
    def setpriority(self, prio: int) -> None:
        if self._pid == 0:
            # Can't change the kernel's priority
            raise PermissionError

        self._check_running()
        os.setpriority(os.PRIO_PROCESS, self._pid, prio)

    @translate_proc_errors
    def send_signal(self, sig: int) -> None:
        if self._pid == 0:
            # Can't send signals to the kernel
            raise PermissionError

        self._check_running()
        os.kill(self._pid, sig)

    def suspend(self) -> None:
        self.send_signal(signal.SIGSTOP)

    def resume(self) -> None:
        self.send_signal(signal.SIGCONT)

    def terminate(self) -> None:
        self.send_signal(signal.SIGTERM)

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)

    def wait(self, *, timeout: Union[int, float, None] = None) -> Optional[int]:
        # We check is_running() up front so we don't run into PID reuse.
        # After that, we can safely just check pid_exists() or os.waitpid().
        if not self.is_running():
            with self._lock, self._exitcode_lock:
                return self._exitcode

        start_time = time.monotonic() if timeout is not None and timeout > 0 else 0

        # Assume it's a child of the current process by default
        is_child = self._pid > 0

        if timeout is None and self._pid > 0:
            # Wait with no timeout

            # We don't lock on self._lock because this is blocking
            with self._exitcode_lock:
                try:
                    wstatus = os.waitpid(self._pid, 0)[1]
                except ChildProcessError:
                    # Not a child of the current process
                    # Fall through to the polling loop
                    is_child = False
                else:
                    self._dead = True
                    self._exitcode = (
                        -os.WTERMSIG(wstatus)
                        if os.WIFSIGNALED(wstatus)
                        else os.WEXITSTATUS(wstatus)
                    )

                    return self._exitcode

        elif (  # pylint: disable=chained-comparison
            timeout is not None and timeout <= 0 and self._pid > 0
        ):
            # Zero timeout
            try:
                if self._wait_child_poll():
                    return self._exitcode
                else:
                    raise TimeoutExpired(timeout, pid=self._pid)
            except ChildProcessError:
                # We already checked is_running(), so we know it's still running
                raise TimeoutExpired(timeout, pid=self._pid)  # pylint: disable=raise-missing-from

        # On Linux 5.3+ (and Python 3.9+), pidfd_open() may avoid a busy loop
        if hasattr(os, "pidfd_open") and self._pid > 0:
            assert self._pid > 0

            try:
                pidfd = os.pidfd_open(self._pid)  # pylint: disable=no-member
            except OSError:
                pass
            else:
                remaining_time = (
                    None
                    if timeout is None
                    else max((start_time + timeout) - time.monotonic(), 0)
                    if timeout > 0
                    else 0
                )

                readfds, _, _ = select.select([pidfd], [], [], remaining_time)
                os.close(pidfd)
                if not readfds:
                    # Timeout expired, and still not dead
                    raise TimeoutExpired(timeout, pid=self._pid)

            # Dead, but now it may be a zombie, so we need to keep watching it
            # Fall through to the normal monitoring code

        # On macOS and the BSDs, we can do something similar with kqueue
        elif hasattr(select, "kqueue"):
            # pylint: disable=no-member
            kqueue: Optional[select.kqueue] = None
            try:
                kqueue = select.kqueue()
                remaining_time = (
                    None
                    if timeout is None
                    else max((start_time + timeout) - time.monotonic(), 0)
                    if timeout > 0
                    else 0
                )
                events = kqueue.control(
                    [select.kevent(self._pid, select.KQ_FILTER_PROC, fflags=select.KQ_NOTE_EXIT)],
                    1,
                    remaining_time,
                )
                if not events:
                    # Timeout expired, and still not dead
                    raise TimeoutExpired(timeout, pid=self._pid)
            except OSError:
                pass
            finally:
                if kqueue is not None:
                    kqueue.close()

            # Once again, just fall through

        while True:
            if is_child:
                try:
                    if self._wait_child_poll():
                        return self._exitcode
                except ChildProcessError:
                    # Switch to pid_exists()
                    is_child = False
                    # Restart the loop so it gets checked immediately, not 0.01 seconds from now
                    continue
            else:
                if not pid_exists(self._pid):
                    with self._lock, self._exitcode_lock:
                        return self._exitcode

            interval = 0.01
            if timeout is not None:
                remaining_time = (start_time + timeout) - time.monotonic() if timeout > 0 else 0
                if remaining_time <= 0:
                    raise TimeoutExpired(timeout, pid=self._pid)

                interval = min(interval, remaining_time)

            time.sleep(interval)

    def _wait_child_poll(self) -> bool:
        with self._lock:
            wpid, wstatus = os.waitpid(self._pid, os.WNOHANG)

            if wpid == 0:
                return False

            self._dead = True
            self._exitcode = (
                -os.WTERMSIG(wstatus) if os.WIFSIGNALED(wstatus) else os.WEXITSTATUS(wstatus)
            )
            return True

    @contextlib.contextmanager
    def oneshot(self) -> Iterator[None]:
        if not hasattr(self._cache_storage, "data"):
            self._cache_storage.data = {}
            yield
            del self._cache_storage.data
        else:
            yield

    def _check_running(self) -> None:
        if not self.is_running():
            raise NoSuchProcess(pid=self._pid)

    def is_running(self) -> bool:
        with self._lock:
            if self._dead:
                return False

            try:
                self._dead = not raw_create_times_eq(
                    self._raw_create_time, _psimpl.pid_raw_create_time(self._pid)
                )
            except ProcessLookupError:
                self._dead = True
            except PermissionError as ex:
                raise AccessDenied(pid=self._pid) from ex

            return not self._dead

    def __eq__(self, other: Any) -> Union[bool, type(NotImplemented)]:
        if isinstance(other, Process):
            return self._pid == other._pid and raw_create_times_eq(
                self._raw_create_time, other._raw_create_time
            )

        return NotImplemented

    def __hash__(self) -> int:
        return self._pid

    def __repr__(self) -> str:
        try:
            status = self.status().value
        except NoSuchProcess:
            status = "terminated"
        except AccessDenied:
            status = "unknown"

        name = None
        try:
            name = self.name()
        except (NoSuchProcess, AccessDenied):
            pass

        creation = datetime.datetime.fromtimestamp(self.create_time())
        now = datetime.datetime.now()

        if creation.date() == now.date():
            start_time = creation.strftime("%H:%M:%S")
        else:
            start_time = creation.strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"{self.__class__.__name__}(pid={self._pid}, "
            + (f"name={name!r}, " if name is not None else "")
            + f"status={status!r}, started={start_time!r})"
        )


class Popen(Process):
    def __init__(
        self,
        args: Union[List[Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]], str, bytes],
        **kwargs: Any,
    ) -> None:
        proc = subprocess.Popen(args, **kwargs)  # pylint: disable=consider-using-with
        super().__init__(proc.pid)

        self._proc = proc

        self.args = proc.args
        self.stdin = proc.stdin
        self.stdout = proc.stdout
        self.stderr = proc.stdout

    def poll(self) -> Optional[int]:
        res = self._proc.poll()
        if res is not None:
            self._dead = True
        return res

    def wait(  # pylint: disable=arguments-differ
        self, timeout: Union[int, float, None] = None
    ) -> int:
        try:
            res = self._proc.wait(timeout)
        except subprocess.TimeoutExpired as ex:
            raise TimeoutExpired(timeout, self._pid) from ex
        else:
            self._dead = True
            return res

    def communicate(
        self,
        input: Union[str, bytes, None] = None,  # pylint: disable=redefined-builtin
        timeout: Union[int, float, None] = None,
    ) -> Tuple[Union[str, bytes, None], Union[str, bytes, None]]:
        try:
            res = self._proc.communicate(input, timeout)
        except subprocess.TimeoutExpired as ex:
            raise TimeoutExpired(timeout, self._pid) from ex
        else:
            self._dead = True
            return res

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.returncode

    def __enter__(self) -> "Popen":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.stdin is not None:
            self.stdin.close()

        if self.stdout is not None:
            self.stdout.close()

        if self.stderr is not None:
            self.stderr.close()

        self.wait()


def pids() -> List[int]:
    return list(_psimpl.iter_pids())


def process_iter() -> Iterator[Process]:
    return _process_iter_impl(skip_perm_error=False)


def process_iter_available() -> Iterator[Process]:
    return _process_iter_impl(skip_perm_error=True)


_process_iter_cache: Dict[int, Process] = {}
_process_iter_cache_lock = threading.RLock()


def _process_iter_impl(
    *, ppids: Optional[Set[int]] = None, skip_perm_error: bool = False
) -> Iterator[Process]:
    seen_pids = set()

    for (pid, raw_create_time) in _psimpl.iter_pid_raw_create_time(
        ppids=ppids, skip_perm_error=skip_perm_error
    ):
        seen_pids.add(pid)

        try:
            # Check the cache
            with _process_iter_cache_lock:
                proc = _process_iter_cache[pid]
        except KeyError:
            # Cache failure
            pass
        else:
            # Cache hit
            if proc.raw_create_time() == raw_create_time:  # pylint: disable=protected-access
                # It's the same process
                yield proc
                continue
            else:
                # Different process
                with _process_iter_cache_lock:
                    # There's a potential race condition here.
                    # Between the time when we first checked the cache and now,
                    # another thread might have also checked the cache, found
                    # this process doesn't exist, and removed it.
                    # We handle that by using pop() instead of 'del' to remove
                    # the entry, so we don't get an error if it's not present.
                    _process_iter_cache.pop(pid, None)

        proc = Process._create(pid, raw_create_time)  # pylint: disable=protected-access
        with _process_iter_cache_lock:
            # There's also a potential race condition here.
            # Another thread might have already populated the cache entry, and we
            # may be overwriting it.
            # However, the only cost is a small increase in memory because we're
            # keeping track of an extra Process object. That's not enough
            # to be concerned about.
            _process_iter_cache[pid] = proc

        yield proc

    # If we got to the end, clean up the cache

    # List the cached PIDs
    with _process_iter_cache_lock:
        cached_pids = list(_process_iter_cache.keys())

    # Find all of the ones that don't exist anymore
    bad_pids = set(cached_pids) - seen_pids

    # Remove them
    with _process_iter_cache_lock:
        for bad_pid in bad_pids:
            # Potential race condition (similar to the ones described above)
            _process_iter_cache.pop(bad_pid, None)


def pid_exists(pid: int) -> bool:
    if pid < 0:
        return False

    try:
        if pid > 0:
            os.kill(pid, 0)
        else:
            _psimpl.pid_raw_create_time(pid)
    except (ProcessLookupError, NoSuchProcess):
        return False
    except (PermissionError, AccessDenied):
        return True
    else:
        return True


def wait_procs(
    procs: Iterable[Process],
    timeout: Union[int, float, None] = None,
    callback: Optional[Callable[[Process], None]] = None,
) -> Tuple[List[Process], List[Process]]:
    start_time = time.monotonic() if timeout is not None and timeout > 0 else 0

    # We check is_running() up front so we don't run into PID reuse.
    # After that, we can safely just check pid_exists().

    gone = []
    alive = []
    for proc in procs:
        if proc.is_running():
            alive.append(proc)
        else:
            if not hasattr(proc, "returncode"):
                with proc._lock, proc._exitcode_lock:  # pylint: disable=protected-access
                    proc.returncode = proc._exitcode  # pylint: disable=protected-access

            if callback is not None:
                callback(proc)

            gone.append(proc)

    if not alive:
        return gone, alive

    nonchildren = set()

    while True:
        if len(alive) == 1:
            # Only one process left; Process.wait() may be able to optimize.
            proc = alive[0]

            try:
                res = proc.wait(timeout=timeout)
            except TimeoutExpired:
                pass
            else:
                if not isinstance(proc, Popen):
                    proc.returncode = res

                if callback is not None:
                    callback(proc)

                alive.remove(proc)
                gone.append(proc)

            return gone, alive

        for proc in list(alive):
            res = None
            dead = False

            if isinstance(proc, Popen):
                # With Popen, delegate to wait()
                try:
                    proc.wait(timeout=0)
                except TimeoutExpired:
                    pass
                else:
                    dead = True

            elif proc in nonchildren:
                # Not a child of the current process; just check if it exists
                if not pid_exists(proc.pid):
                    proc._dead = dead = True  # pylint: disable=protected-access

                    with proc._lock, proc._exitcode_lock:  # pylint: disable=protected-access
                        res = proc._exitcode  # pylint: disable=protected-access

            else:
                try:
                    # Try waitpid()
                    if proc._wait_child_poll():  # pylint: disable=protected-access
                        # The process died
                        res = proc._exitcode  # pylint: disable=protected-access
                        dead = True

                except ChildProcessError:
                    # Either it died and another thread wait()ed for it, or it isn't a child of the
                    # current process.
                    # Begin treating it like a non-child.

                    if pid_exists(proc.pid):
                        # Check using pid_exists() next time
                        nonchildren.add(proc)
                    else:
                        # It died
                        proc._dead = dead = True  # pylint: disable=protected-access

                        with proc._lock, proc._exitcode_lock:  # pylint: disable=protected-access
                            res = proc._exitcode  # pylint: disable=protected-access

            if dead:
                if not isinstance(proc, Popen):
                    proc.returncode = res

                if callback is not None:
                    callback(proc)

                alive.remove(proc)
                gone.append(proc)

        if not alive:
            break

        interval = 0.01
        if timeout is not None:
            remaining_time = (start_time + timeout) - time.monotonic() if timeout > 0 else 0
            if remaining_time <= 0:
                break

            interval = min(interval, remaining_time)

        time.sleep(interval)

    return gone, alive
