import struct
import io
from dataclasses import dataclass
import lz4.frame
import numpy as np
import matplotlib.pyplot as plt


@dataclass
class MidasEvent:
    event_id: int = 0
    trigger_mask: int = 0
    serial_number: int = 0
    time_stamp: int = 0
    data_size: int = 0
    all_bank_size: int = 0
    bank_flags: int = 0
    offset: int = 0


@dataclass
class MidasBank:
    name: str = "    "
    type: int = 0
    size: int = 0
    data: bytes = b""


class MidasFile:
    EVENT_ID_BOR = 0x8000
    EVENT_ID_EOR = 0x8001

    BANK_FLAG_VERSION = 1
    BANK_FLAG_32BIT = 1 << 4
    BANK_FLAG_64BIT_ALIGNED = 1 << 5

    def __init__(self, path: str | io.BufferedReader):
        self.fh = open(path, "rb") if isinstance(path, str) else path
        self.decomp = lz4.frame.LZ4FrameDecompressor()

        self.src_chunk = 16 * 1024
        self.dst = bytearray()
        self.dst_pos = 0

        self.file_offset = 0
        self.event = MidasEvent()
        self.bank = MidasBank()

        self._preread()

    def close(self):
        self.fh.close()

    # -----------------------
    # Decompression
    # -----------------------

    def _preread(self) -> int:
        """
        Decompress until some output is produced or EOF.
        """
        while True:
            chunk = self.fh.read(self.src_chunk)
            if not chunk:
                return 0

            out = self.decomp.decompress(chunk)
            if out:
                self.dst = bytearray(out)
                self.dst_pos = 0
                return len(out)

            if self.decomp.eof:
                return 0

    def _read_exact(self, n: int) -> bytes:
        out = bytearray()
        while n > 0:
            if self.dst_pos >= len(self.dst):
                if self._preread() == 0:
                    raise EOFError("Unexpected end of MIDAS file")

            avail = len(self.dst) - self.dst_pos
            k = min(n, avail)

            out += self.dst[self.dst_pos:self.dst_pos + k]
            self.dst_pos += k
            self.file_offset += k
            self.event.offset += k
            n -= k

        return bytes(out)

    def skip(self, n: int):
        if n > 0:
            self._read_exact(n)

    def _u16(self) -> int:
        return struct.unpack("<H", self._read_exact(2))[0]

    def _u32(self) -> int:
        return struct.unpack("<I", self._read_exact(4))[0]

    # -----------------------
    # MIDAS parsing
    # -----------------------

    def next_event(self) -> int:
        # Skip remaining payload
        rem = self.event.data_size - self.event.offset
        if rem > 0:
            self.skip(rem)

        self.event = MidasEvent()

        if self.dst_pos >= len(self.dst) and self._preread() == 0:
            return -1

        self.event.event_id = self._u16()
        self.event.trigger_mask = self._u16()
        self.event.serial_number = self._u32()
        self.event.time_stamp = self._u32()
        self.event.data_size = self._u32()
        self.event.offset = 0

        if self.event.event_id not in (self.EVENT_ID_BOR, self.EVENT_ID_EOR):
            self.event.all_bank_size = self._u32()
            self.event.bank_flags = self._u32()

        return self.event.data_size

    def next_bank(self) -> int:
        self.bank = MidasBank()

        if self.event.all_bank_size == 0:
            return -1
        if self.event.offset >= self.event.data_size:
            return -1

        self.bank.name = self._read_exact(4).decode("ascii", "replace")

        flags = self.event.bank_flags

        if flags == self.BANK_FLAG_VERSION:
            self.bank.type = self._u16()
            self.bank.size = self._u16()
        elif flags == (self.BANK_FLAG_VERSION | self.BANK_FLAG_32BIT):
            self.bank.type = self._u32()
            self.bank.size = self._u32()
        elif flags == (self.BANK_FLAG_VERSION | self.BANK_FLAG_32BIT | self.BANK_FLAG_64BIT_ALIGNED):
            self.bank.type = self._u32()
            self.bank.size = self._u32()
            self.skip(4)
        else:
            raise NotImplementedError(f"Unsupported bank flags 0x{flags:X}")

        self.bank.data = self._read_exact(self.bank.size)

        if flags & self.BANK_FLAG_64BIT_ALIGNED:
            pad = self.event.offset % 8
            if pad:
                self.skip(8 - pad)

        return self.bank.size


def bank_as_numpy(bank_data: bytes, dtype=np.float32, little_endian: bool = True) -> np.ndarray:
    dt = np.dtype(dtype)
    dt = dt.newbyteorder("<" if little_endian else ">")

    if len(bank_data) % dt.itemsize != 0:
        raise ValueError(f"Bank size {len(bank_data)} not divisible by {dt.itemsize} bytes")

    # zero-copy view of the bytes (very fast)
    return np.frombuffer(bank_data, dtype=dt)

# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    file = MidasFile("run00053.mid.lz4")
    while file.next_event() != -1:
        # mf.event now holds event header fields
        # iterate banks
        t_ns = None
        up = down = block = None
        while file.next_bank() != -1:
            # mf.bank holds name/type/size/data

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

        #plt.plot(t_ns, up, color="red", label="up")
        #plt.plot(t_ns, down, color="blue", label="down")
        plt.plot(t_ns, block, color="green", label="block")

    plt.show()
