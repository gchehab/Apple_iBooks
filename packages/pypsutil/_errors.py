from typing import Optional, Union


class Error(Exception):
    pass


class NoSuchProcess(Error):
    def __init__(self, pid: int) -> None:
        super().__init__()
        self.pid = pid

    def __repr__(self) -> str:
        return f"pypsutil.NoSuchProcess(pid={self.pid!r})"

    def __str__(self) -> str:
        return f"pypsutil.NoSuchProcess: process does not exist (pid={self.pid})"


class ZombieProcess(NoSuchProcess):
    def __repr__(self) -> str:
        return f"pypsutil.ZombieProcess(pid={self.pid!r})"

    def __str__(self) -> str:
        return f"pypsutil.ZombieProcess: process exists but is a zombie (pid={self.pid})"


class AccessDenied(Error):
    def __init__(self, pid: int) -> None:
        super().__init__()
        self.pid = pid

    def __repr__(self) -> str:
        return f"pypsutil.AccessDenied(pid={self.pid!r})"

    def __str__(self) -> str:
        return "pypsutil.AccessDenied" + (f" (pid={self.pid})" if self.pid is not None else "")


class TimeoutExpired(Error):
    def __init__(self, seconds: Union[int, float], pid: Optional[int] = None) -> None:
        super().__init__()
        self.seconds = seconds
        self.pid = pid

    def __repr__(self) -> str:
        return f"pypsutil.TimeoutExpired({self.seconds}, pid={self.pid!r})"

    def __str__(self) -> str:
        return f"pypsutil.TimeoutExpired: timeout after {self.seconds} seconds" + (
            f" (pid={self.pid})" if self.pid is not None else ""
        )
