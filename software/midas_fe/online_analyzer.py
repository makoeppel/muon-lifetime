from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

# This is the official MIDAS python module (comes with MIDAS installations).
# The "midas" PyPI package is NOT the DAQ package (it's unrelated).
import midas  # type: ignore
import midas.client  # type: ignore


# ----------------------------
# MIDAS event parsing (bytes -> header + banks)
# ----------------------------

@dataclass
class Bank:
    name: str
    type: int
    data: memoryview  # view into event payload (no copy)

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass
class Event:
    event_id: int
    trigger_mask: int
    serial_number: int
    time_stamp: int
    data_size: int
    bank_flags: int = 0
    all_bank_size: int = 0
    banks: List[Bank] = None  # filled for normal events

    EVENT_ID_BOR = 0x8000
    EVENT_ID_EOR = 0x8001
    EVENT_ID_MESSAGE = 0x8002

    BANK_FLAG_VERSION = 1
    BANK_FLAG_32BIT = 1 << 4
    BANK_FLAG_64BIT_ALIGNED = 1 << 5


def _u16_le(buf: memoryview, off: int) -> Tuple[int, int]:
    return struct.unpack_from("<H", buf, off)[0], off + 2

def _u32_le(buf: memoryview, off: int) -> Tuple[int, int]:
    return struct.unpack_from("<I", buf, off)[0], off + 4


def parse_midas_event(raw: bytes) -> Event:
    """
    Parse one MIDAS event from raw bytes received from a MIDAS buffer.
    Assumes little-endian encoding (typical on x86).
    """
    mv = memoryview(raw)
    off = 0

    event_id, off = _u16_le(mv, off)
    trigger_mask, off = _u16_le(mv, off)
    serial_number, off = _u32_le(mv, off)
    time_stamp, off = _u32_le(mv, off)
    data_size, off = _u32_le(mv, off)

    # event header is 16 bytes; next is event data
    data_end = off + data_size
    if data_end > len(mv):
        raise ValueError(f"Bad event: data_size={data_size} exceeds buffer length={len(mv)}")

    ev = Event(
        event_id=event_id,
        trigger_mask=trigger_mask,
        serial_number=serial_number,
        time_stamp=time_stamp,
        data_size=data_size,
        banks=[],
    )

    # BOR/EOR/message events often don't have standard bank headers
    if event_id in (Event.EVENT_ID_BOR, Event.EVENT_ID_EOR, Event.EVENT_ID_MESSAGE):
        return ev

    # Bank header (matches your file-reader C++ logic)
    all_bank_size, off = _u32_le(mv, off)
    bank_flags, off = _u32_le(mv, off)
    ev.all_bank_size = all_bank_size
    ev.bank_flags = bank_flags

    # The remaining bytes should be all_bank_size
    if (data_end - off) != all_bank_size:
        raise ValueError(f"Bad event: remaining={(data_end-off)} != all_bank_size={all_bank_size}")

    # Parse banks until we consume the event data
    while off < data_end:
        # bank name: 4 bytes
        name = bytes(mv[off:off+4]).decode("ascii", "replace")
        off += 4

        if bank_flags == Event.BANK_FLAG_VERSION:
            # 16-bit type/size
            btype, off = _u16_le(mv, off)
            bsize, off = _u16_le(mv, off)
        elif bank_flags == (Event.BANK_FLAG_VERSION | Event.BANK_FLAG_32BIT):
            btype, off = _u32_le(mv, off)
            bsize, off = _u32_le(mv, off)
        elif bank_flags == (Event.BANK_FLAG_VERSION | Event.BANK_FLAG_32BIT | Event.BANK_FLAG_64BIT_ALIGNED):
            btype, off = _u32_le(mv, off)
            bsize, off = _u32_le(mv, off)
            off += 4  # reserved
        else:
            raise NotImplementedError(f"Unsupported bank_flags=0x{bank_flags:08X}")

        if off + bsize > data_end:
            raise ValueError(f"Bad bank {name}: size={bsize} exceeds event boundary")

        data_view = mv[off:off+bsize]
        off += bsize

        ev.banks.append(Bank(name=name, type=btype, data=data_view))

        # 64-bit alignment padding
        if bank_flags & Event.BANK_FLAG_64BIT_ALIGNED:
            pad = off % 8
            if pad:
                off += (8 - pad)

    return ev


# ----------------------------
# Bank decoding helpers
# ----------------------------

def bank_as_floats(bank: Bank, float64: bool = False) -> List[float]:
    """
    Convert bank payload to floats (copying into Python floats).
    Use float64=True for double precision.
    """
    fmt = "<d" if float64 else "<f"
    step = 8 if float64 else 4
    if bank.size % step != 0:
        raise ValueError(f"Bank {bank.name} size {bank.size} not divisible by {step}")
    n = bank.size // step
    return list(struct.unpack_from("<" + ("d" if float64 else "f") * n, bank.data, 0))


# ----------------------------
# Analyzer module interface (like TARunObject)
# ----------------------------

class Module(Protocol):
    name: str
    order: int

    def begin_run(self, run_number: int) -> None: ...
    def end_run(self, run_number: int) -> None: ...
    def analyze_event(self, run_number: int, event: Event) -> None: ...


class EventDumpModule:
    name = "EventDump"
    order = -1

    def begin_run(self, run_number: int) -> None:
        print(f"[{self.name}] BeginRun {run_number}")

    def end_run(self, run_number: int) -> None:
        print(f"[{self.name}] EndRun {run_number}")

    def analyze_event(self, run_number: int, event: Event) -> None:
        if event.banks:
            banks = ", ".join(f"{b.name}(type={b.type},size={b.size})" for b in event.banks)
        else:
            banks = "(no banks)"
        print(f"[{self.name}] run={run_number} id=0x{event.event_id:04X} ser={event.serial_number} {banks}")


# ----------------------------
# Live MIDAS buffer analyzer
# ----------------------------

class LiveMidasAnalyzer:
    """
    Connects to MIDAS, opens an event buffer, receives events, parses them, and dispatches to modules.

    Uses methods documented for MIDAS Python client / SequenceClient:
      open_event_buffer(), register_event_request(), receive_event() :contentReference[oaicite:2]{index=2}
    """

    def __init__(
        self,
        progname: str = "pyana",
        hostname: str = "",
        exptname: str = "",
        buffer_name: str = "SYSTEM",
        sampling_type=midas.GET_NONBLOCKING,  # often what you want online
        event_id: int = -1,
        trigger_mask: int = -1,
        poll_sleep_s: float = 0.001,
        modules: Optional[List[Module]] = None,
    ):
        self.client = midas.client.MidasClient(progname, hostname, exptname)
        self.buffer_name = buffer_name
        self.sampling_type = sampling_type
        self.event_id = event_id
        self.trigger_mask = trigger_mask
        self.poll_sleep_s = poll_sleep_s

        self.modules = sorted(modules or [], key=lambda m: m.order)
        self.buf_handle = None
        self.req_id = None

        self._run_number: int = 0
        self._in_run: bool = False

    def _odb_get_int(self, path: str, default: int = 0) -> int:
        try:
            v = self.client.odb_get(path, recurse_dir=False)
            # odb_get can return dicts for directories; here it's a scalar
            return int(v)
        except Exception:
            return default

    def _check_run_state(self) -> None:
        """
        Lightweight run state machine similar to the C++ logic:
        - watch /Runinfo/State and /Runinfo/Run number
        - call begin_run/end_run on transitions
        """
        runno = self._odb_get_int("/Runinfo/Run number", self._run_number)
        state = self._odb_get_int("/Runinfo/State", 0)

        STATE_RUNNING = 3  # common MIDAS: 1=STOPPED, 2=PAUSED, 3=RUNNING (can vary by setup)
        now_in_run = (state == STATE_RUNNING)

        if now_in_run and not self._in_run:
            self._run_number = runno
            self._in_run = True
            for m in self.modules:
                m.begin_run(self._run_number)

        if (not now_in_run) and self._in_run:
            for m in self.modules:
                m.end_run(self._run_number)
            self._in_run = False

    def start(self) -> None:
        # open buffer + request events
        self.buf_handle = self.client.open_event_buffer(self.buffer_name)
        self.req_id = self.client.register_event_request(
            self.buf_handle,
            event_id=self.event_id,
            trigger_mask=self.trigger_mask,
            sampling_type=self.sampling_type,
        )

    def stop(self) -> None:
        # best-effort cleanup
        try:
            if self.buf_handle is not None and self.req_id is not None:
                self.client.deregister_event_request(self.buf_handle, self.req_id)
        except Exception:
            pass

    def loop(self) -> None:
        """
        Main online loop:
        - check run state
        - receive event from buffer
        - parse it
        - dispatch to modules
        """
        if self.buf_handle is None:
            raise RuntimeError("Call start() first")

        while True:
            # You can remove this if you don't care about Begin/End run hooks
            self._check_run_state()

            raw = self.client.receive_event(self.buf_handle, async_flag=True, use_numpy=False)
            if not raw:
                time.sleep(self.poll_sleep_s)
                continue

            ev = parse_midas_event(raw)

            # If you're not using ODB state, you can set run number from BOR serial, etc.
            runno = self._run_number

            for m in self.modules:
                m.analyze_event(runno, ev)


# ----------------------------
# Example: run it
# ----------------------------

if __name__ == "__main__":
    ana = LiveMidasAnalyzer(
        progname="pyana",
        hostname="",      # "" = local
        exptname="",      # "" = default
        buffer_name="SYSTEM",
        sampling_type=midas.GET_NONBLOCKING,
        event_id=-1,
        trigger_mask=-1,
        modules=[EventDumpModule()],
    )
    ana.start()
    try:
        ana.loop()
    finally:
        ana.stop()
