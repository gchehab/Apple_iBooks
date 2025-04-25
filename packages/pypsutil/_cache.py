from typing import TYPE_CHECKING, Callable, Generic, TypeVar, cast

if TYPE_CHECKING:  # pragma: no cover
    from ._process import Process

T = TypeVar("T")


class CachedByProcess(Generic[T]):
    def __init__(self, func: Callable[["Process"], T]):
        self._func = func
        self._name = self.__class__.__name__ + "-" + func.__module__ + "." + func.__name__

    def get_cached_value(self, proc: "Process") -> T:
        return cast(  # pytype: disable=invalid-typevar
            T, proc._get_cache(self._name)  # pylint: disable=protected-access
        )

    def __call__(self, proc: "Process") -> T:
        try:
            return self.get_cached_value(proc)
        except KeyError:
            pass

        value = self._func(proc)
        proc._set_cache(self._name, value)  # pylint: disable=protected-access
        return value
