import dataclasses
import os
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover
    from ._process import Process


def proc_pgid(proc: "Process") -> int:
    pid = proc.pid

    if pid == 0:
        return 0

    return os.getpgid(pid)


def proc_sid(proc: "Process") -> int:
    pid = proc.pid

    if pid == 0:
        return 0

    return os.getsid(pid)


def proc_getpriority(proc: "Process") -> int:
    pid = proc.pid

    if pid == 0:
        raise PermissionError

    return os.getpriority(os.PRIO_PROCESS, pid)


@dataclasses.dataclass
class DiskUsage:
    total: int
    used: int
    free: int

    def percent(self) -> float:
        return self.used * 100.0 / (self.used + self.free)


def disk_usage(path: Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]) -> DiskUsage:
    vfs_stat = os.statvfs(os.fspath(path))

    total = vfs_stat.f_blocks * vfs_stat.f_frsize
    free = vfs_stat.f_bavail * vfs_stat.f_frsize
    used = total - vfs_stat.f_bfree * vfs_stat.f_frsize

    return DiskUsage(total=total, free=free, used=used)
