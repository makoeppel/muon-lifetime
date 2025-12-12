import asyncio
import json
import time
import midas.client
from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict

import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse

from midas_file import MidasFile, bank_as_numpy

from pathlib import Path

# -------------------------
# Pulse finding (time in ns, signal in mV)
# -------------------------

def find_negative_pulses_times_ns(y_mV: np.ndarray, t_ns: np.ndarray,
                                 level_mV: float, min_sep_ns: float) -> np.ndarray:
    pulses = []
    last_t = -np.inf
    for i in range(len(y_mV) - 1):
        if y_mV[i] > level_mV and y_mV[i + 1] <= level_mV:
            ti = float(t_ns[i])
            if ti - last_t >= min_sep_ns:
                pulses.append(ti)
                last_t = ti
    return np.array(pulses, dtype=float)


def pick_stop_and_decay_ns(block_pulse_times_ns: np.ndarray,
                           dead_time_ns: float,
                           dt_max_ns: Optional[float]) -> Optional[float]:
    if len(block_pulse_times_ns) < 2:
        return None
    t_stop = block_pulse_times_ns[0]
    for t2 in block_pulse_times_ns[1:]:
        dt = t2 - t_stop
        if dt <= dead_time_ns:
            continue
        if dt_max_ns is not None and dt > dt_max_ns:
            continue
        return float(dt)
    return None


# -------------------------
# Shared state
# -------------------------

@dataclass
class WaveformState:
    t_ns: Optional[list] = None
    up: Optional[list] = None
    down: Optional[list] = None
    block: Optional[list] = None
    last_event_serial: int = 0
    last_update_unix: float = 0.0

state = WaveformState()
state_lock = asyncio.Lock()

# Per-channel thresholds in mV
thresholds = {"up": -80.0, "down": -80.0, "block": -80.0}
min_sep_ns = {"up": 50.0, "down": 50.0, "block": 50.0}

# Muon pairing params (ns)
dead_time_ns = 200.0
dt_max_ns = 50_000.0  # 50 us; set to None if you prefer no max

# Rolling buffers for histograms
ROLL_N = 5000
amp_up = deque(maxlen=ROLL_N)
amp_down = deque(maxlen=ROLL_N)
amp_block = deque(maxlen=ROLL_N)
muon_dt_ns = deque(maxlen=ROLL_N)


# -------------------------
# Background reader task (file replay)
# -------------------------

async def midas_reader_task(path: str):
    try:
        print("Opening MIDAS file:", path)
        mf = MidasFile(path)
        print("Opened ok")
        while True:
            if mf.next_event() == -1:
                # loop file for demo
                mf.close()
                mf = MidasFile(path)
                continue

            t_ns = None
            up = down = block = None

            while mf.next_bank() != -1:
                if mf.bank.name == "TC00":
                    t_ns = bank_as_numpy(mf.bank.data).astype(float)
                elif mf.bank.name == "CC00":
                    up = bank_as_numpy(mf.bank.data).astype(float)
                elif mf.bank.name == "CC01":
                    down = bank_as_numpy(mf.bank.data).astype(float)
                elif mf.bank.name == "CC02":
                    block = bank_as_numpy(mf.bank.data).astype(float)

            if t_ns is None or up is None or down is None or block is None:
                await asyncio.sleep(0)
                continue

            # cut start
            t_ns = t_ns[100:]
            up = up[100:]
            down = down[100:]
            block = block[100:]

            hit_up    = np.min(up)    <= thresholds["up"]
            hit_down  = np.min(down)  <= thresholds["down"]
            hit_block = np.min(block) <= thresholds["block"]

            if not (hit_up or hit_down or hit_block):
                continue  # skip updating the live waveform

            # Update live waveform snapshot
            async with state_lock:
                state.t_ns = t_ns.tolist()
                state.up = up.tolist()
                state.down = down.tolist()
                state.block = block.tolist()
                state.last_event_serial = int(mf.event.serial_number)
                state.last_update_unix = time.time()

            # Fill rolling amplitude histos (min value is pulse amplitude for negative pulses)
            amp_up.append(float(np.min(up)))
            amp_down.append(float(np.min(down)))
            amp_block.append(float(np.min(block)))

            # Build rolling muon dt histogram (stopping muon selection)
            hit_up = np.min(up) <= thresholds["up"]
            hit_down = np.min(down) <= thresholds["down"]
            hit_block = np.min(block) <= thresholds["block"]

            if hit_up and hit_block and (not hit_down):
                block_times = find_negative_pulses_times_ns(
                    block, t_ns, thresholds["block"], min_sep_ns["block"]
                )
                dt = pick_stop_and_decay_ns(block_times, dead_time_ns, dt_max_ns)
                if dt is not None:
                    muon_dt_ns.append(dt)

            await asyncio.sleep(0)
    finally:
        try:
            mf.close()
        except Exception:
            pass


async def midas_online_reader_task():
    try:
        while True:
            event = client.receive_event(buffer_handle, async_flag=False)
            if event is not None:
                # Print some information to screen about this event.
                bank_names = ", ".join(b.name for b in event.banks.values())

            # Talk to midas so it knows we're alive, or can kill us if the user
            # pressed the "stop program" button.
            client.communicate(10)

            t_ns = None
            up = down = block = None

            for bank_name, bank in event.banks.items():
                if bank_name == "TC00":
                    t_ns = np.array(bank.data)
                elif bank_name == "CC00":
                    up = np.array(bank.data)
                elif bank_name == "CC01":
                    down = np.array(bank.data)
                elif bank_name == "CC02":
                    block = np.array(bank.data)

            if t_ns is None or up is None or down is None or block is None:
                await asyncio.sleep(0)
                continue

            # cut start
            t_ns = t_ns[100:]
            up = up[100:]
            down = down[100:]
            block = block[100:]

            hit_up    = np.min(up)    <= thresholds["up"]
            hit_down  = np.min(down)  <= thresholds["down"]
            hit_block = np.min(block) <= thresholds["block"]

            if not (hit_up or hit_down or hit_block):
                continue  # skip updating the live waveform

            # Update live waveform snapshot
            async with state_lock:
                state.t_ns = t_ns.tolist()
                state.up = up.tolist()
                state.down = down.tolist()
                state.block = block.tolist()
                state.last_event_serial = int(event.header.serial_number)
                state.last_update_unix = time.time()

            # Fill rolling amplitude histos (min value is pulse amplitude for negative pulses)
            amp_up.append(float(np.min(up)))
            amp_down.append(float(np.min(down)))
            amp_block.append(float(np.min(block)))

            # Build rolling muon dt histogram (stopping muon selection)
            hit_up = np.min(up) <= thresholds["up"]
            hit_down = np.min(down) <= thresholds["down"]
            hit_block = np.min(block) <= thresholds["block"]

            if hit_up and hit_block and (not hit_down):
                block_times = find_negative_pulses_times_ns(
                    block, t_ns, thresholds["block"], min_sep_ns["block"]
                )
                dt = pick_stop_and_decay_ns(block_times, dead_time_ns, dt_max_ns)
                if dt is not None:
                    muon_dt_ns.append(dt)

            await asyncio.sleep(0)
    finally:
        try:
            mf.close()
        except Exception:
            pass


# -------------------------
# FastAPI + UI
# -------------------------

app = FastAPI()

BASE_DIR = Path(__file__).parent

# MIDAS_PATH = "run00053.mid.lz4"
client = midas.client.MidasClient("analyzer")
buffer_handle = client.open_event_buffer("SYSTEM")
request_id = client.register_event_request(buffer_handle, event_id = 666)

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")

@app.on_event("startup")
async def startup():
    #asyncio.create_task(midas_reader_task(MIDAS_PATH))
    asyncio.create_task(midas_online_reader_task())
    print("Started midas_reader_task()")

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    while True:
        # 1) read incoming messages if any
        try:
            msg = await asyncio.wait_for(ws.receive_text(), timeout=0.01)
            data = json.loads(msg)
            if data.get("type") == "set_params":
                ch = data["channel"]
                thresholds[ch] = float(data["threshold"])
                min_sep_ns[ch] = float(data["min_sep_ns"])
        except asyncio.TimeoutError:
            pass

        # 2) send current payload (includes updated thresholds)
        async with state_lock:
            if state.t_ns is None:
                payload = {
                    "t_ns": [], "up": [], "down": [], "block": [],
                    "edges": {"up": [], "down": [], "block": []},
                    "thresholds": thresholds,
                    "min_sep_ns": min_sep_ns,
                    "last_event_serial": 0,
                    "last_update_unix": 0.0,
                    "roll_n": len(amp_up),
                    "amp_hist": {"up": list(amp_up), "down": list(amp_down), "block": list(amp_block)},
                    "dt_hist_us": (np.array(list(muon_dt_ns), dtype=float) / 1000.0).tolist(),
                }
            else:
                t_ns = np.asarray(state.t_ns, dtype=float)
                up = np.asarray(state.up, dtype=float)
                down = np.asarray(state.down, dtype=float)
                block = np.asarray(state.block, dtype=float)

                edges = {
                    "up": find_negative_pulses_times_ns(up, t_ns, thresholds["up"], min_sep_ns["up"]).tolist(),
                    "down": find_negative_pulses_times_ns(down, t_ns, thresholds["down"], min_sep_ns["down"]).tolist(),
                    "block": find_negative_pulses_times_ns(block, t_ns, thresholds["block"], min_sep_ns["block"]).tolist(),
                }

                payload = {
                    "t_ns": state.t_ns,
                    "up": state.up,
                    "down": state.down,
                    "block": state.block,
                    "edges": edges,
                    "thresholds": thresholds,
                    "min_sep_ns": min_sep_ns,
                    "last_event_serial": state.last_event_serial,
                    "last_update_unix": state.last_update_unix,
                    "roll_n": len(amp_up),
                    "amp_hist": {
                        "up": list(amp_up),
                        "down": list(amp_down),
                        "block": list(amp_block),
                    },
                    "dt_hist_us": (np.array(list(muon_dt_ns), dtype=float) / 1000.0).tolist(),
                }

        await ws.send_text(json.dumps(payload))
        await asyncio.sleep(0.05)


def run_file(path: str, host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(midas_reader_task(path))
    uvicorn.run(app, host=host, port=port, log_level="info")

def run_online(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    loop = asyncio.get_event_loop()
    loop.create_task(midas_online_reader_task(path))
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    # run_file(MIDAS_PATH, port=8000)
    run_online(port=8000)
