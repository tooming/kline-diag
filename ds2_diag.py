#!/usr/bin/env python3
"""BMW DS2 diagnostics for pre-2001 cars (E39/E38/E36 era) over a K+DCAN cable.

DS2 runs on the K-line at 9600 baud **8E1** (even parity). Frames are
[ecu_addr, total_len, data..., XOR-checksum] in both directions; a positive
response carries status byte 0xA0. No session/init handshake is needed.

Modes:
  scan            probe known E39 ECU addresses: ident + fault memory
  sweep           probe every address 0x00-0xFF
  ident ADDR      identification block of one ECU (hex addr)
  faults ADDR     fault memory of one ECU
  status ADDR     probe 0x0B status sub-functions of one ECU (read-only)
  clear ADDR      clear fault memory (only with --yes)

Reuses the KLine transport from power_diag.py (raw termios; pyserial does
not work with this adapter on macOS). All traffic logs to kline_raw.log.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from power_diag import KLine, hexs, now  # noqa: E402

DS2_BAUD = 9600

E39_MODULES = {
    0x00: "GM/ZKE (general body module)",
    0x08: "SZM (switch center, console)",
    0x12: "DME (engine)",
    0x18: "CDC (CD changer)",
    0x32: "EGS (transmission)",
    0x44: "EWS (immobiliser)",
    0x50: "MFL (wheel controls)",
    0x56: "ABS/ASC/DSC",
    0x5B: "IHKA (climate)",
    0x60: "PDC (park distance)",
    0x68: "RADIO",
    0x6A: "DSP (audio)",
    0x80: "IKE (instrument cluster)",
    0xA4: "MRS (airbag)",
    0xC0: "MID (multi-info display)",
    0xC8: "TEL (telephone)",
    0xD0: "LCM (light check module)",
}

STATUS_BYTE = {0xA0: "OK", 0xA1: "busy", 0xA2: "invalid parameter",
               0xFF: "invalid command"}


def _load_dtc_table(name):
    """Fault-code tables live as JSON next to this script (decimal code ->
    text). ms41_dtc.json came from the OpenMS41 project documentation."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
    try:
        import json
        with open(path) as f:
            return {int(k): v for k, v in json.load(f).items()}
    except OSError:
        return {}


def _load_body_tables():
    """e39_body_dtc_en.json: fault location (ort) + type (art) texts per module,
    extracted from the BMW SGBD docs (emdzej/ediabasx-docs-sgbd) and translated
    to English. Returns (ort_by_addr, art_by_addr) with int keys."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "e39_body_dtc_en.json")
    ort, art = {}, {}
    try:
        import json
        with open(path) as f:
            data = json.load(f)
        for addr_s, entry in data.items():
            if not addr_s.startswith("0x"):
                continue
            addr = int(addr_s, 16)
            ort[addr] = {int(k): v for k, v in entry.get("ort", {}).items()}
            art[addr] = {int(k): v for k, v in entry.get("art", {}).items()}
    except OSError:
        pass
    return ort, art


# per-ECU-address fault code lookup tables (first byte of a fault entry)
DTC_TABLES = {0x12: _load_dtc_table("ms41_dtc.json")}
_ort, ART_TABLES = _load_body_tables()
DTC_TABLES.update(_ort)


def fault_type_text(addr, art_byte):
    """Decode a fault entry's type byte (2nd byte). Exact match first, then
    the low nibble (the high bits carry present/stored flags on some ECUs)."""
    t = ART_TABLES.get(addr, {})
    return t.get(art_byte) or t.get(art_byte & 0x0F) or ""


def xor(data):
    c = 0
    for b in data:
        c ^= b
    return c


class DS2:
    def __init__(self, kl):
        self.kl = kl

    def _read_frame(self, deadline):
        """Parse one DS2 frame [addr, len, ..., xor] from the stream."""
        while now() < deadline:
            buf = self.kl.buf
            # drop leading nulls (bus noise)
            while buf[:1] == b"\x00":
                buf = buf[1:]
            self.kl.buf = buf
            if len(buf) >= 2:
                ln = buf[1]
                if 3 <= ln <= 120:
                    if len(buf) >= ln:
                        frame = buf[:ln]
                        if xor(frame[:-1]) == frame[-1]:
                            self.kl.buf = buf[ln:]
                            self.kl.log("<<", frame)
                            return frame
                        self.kl.buf = buf[1:]  # bad cks: resync
                        continue
                else:
                    self.kl.buf = buf[1:]  # implausible length: resync
                    continue
            self.kl._pump(min(0.05, deadline - now()))
        return None

    def request(self, addr, payload, timeout=0.4, retries=1):
        msg = bytes([addr, len(payload) + 3]) + bytes(payload)
        msg += bytes([xor(msg)])
        for attempt in range(retries + 1):
            if attempt:
                time.sleep(0.05)
            self.kl.flush()
            self.kl.log(">>", msg, "(retry)" if attempt else "")
            self.kl.write_raw(msg)
            self.kl.drain()
            deadline = now() + timeout
            # strip our own K-line echo
            while len(self.kl.buf.lstrip(b"\x00")) < len(msg) \
                    and now() < deadline:
                self.kl._pump(0.02)
            b = self.kl.buf.lstrip(b"\x00")
            if b[: len(msg)] == msg:
                self.kl.buf = b[len(msg):]
            f = self._read_frame(deadline)
            if f is not None:
                return f
        return None

    def ident(self, addr, timeout=0.4):
        return self.request(addr, [0x00], timeout=timeout)

    def sia_reset(self, kind=0x01):
        """Reset the service interval display via the IKE (0x80).

        EXPERIMENTAL: selector values are documented (KOMBI39 SGBD SIARESET
        table: 0x01 oil, 0x02 distance, 0x04 time) but the DS2 command byte
        is not public; 0x31 was rejected 0xFF (invalid command) on this car.
        Do NOT probe blindly — the neighbouring command space includes
        cluster coding writes. If a KOMBI39.prg or an INPA trace of
        SIA_RESET becomes available, put the real bytes here.
        The always-working manual fallback: hold the odometer button while
        turning the ignition to position 1, keep holding ~5 s until
        "OIL SERVICE RESET" appears, release, press again to confirm.
        """
        return self.request(0x80, [0x31, kind], timeout=1.5)

    def faults(self, addr):
        return self.request(addr, [0x04], timeout=0.8)

    def clear(self, addr):
        return self.request(addr, [0x05], timeout=1.5)

    def read_coding(self, addr):
        """
        Read coding data from module (0x08 service).

        Returns:
            Frame with coding data, or None if failed
        """
        return self.request(addr, [0x08], timeout=0.5)

    def write_coding(self, addr, coding_bytes):
        """
        Write coding data to module (0x07 service).

        Args:
            addr: Module address
            coding_bytes: Coding data to write

        Returns:
            Frame with response, or None if failed

        WARNING: This modifies module configuration. Use with caution.
        Always backup current coding before writing.
        """
        payload = [0x07] + list(coding_bytes)
        return self.request(addr, payload, timeout=1.0)


def body(frame):
    """Payload after addr+len+status, before checksum."""
    return frame[3:-1]


class MS41Logger:
    """Fast multi-parameter logging from the MS41 DME via the DS2
    address-list mechanism (verified against RomRaider's DS2 support):

      set list : 12 len 0B 01 [type addr32]*N cks   (type 0=byte 1=word
                 2=ADC-procedure for addresses < 0x1C), ack = A0
      read     : 12 05 0B 00 cks -> A0 + values in list order

    Parameter addresses/conversions come from ms41_ram_params.json
    (RomRaider logger definition v353, ECU id 1429861).
    """
    def __init__(self, ds2, params):
        self.ds2 = ds2
        self.params = params  # list of dicts from ms41_ram_params.json
        self.armed = False

    @staticmethod
    def value_size(p):
        if int(p["addr"], 16) < 0x1C:
            return 2  # ADC procedure reads return a word
        return 2 if p["storagetype"] in ("uint16", "int16") else 1

    def arm(self):
        payload = [0x0B, 0x01, len(self.params)]
        for p in self.params:
            a = int(p["addr"], 16)
            t = 2 if a < 0x1C else (self.value_size(p) - 1)
            payload += [t, (a >> 24) & 0xFF, (a >> 16) & 0xFF,
                        (a >> 8) & 0xFF, a & 0xFF]
        f = self.ds2.request(0x12, payload, timeout=0.8)
        self.armed = f is not None and f[2] == 0xA0
        return self.armed

    def sample(self):
        if not self.armed and not self.arm():
            return None
        f = self.ds2.request(0x12, [0x0B, 0x00], timeout=0.5, retries=0)
        if f is None or f[2] != 0xA0:
            self.armed = False  # ECU may have restarted; re-arm next time
            return None
        data = body(f)
        out = {}
        i = 0
        for p in self.params:
            n = self.value_size(p)
            if i + n > len(data):
                break
            v = int.from_bytes(data[i:i + n], "big")
            if p["storagetype"] == "int16" and v > 32767:
                v -= 65536
            i += n
            try:
                out[p["id"]] = round(eval(p["expr"], {"__builtins__": {}},
                                          {"x": v}), 2)
            except Exception:
                out[p["id"]] = v
        return out


def ram_read(ds2, addresses, width=1):
    """Read-only RAM explorer (Phase 7.1). Reads a list of 16/32-bit MS41
    RAM addresses via the SAME address-list mechanism MS41Logger uses
    (arm `0B 01`, read `0B 00`) — verified working. `width` is bytes per
    value (1 or 2). Returns {addr_int: raw_value} or None on failure.

    Read-only by construction: the address list only reads; there is no
    write path here. Safe to call freely.
    """
    addrs = [a if isinstance(a, int) else int(a, 16) for a in addresses]
    payload = [0x0B, 0x01, len(addrs)]
    for a in addrs:
        t = 2 if a < 0x1C else (width - 1)  # 0=byte,1=word,2=ADC-proc
        payload += [t, (a >> 24) & 0xFF, (a >> 16) & 0xFF,
                    (a >> 8) & 0xFF, a & 0xFF]
    f = ds2.request(0x12, payload, timeout=0.8)
    if f is None or f[2] != 0xA0:
        return None
    f = ds2.request(0x12, [0x0B, 0x00], timeout=0.5)
    if f is None or f[2] != 0xA0:
        return None
    data = body(f)
    out, i = {}, 0
    for a in addrs:
        n = 2 if (a < 0x1C or width == 2) else 1
        if i + n > len(data):
            break
        out[a] = int.from_bytes(data[i:i + n], "big")
        i += n
    return out


def ram_dump_range(ds2, start, count, width=1, chunk=16):
    """Read a contiguous RAM window (start..start+count) in chunks. Read-only.
    Returns {addr: value}. Useful for the idle-vs-rev VANOS probe."""
    result = {}
    a = start
    end = start + count
    while a < end:
        block = list(range(a, min(a + chunk, end)))
        r = ram_read(ds2, block, width=width)
        if r is None:
            break
        result.update(r)
        a += chunk
    return result


def ram_diff(dump_a, dump_b, min_delta=1):
    """Offline (Phase 7.3): compare two RAM dumps ({addr:value}), return the
    addresses that changed, sorted by magnitude. Pure function, no car."""
    out = []
    for addr in sorted(set(dump_a) & set(dump_b)):
        d = dump_b[addr] - dump_a[addr]
        if abs(d) >= min_delta:
            out.append({"addr": addr, "hex": f"0x{addr:04X}",
                        "a": dump_a[addr], "b": dump_b[addr], "delta": d})
    out.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return out


def show_ident(frame):
    data = body(frame)
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in data)
    print(f"   ident: {hexs(data)}")
    print(f"          |{asc}|")


def show_faults(frame, addr=None):
    st = frame[2]
    data = body(frame)
    if st != 0xA0:
        print(f"   fault read: status 0x{st:02X} "
              f"({STATUS_BYTE.get(st, '?')})")
        return
    if not data or data[0] == 0:
        print("   faults: none stored")
        return
    n = data[0]
    rest = data[1:]
    table = DTC_TABLES.get(addr, {})
    print(f"   faults ({n}): raw {hexs(rest) or '(no fault bytes)'}")
    # entry size varies per ECU; if it divides evenly, show grouped
    if n and rest and len(rest) % n == 0:
        size = len(rest) // n
        for k in range(n):
            e = rest[k * size:(k + 1) * size]
            code = f"0x{e[0]:02X}" + (f"{e[1]:02X}" if size >= 2 else "")
            note = "  (empty slot)" if not any(e) else ""
            text = table.get(e[0])
            if text and any(e):
                note = f"  = {text}"
                if size >= 2:
                    art = fault_type_text(addr, e[1])
                    if art:
                        note += f" [{art}]"
            print(f"     #{k + 1}: {hexs(e)}   (code {code}){note}")


def probe(ds2, addr, name=None, timeout=0.4):
    f = ds2.ident(addr, timeout=timeout)
    if f is None:
        return False
    print(f"\n== 0x{addr:02X} {name or E39_MODULES.get(addr, '?')} "
          f"(status 0x{f[2]:02X})")
    show_ident(f)
    ff = ds2.faults(addr)
    if ff is None:
        print("   fault read: no response")
    else:
        show_faults(ff, addr=addr)
    return True


def mode_live(ds2, duration=None):
    """Poll DME analog block (0B 03) + IKE block (0B 0A); annotate changes.

    Byte meanings on MS41 are not fully documented here, so this shows the
    raw block, marks bytes that changed since the previous sample, and
    annotates values that match BMW's usual scalings (temp = x*0.75-48,
    voltage = x*0.1).
    """
    prev = {}
    start = now()
    try:
        while duration is None or now() - start < duration:
            for addr, sub_id, name in ((0x12, 0x03, "DME"),
                                       (0x80, 0x0A, "IKE")):
                f = ds2.request(addr, [0x0B, sub_id], timeout=0.4)
                if f is None or f[2] != 0xA0:
                    print(f"{name}: no data")
                    continue
                data = body(f)
                marks = []
                old = prev.get(addr)
                for i, b in enumerate(data):
                    if old and i < len(old) and old[i] != b:
                        marks.append(f"[{i}]:{old[i]:02X}->{b:02X}")
                prev[addr] = data
                ts = time.strftime("%H:%M:%S")
                print(f"{ts} {name} {hexs(data)}")
                if marks:
                    print(f"         changed: {' '.join(marks)}")
                notes = []
                for i, b in enumerate(data):
                    if 95 <= b <= 160:
                        notes.append(f"[{i}]={b} -> {b / 10:.1f}V? "
                                     f"or {b * 0.75 - 48:.0f}C?")
                if notes and old is None:
                    print(f"         plausible: {'; '.join(notes)}")
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--port", default=None)
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("scan")
    sub.add_parser("sweep")
    p = sub.add_parser("live")
    p.add_argument("--duration", type=float, default=None)
    for m in ("ident", "faults", "status", "clear"):
        p = sub.add_parser(m)
        p.add_argument("addr", type=lambda s: int(s, 16))
        if m == "clear":
            p.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    kw = dict(show_raw=args.raw,
              rawlog_path=os.path.join(here, "kline_raw.log"),
              baud=DS2_BAUD, parity="E")
    kl = KLine(args.port, **kw) if args.port else KLine(**kw)
    ds2 = DS2(kl)
    try:
        if args.mode == "live":
            mode_live(ds2, args.duration)
        elif args.mode == "scan":
            found = [a for a in E39_MODULES if probe(ds2, a)]
            print(f"\nResponding: {', '.join(f'0x{a:02X}' for a in found) or 'none'}")
        elif args.mode == "sweep":
            found = []
            for a in range(0x100):
                if probe(ds2, a, name=f"(sweep 0x{a:02X})", timeout=0.25):
                    found.append(a)
            print(f"\nResponding: {', '.join(f'0x{a:02X}' for a in found) or 'none'}")
        elif args.mode == "ident":
            f = ds2.ident(args.addr)
            print("no response" if f is None else "", end="")
            if f:
                show_ident(f)
        elif args.mode == "faults":
            f = ds2.faults(args.addr)
            if f is None:
                print("no response")
            else:
                show_faults(f, addr=args.addr)
        elif args.mode == "status":
            # probe read-only 0x0B sub-functions, show raw
            for p in range(0x00, 0x20):
                f = ds2.request(args.addr, [0x0B, p], timeout=0.3)
                if f is not None and f[2] == 0xA0:
                    print(f"0B {p:02X}: {hexs(body(f))}")
        elif args.mode == "clear":
            if not args.yes:
                sys.exit("refusing to clear fault memory without --yes "
                         "(capture 'faults' output first!)")
            f = ds2.clear(args.addr)
            print("no response" if f is None
                  else f"clear: status 0x{f[2]:02X}")
            f = ds2.faults(args.addr)
            if f is not None:
                show_faults(f, addr=args.addr)
    finally:
        kl.close()


if __name__ == "__main__":
    main()
