"""GPU ROM reading and firmware-table decoding.

Two independent read paths (kernel sysfs expansion-ROM attribute and the
BAR window through /dev/mem) that must agree byte for byte before anything
is trusted. Table decoding uses the pointer grammar imported from the
gpu-lab rings: P-token field offsets, and pointers past the legacy image
resolve relative to the EFI image end.
"""
import hashlib
import mmap
import os
import struct
import subprocess
from pathlib import Path

SYSFS = "/sys/bus/pci/devices"

# P-token field offsets (gpu-lab rings 3 and 14)
POWER_BUDGET_PTR = 0x2C
FAN_COOLER_PTR = 0x58
FAN_POLICY_PTR = 0x5C


def nvidia_pci_path():
    for entry in Path(SYSFS).glob("*"):
        vendor = entry / "vendor"
        if vendor.exists() and vendor.read_text().strip() == "0x10de":
            return entry
    raise SystemExit("error: no NVIDIA GPU found")


def read_via_sysfs(dev):
    """The kernel caps this at the PCI image-chain length — by design."""
    rom = dev / "rom"
    rom.write_text("1")
    try:
        return rom.read_bytes()
    finally:
        rom.write_text("0")


def read_via_bar(dev, size=0x80000, fallback_addr=0xFC000000):
    """Read the expansion-ROM BAR window through /dev/mem, then restore the
    BAR to 0. The address is the firmware-assigned one when present; never
    guess a scratch hole — outside the upstream bridges' decode ranges a
    read master-aborts to all-0xFF (gpu-lab rings 13/21)."""
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        raw = int.from_bytes((dev / "config").read_bytes()[:0x34][0x30:0x34], "little")
        addr = (raw & ~1) or fallback_addr
        with open(dev / "config", "r+b") as cf:
            cf.seek(0x30)
            cf.write((addr | 1).to_bytes(4, "little"))
            cf.flush()
        try:
            probe = mmap.mmap(fd, 0x1000, offset=addr)
            head = probe[:2]
            probe.close()
            if head != b"\x55\xaa":
                raise RuntimeError("window does not decode the ROM")
            window = mmap.mmap(fd, size, offset=addr)
            try:
                return window[:]
            finally:
                window.close()
        finally:
            with open(dev / "config", "r+b") as cf:
                cf.seek(0x30)
                cf.write((0).to_bytes(4, "little"))
                cf.flush()
    finally:
        os.close(fd)


def dual_read(out_dir, window_size=0x80000):
    """Dual read + cross-check. Returns a report dict; artifacts on disk."""
    dev = nvidia_pci_path()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sysfs = read_via_sysfs(dev)
    (out / "rom-sysfs.rom").write_bytes(sysfs)
    bar = read_via_bar(dev, window_size)
    (out / "rom-bar.rom").write_bytes(bar)
    n = min(len(sysfs), len(bar))
    report = {
        "device": dev.name,
        "sysfs_bytes": len(sysfs),
        "bar_bytes": len(bar),
        "prefix_match": sysfs[:n] == bar[:n],
        "sha256_sysfs": hashlib.sha256(sysfs).hexdigest(),
        "sha256_bar": hashlib.sha256(bar).hexdigest(),
    }
    return report


def image_layout(data):
    """(legacy image base/length, EFI image length) — pointers past the
    legacy image resolve relative to the EFI image end (gpu-lab ring 3)."""
    legacy = None
    efi_len = 0
    for base in range(0, len(data) - 0x20, 0x200):
        if data[base:base + 2] == b"\x55\xaa":
            pcir = base + struct.unpack_from("<H", data, base + 0x18)[0]
            if data[pcir:pcir + 4] == b"PCIR" and data[pcir + 0x14] == 0:
                legacy = {"base": base, "length": struct.unpack_from("<H", data, pcir + 0x10)[0] * 512}
                break
    if legacy:
        for probe in range(legacy["base"] + legacy["length"], len(data) - 0x20, 0x200):
            if data[probe:probe + 2] == b"\x55\xaa":
                pcir2 = probe + struct.unpack_from("<H", data, probe + 0x18)[0]
                if data[pcir2:pcir2 + 4] == b"PCIR" and data[pcir2 + 0x14] == 3:
                    efi_len = struct.unpack_from("<H", data, pcir2 + 0x10)[0] * 512
                break
    return legacy, efi_len


def find_p_token(data, base=0):
    bit = data.find(b"\xff\xb8BIT\x00", base, base + 0x10000)
    if bit < 0:
        raise SystemExit("error: BIT table not found")
    hlen, rlen, count = data[bit + 8], data[bit + 9], data[bit + 10]
    for i in range(count):
        off = bit + hlen + i * rlen
        if data[off:off + 1] == b"P":
            return base + struct.unpack_from("<H", data, off + 4)[0]
    raise SystemExit("error: no 'P' token in the BIT table")


def decode_tables(rom_path):
    """Decode the board's operative firmware tables and cross them against
    the live NVML power range. Honest refusal when a table lies beyond the
    supplied image."""
    rom = Path(rom_path).read_bytes()
    legacy, efi_len = image_layout(rom)
    if not legacy:
        raise SystemExit("error: no legacy image found")

    def resolve(raw):
        return legacy["base"] + raw if raw <= legacy["length"] else legacy["base"] + raw + efi_len

    token = find_p_token(rom, legacy["base"])
    out = {"image": {"legacy_base": legacy["base"], "legacy_len": legacy["length"], "efi_len": efi_len}}

    def table(field):
        raw = struct.unpack_from("<I", rom, token + field)[0]
        off = resolve(raw)
        if off + 4 > len(rom):
            return None, off
        return rom[off:off + 4], off

    hdr, off = table(POWER_BUDGET_PTR)
    if hdr and hdr[0] >= 0x30:
        cap = rom[off + 0xA]  # cap-entry index (gpu-lab ring 3)
        entry = off + hdr[1] + cap * hdr[2]
        out["power_budget_W"] = {
            "min": struct.unpack_from("<I", rom, entry + 2)[0] / 1000,
            "avg": struct.unpack_from("<I", rom, entry + 6)[0] / 1000,
            "peak": struct.unpack_from("<I", rom, entry + 10)[0] / 1000,
        }
    elif off is not None:
        out["power_budget_note"] = (
            f"power table at {off:#x} lies beyond this image ({len(rom):,} B) — supply the full dump")

    hdr, off = table(FAN_POLICY_PTR)
    if hdr and hdr[0] == 0x20 and hdr[2] == 0x33:
        records = []
        for i in range(hdr[3]):
            ro = off + hdr[1] + i * hdr[2]
            duties = list(rom[ro + 14:ro + 17])
            temps = [round(int.from_bytes(rom[ro + o:ro + o + 2], "little") / 32.0, 1) for o in (18, 22, 26)]
            rpms = [int.from_bytes(rom[ro + o:ro + o + 2], "little") for o in (20, 24, 28)]
            if duties == sorted(duties) and rpms == sorted(rpms) and any(rpms):
                records.append({"duty_pct": duties, "temp_c": temps, "rpm": rpms})
        out["fan_policy"] = records[:2]  # the operative curve; escalation records omitted
    elif off is not None:
        out["fan_policy_note"] = (
            f"fan table at {off:#x} lies beyond this image ({len(rom):,} B) — supply the full dump")

    try:
        live = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.min_limit,power.default_limit,power.max_limit",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip()
        if live:
            limits = [float(v) for v in live.split(",")]
            out["live_nvml_power_W"] = {"min": limits[0], "default": limits[1], "max": limits[2]}
    except (OSError, ValueError):
        pass
    return out
