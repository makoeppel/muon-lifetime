from midas_file import *
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
import numpy as np
from scipy.optimize import curve_fit


def find_negative_pulses_times_ns(y_mV, t_ns, level_mV=-80.0, min_sep_ns=50.0):
    """
    Return array of pulse times (ns) for negative pulses using downward level crossing.

    y_mV: waveform in mV (negative pulses)
    t_ns: time axis in ns
    level_mV: crossing threshold (e.g. -80 mV)
    min_sep_ns: enforce separation to avoid double-counting ringing
    """
    y = np.asarray(y_mV)
    t = np.asarray(t_ns)

    pulses = []
    last_t = -np.inf

    for i in range(len(y) - 1):
        # downward crossing through level_mV
        if y[i] > level_mV and y[i + 1] <= level_mV:
            ti = t[i]
            if ti - last_t >= min_sep_ns:
                pulses.append(ti)
                last_t = ti

    return np.array(pulses, dtype=float)


def pick_stop_and_decay_ns(block_pulse_times_ns, dead_time_ns=200.0, dt_max_ns=None):
    """
    Choose t_stop = first pulse, t_decay = first later pulse after dead_time_ns.
    Returns dt_ns or None if not found.
    """
    if len(block_pulse_times_ns) < 2:
        return None

    t_stop = block_pulse_times_ns[0]

    for t2 in block_pulse_times_ns[1:]:
        dt = t2 - t_stop
        if dt <= dead_time_ns:
            continue
        if dt_max_ns is not None and dt > dt_max_ns:
            continue
        return dt

    return None


muon_times_ns = []

LEVEL_MV = -80.0        # hit threshold
MIN_SEP_NS = 50.0       # avoid ringing double-count
DEAD_TIME_NS = 200.0    # ignore pulses right after the stop pulse
DT_MAX_NS = 50_000.0    # 50 us; set None if you prefer "no max"

file = MidasFile("run00053.mid.lz4")

while file.next_event() != -1:
    t_ns = None
    up = down = block = None

    while file.next_bank() != -1:
        if file.bank.name == "TC00":
            t_ns = bank_as_numpy(file.bank.data)
        elif file.bank.name == "CC00":
            up = bank_as_numpy(file.bank.data)
        elif file.bank.name == "CC01":
            down = bank_as_numpy(file.bank.data)
        elif file.bank.name == "CC02":
            block = bank_as_numpy(file.bank.data)

    if t_ns is None or up is None or down is None or block is None:
        continue

    # cut start
    t_ns = t_ns[100:]
    up = up[100:]
    down = down[100:]
    block = block[100:]

    # simple hit logic
    hit_up = np.min(up) <= LEVEL_MV
    hit_down = np.min(down) <= LEVEL_MV
    hit_block = np.min(block) <= LEVEL_MV

    print(hit_up, hit_down, hit_block)

    if hit_up and hit_block and hit_down:
        plt.plot(t_ns, up)
        plt.plot(t_ns, down)
        plt.plot(t_ns, block)
        plt.show()

    # stopping muon: U and M, but NOT D
    if hit_up and hit_block and (not hit_down):
        block_times = find_negative_pulses_times_ns(
            block, t_ns, level_mV=LEVEL_MV, min_sep_ns=MIN_SEP_NS
        )

        dt_ns = pick_stop_and_decay_ns(
            block_times, dead_time_ns=DEAD_TIME_NS, dt_max_ns=DT_MAX_NS
        )

        if dt_ns is not None:
            muon_times_ns.append(dt_ns)

print(muon_times_ns)
muon_times_ns = np.array(muon_times_ns, dtype=float)
muon_times_us = muon_times_ns / 1000.0

def expo(t_us, N0, tau_us):
    return N0 * np.exp(-t_us / tau_us)

bins = np.linspace(0, 20.0, 60)  # 0..20 us
hist, edges = np.histogram(muon_times_us, bins=bins)
centers = 0.5 * (edges[:-1] + edges[1:])

# fit ignoring empty bins helps stability
mask = hist > 0
popt, _ = curve_fit(expo, centers[mask], hist[mask], p0=[hist.max(), 2.2])

plt.step(centers, hist, where="mid", label="Data")
plt.plot(centers, expo(centers, *popt), label=f"Fit: τ = {popt[1]:.2f} µs")
plt.xlabel("Δt [µs]")
plt.ylabel("Counts")
plt.grid(True)
plt.legend()
plt.show()
