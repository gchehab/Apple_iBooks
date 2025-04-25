import os
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    overload,
)

from typing_extensions import Literal

import pypsutil

AF_LINK = pypsutil.AF_LINK


class Process:
    _proc: pypsutil.Process

    def __init__(self, pid: Optional[int] = None) -> None:
        self._proc = pypsutil.Process(pid)

    @classmethod
    def _wrap(cls, proc: pypsutil.Process) -> "Process":
        res = object.__new__(Process)
        res._proc = proc  # pylint: disable=protected-access
        return res

    @property
    def pid(self) -> int:
        return self._proc.pid

    def ppid(self) -> int:
        return self._proc.ppid()

    def parent(self) -> Optional["Process"]:
        parent = self._proc.parent()
        return Process._wrap(parent) if parent is not None else None

    def parents(self) -> List["Process"]:
        return [Process._wrap(proc) for proc in self._proc.parents()]

    def children(self, recursive: bool = False) -> List["Process"]:
        return [Process._wrap(proc) for proc in self._proc.children(recursive=recursive)]

    def create_time(self) -> float:
        return self._proc.create_time()

    def status(self) -> pypsutil.ProcessStatus:
        return self._proc.status()

    def name(self) -> str:
        return self._proc.name()

    def exe(self) -> str:
        return self._proc.exe()

    def cmdline(self) -> List[str]:
        return self._proc.cmdline()

    def cwd(self) -> str:
        return self._proc.cwd()

    def environ(self) -> Dict[str, str]:
        return self._proc.environ()

    def uids(self) -> pypsutil.Uids:
        return self._proc.uids()

    def gids(self) -> pypsutil.Gids:
        return self._proc.gids()

    def username(self) -> str:
        return self._proc.username()

    def terminal(self) -> Optional[str]:
        return self._proc.terminal()

    @overload
    def nice(self, value: int) -> None:
        ...

    @overload
    def nice(self, value: None = None) -> int:
        ...

    def nice(self, value: Optional[int] = None) -> Optional[int]:
        if value is not None:
            self._proc.setpriority(value)
            return None
        else:
            return self._proc.getpriority()

    if pypsutil.LINUX:
        assert hasattr(pypsutil.Process, "rlimit")

        @overload
        def rlimit(self, resource: int, limits: Tuple[int, int]) -> None:
            ...

        @overload
        def rlimit(self, resource: int, limits: None = None) -> Tuple[int, int]:
            ...

        def rlimit(
            self, resource: int, limits: Optional[Tuple[int, int]] = None
        ) -> Optional[Tuple[int, int]]:
            res = self._proc.rlimit(resource, limits)

            return res if limits is None else None

    if hasattr(pypsutil.Process, "num_threads"):

        def num_threads(self) -> int:
            return self._proc.num_threads()

    if hasattr(pypsutil.Process, "threads"):

        def threads(self) -> List[pypsutil.ThreadInfo]:
            return self._proc.threads()

    if hasattr(pypsutil.Process, "cpu_num"):

        def cpu_num(self) -> int:
            return self._proc.cpu_num()

    if hasattr(pypsutil.Process, "cpu_setaffinity") and hasattr(
        pypsutil.Process, "cpu_getaffinity"
    ):

        @overload
        def cpu_affinity(self, cpus: Iterable[int]) -> None:
            ...

        @overload
        def cpu_affinity(self, cpus: None = None) -> Set[int]:
            ...

        def cpu_affinity(self, cpus: Optional[Iterable[int]] = None) -> Optional[Set[int]]:
            if cpus is not None:
                self._proc.cpu_setaffinity(cpus)
                return None
            else:
                return self._proc.cpu_getaffinity()

    if hasattr(pypsutil.Process, "memory_maps_grouped"):
        assert hasattr(pypsutil.Process, "memory_maps")
        assert hasattr(pypsutil, "ProcessMemoryMap")
        assert hasattr(pypsutil, "ProcessMemoryMapGrouped")

        @overload
        def memory_maps(
            self,
            *,
            grouped: Literal[False] = False,
        ) -> List[pypsutil.ProcessMemoryMap]:
            ...

        @overload
        def memory_maps(
            self,
            *,
            grouped: Literal[True],
        ) -> List[pypsutil.ProcessMemoryMapGrouped]:
            ...

        def memory_maps(
            self, *, grouped: bool = True
        ) -> Union[List[pypsutil.ProcessMemoryMap], List[pypsutil.ProcessMemoryMapGrouped]]:
            return self._proc.memory_maps_grouped() if grouped else self._proc.memory_maps()

    def num_fds(self) -> int:
        return self._proc.num_fds()

    def open_files(self) -> List[pypsutil.ProcessOpenFile]:
        return self._proc.open_files()

    def cpu_times(self) -> pypsutil.ProcessCPUTimes:
        return self._proc.cpu_times()

    def memory_info(self) -> pypsutil.ProcessMemoryInfo:
        return self._proc.memory_info()

    def memory_percent(self, memtype: str = "rss") -> float:
        return self._proc.memory_percent(memtype)

    def is_running(self) -> bool:
        return self._proc.is_running()

    def send_signal(self, sig: int) -> None:
        self._proc.send_signal(sig)

    def suspend(self) -> None:
        self._proc.suspend()

    def resume(self) -> None:
        self._proc.resume()

    def terminate(self) -> None:
        self._proc.terminate()

    def kill(self) -> None:
        self._proc.kill()

    def wait(self, timeout: Union[int, float, None] = None) -> Optional[int]:
        return self._proc.wait(timeout=timeout)

    def oneshot(self) -> ContextManager[None]:
        return self._proc.oneshot()

    def __repr__(self) -> str:
        return f"pypsutil.compat.psutil.{self.__class__.__name__}(pid={self.pid})"

    def __eq__(self, other: Any) -> Union[bool, type(NotImplemented)]:  # type: ignore[valid-type]
        if isinstance(other, Process):
            return self._proc == other._proc

        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._proc)


class Popen(Process):
    _proc: pypsutil.Popen

    def __init__(  # pylint: disable=super-init-not-called
        self,
        args: Union[List[Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]], str, bytes],
        **kwargs: Any,
    ) -> None:
        self._proc = pypsutil.Popen(args, **kwargs)

        self.args = self._proc.args
        self.stdin = self._proc.stdin
        self.stdout = self._proc.stdout
        self.stderr = self._proc.stderr

    def poll(self) -> Optional[int]:
        return self._proc.poll()

    def wait(self, timeout: Union[int, float, None] = None) -> int:
        return self._proc.wait(timeout=timeout)

    def communicate(
        self,
        input: Union[str, bytes, None] = None,  # pylint: disable=redefined-builtin
        timeout: Union[int, float, None] = None,
    ) -> Tuple[Union[str, bytes, None], Union[str, bytes, None]]:
        return self._proc.communicate(input, timeout)

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.returncode

    def __enter__(self) -> "Popen":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._proc.__exit__(exc_type, exc_value, traceback)


Error = pypsutil.Error
NoSuchProcess = pypsutil.NoSuchProcess
ZombieProcess = pypsutil.ZombieProcess
AccessDenied = pypsutil.AccessDenied
TimeoutExpired = pypsutil.TimeoutExpired

pids = pypsutil.pids
pid_exists = pypsutil.pid_exists


def process_iter() -> Iterator[Process]:
    for proc in pypsutil.process_iter():
        yield Process._wrap(proc)  # pylint: disable=protected-access


def wait_procs(
    procs: Iterable[Process],
    timeout: Union[int, float, None] = None,
    callback: Optional[Callable[[Process], None]] = None,
) -> Tuple[List[Process], List[Process]]:
    proc_map: Dict[pypsutil.Process, Process] = {
        proc._proc: proc  # pylint: disable=protected-access  # type: ignore
        for proc in procs  # pytype: disable=annotation-type-mismatch
    }

    def inner_callback(inner_proc: pypsutil.Process) -> None:
        proc = proc_map[inner_proc]

        proc.returncode = inner_proc.returncode  # type: ignore

        if callback is not None:
            callback(proc)

    gone, alive = pypsutil.wait_procs(
        proc_map.keys(),
        timeout=timeout,
        callback=inner_callback,
    )

    return [proc_map[proc] for proc in gone], [proc_map[proc] for proc in alive]


disk_usage = pypsutil.disk_usage

virtual_memory = pypsutil.virtual_memory
swap_memory = pypsutil.swap_memory

boot_time = pypsutil.boot_time

if hasattr(pypsutil, "cpu_stats"):
    cpu_stats = pypsutil.cpu_stats

if hasattr(pypsutil, "sensors_battery"):
    sensors_battery = pypsutil.sensors_battery


def cpu_count(logical: bool = True) -> Optional[int]:
    return os.cpu_count() if logical else pypsutil.physical_cpu_count()


if (
    hasattr(pypsutil, "cpu_times")
    and hasattr(pypsutil, "percpu_times")
    and hasattr(pypsutil, "CPUTimes")
):

    @overload
    def cpu_times(percpu: Literal[False] = False) -> pypsutil.CPUTimes:
        ...

    @overload
    def cpu_times(percpu: Literal[True]) -> List[pypsutil.CPUTimes]:
        ...

    def cpu_times(
        percpu: bool = False,
    ) -> Union[pypsutil.CPUTimes, List[pypsutil.CPUTimes]]:
        return pypsutil.percpu_times() if percpu else pypsutil.cpu_times()


if (
    hasattr(pypsutil, "cpu_freq")
    and hasattr(pypsutil, "percpu_freq")
    and hasattr(pypsutil, "CPUFrequencies")
):

    @overload
    def cpu_freq(percpu: Literal[False] = False) -> Optional[pypsutil.CPUFrequencies]:
        ...

    @overload
    def cpu_freq(percpu: Literal[True]) -> List[pypsutil.CPUFrequencies]:
        ...

    def cpu_freq(
        percpu: bool = False,
    ) -> Union[pypsutil.CPUFrequencies, List[pypsutil.CPUFrequencies], None]:
        return pypsutil.percpu_freq() if percpu else pypsutil.cpu_freq()


if hasattr(pypsutil, "net_io_counters"):
    assert hasattr(pypsutil, "pernic_net_io_counters")

    @overload
    def net_io_counters(
        *, pernic: Literal[False] = False, nowrap: bool = True
    ) -> Optional[pypsutil.NetIOCounts]:
        ...

    @overload
    def net_io_counters(
        *, pernic: Literal[True], nowrap: bool = True
    ) -> Dict[str, pypsutil.NetIOCounts]:
        ...

    def net_io_counters(
        *, pernic: bool = False, nowrap: bool = True
    ) -> Union[pypsutil.NetIOCounts, Dict[str, pypsutil.NetIOCounts], None]:
        return (
            pypsutil.pernic_net_io_counters(nowrap=nowrap)
            if pernic
            else pypsutil.net_io_counters(nowrap=nowrap)
        )
