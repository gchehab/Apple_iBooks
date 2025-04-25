import socket
from typing import cast

from . import _process, _system
from ._detect import BSD, FREEBSD, LINUX, MACOS, NETBSD, OPENBSD
from ._errors import AccessDenied, Error, NoSuchProcess, TimeoutExpired, ZombieProcess
from ._process import (
    Connection,
    ConnectionStatus,
    Gids,
    Popen,
    Process,
    ProcessCPUTimes,
    ProcessFd,
    ProcessFdType,
    ProcessMemoryInfo,
    ProcessOpenFile,
    ProcessSignalMasks,
    ProcessStatus,
    ThreadInfo,
    Uids,
    pid_exists,
    pids,
    process_iter,
    process_iter_available,
    wait_procs,
)
from ._system import (
    ACPowerInfo,
    BatteryInfo,
    BatteryStatus,
    CPUFrequencies,
    CPUStats,
    DiskUsage,
    NetIOCounts,
    NICAddr,
    PowerSupplySensorInfo,
    SwapInfo,
    VirtualMemoryInfo,
    boot_time,
    disk_usage,
    physical_cpu_count,
    swap_memory,
    time_since_boot,
    virtual_memory,
)

__version__ = "0.2.0"

__all__ = [
    "PROCFS_PATH",
    "LINUX",
    "MACOS",
    "FREEBSD",
    "NETBSD",
    "OPENBSD",
    "BSD",
    "boot_time",
    "time_since_boot",
    "physical_cpu_count",
    "disk_usage",
    "Process",
    "ProcessCPUTimes",
    "ProcessMemoryInfo",
    "ProcessOpenFile",
    "ProcessFd",
    "ProcessFdType",
    "Connection",
    "ConnectionStatus",
    "ProcessSignalMasks",
    "ProcessStatus",
    "Popen",
    "ThreadInfo",
    "pid_exists",
    "pids",
    "process_iter",
    "process_iter_available",
    "wait_procs",
    "CPUFrequencies",
    "CPUStats",
    "DiskUsage",
    "ProcessSignalMasks",
    "SwapInfo",
    "VirtualMemoryInfo",
    "virtual_memory",
    "swap_memory",
    "PowerSupplySensorInfo",
    "ACPowerInfo",
    "BatteryInfo",
    "BatteryStatus",
    "NetIOCounts",
    "NICAddr",
    "Uids",
    "Gids",
    "Error",
    "NoSuchProcess",
    "ZombieProcess",
    "AccessDenied",
    "TimeoutExpired",
]

if hasattr(_system, "uptime"):
    uptime = _system.uptime
    __all__.append("uptime")
if hasattr(_system, "cpu_freq"):
    cpu_freq = _system.cpu_freq
    __all__.append("cpu_freq")
if hasattr(_system, "percpu_freq"):
    percpu_freq = _system.percpu_freq
    __all__.append("percpu_freq")
if hasattr(_system, "cpu_stats"):
    cpu_stats = _system.cpu_stats
    __all__.append("cpu_stats")
if hasattr(_system, "cpu_times"):
    cpu_times = _system.cpu_times
    __all__.append("cpu_times")
if hasattr(_system, "percpu_times"):
    percpu_times = _system.percpu_times
    __all__.append("percpu_times")
if hasattr(_system, "sensors_power"):
    sensors_power = _system.sensors_power
    __all__.append("sensors_power")
if hasattr(_system, "sensors_battery"):
    sensors_battery = _system.sensors_battery
    __all__.append("sensors_battery")
if hasattr(_system, "sensors_battery_total"):
    sensors_battery_total = _system.sensors_battery_total
    __all__.append("sensors_battery_total")
if hasattr(_system, "sensors_is_on_ac_power"):
    sensors_is_on_ac_power = _system.sensors_is_on_ac_power
    __all__.append("sensors_is_on_ac_power")
if hasattr(_system, "sensors_temperatures"):
    sensors_temperatures = _system.sensors_temperatures
    __all__.append("sensors_temperatures")
if hasattr(_system, "net_connections"):
    net_connections = _system.net_connections
    __all__.append("net_connections")
if hasattr(_system, "net_if_addrs"):
    net_if_addrs = _system.net_if_addrs
    __all__.append("net_if_addrs")
if hasattr(_system, "net_if_stats"):
    net_if_stats = _system.net_if_stats
    __all__.append("net_if_stats")
if hasattr(_system, "net_io_counters"):
    net_io_counters = _system.net_io_counters
    __all__.append("net_io_counters")
if hasattr(_system, "pernic_net_io_counters"):
    pernic_net_io_counters = _system.pernic_net_io_counters
    __all__.append("pernic_net_io_counters")
if hasattr(_system, "CPUTimes"):
    CPUTimes = _system.CPUTimes
    __all__.append("CPUTimes")
if hasattr(_system, "TempSensorInfo"):
    TempSensorInfo = _system.TempSensorInfo
    __all__.append("TempSensorInfo")

if hasattr(_process, "ProcessMemoryMap"):
    ProcessMemoryMap = _process.ProcessMemoryMap
    __all__.append("ProcessMemoryMap")
if hasattr(_process, "ProcessMemoryMapGrouped"):
    ProcessMemoryMapGrouped = _process.ProcessMemoryMapGrouped
    __all__.append("ProcessMemoryMapGrouped")


# Alias to help with net_if_addrs()
# pylint: disable=no-member
if hasattr(socket, "AF_LINK"):
    AF_LINK = socket.AF_LINK
else:
    AF_LINK = cast(socket.AddressFamily, socket.AF_PACKET)  # type: ignore
# pylint: enable=no-member

DEVFS_PATH = "/dev"

PROCFS_PATH = "/proc"

if LINUX:
    SYSFS_PATH = "/sys"
    __all__.append("SYSFS_PATH")
