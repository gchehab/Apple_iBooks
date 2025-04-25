# Type checkers don't like the wrapper names not existing.
# mypy: ignore-errors
# pytype: disable=module-attr
import dataclasses
from typing import Dict, List, Optional

from . import _util
from ._detect import _psimpl

SwapInfo = _util.SwapInfo
NICAddr = _util.NICAddr

PowerSupplySensorInfo = _util.PowerSupplySensorInfo
ACPowerInfo = _util.ACPowerInfo
BatteryInfo = _util.BatteryInfo
BatteryStatus = _util.BatteryStatus
NetIOCounts = _util.NetIOCounts


@dataclasses.dataclass
class CPUFrequencies:
    current: float
    min: float
    max: float


@dataclasses.dataclass
class CPUStats:
    ctx_switches: int
    interrupts: int
    soft_interrupts: int
    syscalls: int


if hasattr(_psimpl, "physical_cpu_count"):
    physical_cpu_count = _psimpl.physical_cpu_count
else:

    def physical_cpu_count() -> Optional[int]:
        return None


if hasattr(_psimpl, "cpu_freq"):

    def cpu_freq() -> Optional[CPUFrequencies]:
        result = _psimpl.cpu_freq()

        if result is not None:
            return CPUFrequencies(current=result[0], min=result[1], max=result[2])
        else:
            return None

elif hasattr(_psimpl, "percpu_freq"):

    def cpu_freq() -> Optional[CPUFrequencies]:
        freqs = _psimpl.percpu_freq()
        if not freqs:
            return None

        cur_total = 0.0
        min_total = 0.0
        max_total = 0.0

        for cur_freq, min_freq, max_freq in freqs:
            cur_total += cur_freq
            min_total += min_freq
            max_total += max_freq

        return CPUFrequencies(
            current=cur_total / len(freqs), min=min_total / len(freqs), max=max_total / len(freqs)
        )


if hasattr(_psimpl, "percpu_freq"):

    def percpu_freq() -> List[CPUFrequencies]:
        return [
            CPUFrequencies(f_cur, f_min, f_max) for f_cur, f_min, f_max in _psimpl.percpu_freq()
        ]


if hasattr(_psimpl, "cpu_stats"):

    def cpu_stats() -> CPUStats:
        ctx, intr, soft_intr, syscalls = _psimpl.cpu_stats()

        return CPUStats(
            ctx_switches=ctx, interrupts=intr, soft_interrupts=soft_intr, syscalls=syscalls
        )


if hasattr(_psimpl, "cpu_times"):
    CPUTimes = _psimpl.CPUTimes

    cpu_times = _psimpl.cpu_times


if hasattr(_psimpl, "percpu_times"):
    percpu_times = _psimpl.percpu_times


if hasattr(_psimpl, "net_connections"):

    def net_connections(kind: str = "inet") -> List[_util.Connection]:
        return list(_psimpl.net_connections(kind))


VirtualMemoryInfo = _psimpl.VirtualMemoryInfo
virtual_memory = _psimpl.virtual_memory
swap_memory = _psimpl.swap_memory


if hasattr(_psimpl, "sensors_power"):
    sensors_power = _psimpl.sensors_power
    sensors_is_on_ac_power = _psimpl.sensors_is_on_ac_power

    def sensors_battery() -> Optional[BatteryInfo]:
        psinfo = sensors_power()
        if not psinfo.batteries:
            if hasattr(_psimpl, "sensors_battery_total_alt"):
                return _psimpl.sensors_battery_total_alt(psinfo.is_on_ac_power)
            else:
                return None

        battery = psinfo.batteries[0]

        if battery.power_plugged is None:
            battery._power_plugged = psinfo.is_on_ac_power  # pylint: disable=protected-access

        return battery

    def sensors_battery_total() -> Optional[BatteryInfo]:
        psinfo = sensors_power()
        if not psinfo.batteries:
            if hasattr(_psimpl, "sensors_battery_total_alt"):
                return _psimpl.sensors_battery_total_alt(psinfo.is_on_ac_power)
            else:
                return None

        elif len(psinfo.batteries) == 1:
            # 1 battery
            battery = psinfo.batteries[0]
            if battery.power_plugged is None:
                battery._power_plugged = psinfo.is_on_ac_power  # pylint: disable=protected-access
            return battery

        total_energy_full = 0
        total_energy_now = 0

        total_discharge_rate = 0
        total_charge_rate = 0

        for battery in psinfo.batteries:
            total_energy_full += battery.energy_full or 0
            total_energy_now += battery.energy_now or 0

            if battery.status == BatteryStatus.CHARGING:
                total_charge_rate += battery.power_now or 0
            elif battery.status == BatteryStatus.DISCHARGING:
                total_discharge_rate += battery.power_now or 0

        if total_energy_full == 0:
            return None
        percent = total_energy_now * 100 / total_energy_full

        power_now = None

        if any(battery.status == BatteryStatus.CHARGING for battery in psinfo.batteries) and all(
            battery.status in (BatteryStatus.CHARGING, BatteryStatus.FULL)
            for battery in psinfo.batteries
        ):
            # At least one battery charging, all either charging or full
            status = BatteryStatus.CHARGING
            power_now = total_charge_rate
        elif any(
            battery.status == BatteryStatus.DISCHARGING for battery in psinfo.batteries
        ) and all(
            battery.status in (BatteryStatus.DISCHARGING, BatteryStatus.FULL)
            for battery in psinfo.batteries
        ):
            # At least one battery discharging, all either discharging or full
            status = BatteryStatus.DISCHARGING
            power_now = total_discharge_rate
        elif all(battery.status == BatteryStatus.FULL for battery in psinfo.batteries):
            # All full
            status = BatteryStatus.FULL
        else:
            status = BatteryStatus.UNKNOWN

        return BatteryInfo(
            name="Combined",
            percent=percent,
            energy_full=total_energy_full,
            energy_now=total_energy_now,
            power_now=power_now,
            _power_plugged=psinfo.is_on_ac_power,
            status=status,
        )


if hasattr(_psimpl, "sensors_temperatures"):
    TempSensorInfo = _psimpl.TempSensorInfo

    sensors_temperatures = _psimpl.sensors_temperatures


if hasattr(_psimpl, "pernic_net_io_counters"):
    _pernic_net_io_cache: Dict[str, NetIOCounts] = {}

    def pernic_net_io_counters(*, nowrap: bool = True) -> Dict[str, NetIOCounts]:
        pernic_counts = _psimpl.pernic_net_io_counters()
        if nowrap:
            for name, counts in pernic_counts.items():
                _pernic_net_io_cache[name] = counts._nowrap(  # pylint: disable=protected-access
                    _pernic_net_io_cache.get(name)
                )
        return pernic_counts

    pernic_net_io_counters.cache_clear = _pernic_net_io_cache.clear

    def net_io_counters(*, nowrap: bool = True) -> Optional[NetIOCounts]:
        totals = NetIOCounts(
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            errin=0,
            errout=0,
            dropin=0,
            dropout=0,
        )

        allnic_counts = pernic_net_io_counters(nowrap=nowrap).values()
        if not allnic_counts:
            return None

        for nic_counts in allnic_counts:
            for field in dataclasses.fields(NetIOCounts):
                setattr(
                    totals,
                    field.name,
                    getattr(totals, field.name) + getattr(nic_counts, field.name),
                )

        return totals

    net_io_counters.cache_clear = pernic_net_io_counters.cache_clear


boot_time = _psimpl.boot_time


time_since_boot = _psimpl.time_since_boot


if hasattr(_psimpl, "uptime"):
    uptime = _psimpl.uptime


DiskUsage = _psimpl.DiskUsage
disk_usage = _psimpl.disk_usage

if hasattr(_psimpl, "net_if_addrs"):
    net_if_addrs = _psimpl.net_if_addrs

if hasattr(_psimpl, "net_if_stats"):
    net_if_stats = _psimpl.net_if_stats
