"""Motherboard BIOS CAP diffing.

Takes two ASUS .CAP files (or any flash-image pair), reports which firmware
volumes and modules changed, extracts semantic markers (certificate
rollover timestamps, build dates, AGESA markers), and renders a plain-language
verdict: is this update maintenance, a security change, or a major landing?

Imported from the gpu-lab/BIOS- rings: the 3644-to-3645 analysis that saved
the founder from an unnecessary flash.
"""
import re
import uuid
from pathlib import Path

BLOCK = 512


def _changed_regions(old, new):
    changed = []
    for i in range(0, len(old), BLOCK):
        if old[i:i + BLOCK] != new[i:i + BLOCK]:
            changed.append(i)
    ranges = []
    for i in changed:
        if ranges and i == ranges[-1][1]:
            ranges[-1][1] = i + BLOCK
        else:
            ranges.append([i, i + BLOCK])
    return ranges


def _firmware_volumes(data):
    volumes = []
    pos = 0
    while True:
        i = data.find(b"_FVH", pos)
        if i == -1:
            break
        base = i - 40
        if base >= 0:
            guid = str(uuid.UUID(bytes_le=data[base + 16:base + 32]))
            length = int.from_bytes(data[base + 32:base + 40], "little")
            if 0 < length <= len(data):
                volumes.append({"offset": base, "guid": guid, "length": length})
        pos = i + 1
    return volumes


def _cert_timestamps(data):
    """X.509 NotBefore/NotAfter-style stamps, e.g. 260910084920Z."""
    return sorted(set(m.group().decode() for m in re.finditer(rb"\d{12}Z", data)))


def _dates(data):
    return sorted(set(m.group().decode() for m in re.finditer(rb"\d{2}/\d{2}/\d{2,4}", data)))


def _agesa(data):
    markers = set()
    for pattern in (rb"AGESA[ -~]{0,40}", rb"ComboAM4[ -~]{0,30}", rb"PI-1\.[0-9.]+"):
        markers.update(m.group().decode(errors="replace") for m in re.finditer(pattern, data))
    return markers


def diff(old_path, new_path):
    old = Path(old_path).read_bytes()
    new = Path(new_path).read_bytes()
    report = {
        "old": {"file": Path(old_path).name, "bytes": len(old),
                "sha256": __import__("hashlib").sha256(old).hexdigest()},
        "new": {"file": Path(new_path).name, "bytes": len(new),
                "sha256": __import__("hashlib").sha256(new).hexdigest()},
    }
    if len(old) != len(new):
        report["note"] = "different sizes — not the same flash layout, deep diff skipped"
        return report

    regions = _changed_regions(old, new)
    report["changed_regions"] = len(regions)
    report["changed_bytes"] = sum(b - a for a, b in regions)
    report["regions"] = [{"start": hex(a), "end": hex(b), "bytes": b - a} for a, b in
                         sorted(regions, key=lambda r: r[0] - r[1])[:12]]

    volumes = _firmware_volumes(old)
    touched = []
    for vol in volumes:
        hits = [r for r in regions if vol["offset"] <= r[0] < vol["offset"] + vol["length"]]
        if hits:
            touched.append({"guid": vol["guid"], "offset": hex(vol["offset"]),
                            "length": vol["length"], "regions": len(hits)})
    report["volumes_touched"] = touched

    big = max(regions, key=lambda r: r[1] - r[0], default=None)
    if big:
        report["largest_region"] = {"start": hex(big[0]), "bytes": big[1] - big[0]}

    old_certs, new_certs = _cert_timestamps(old), _cert_timestamps(new)
    added_certs = [c for c in new_certs if c not in old_certs]
    if added_certs:
        report["certificate_rollover"] = added_certs

    old_a, new_a = _agesa(old), _agesa(new)
    report["agesa_markers"] = {"unchanged": sorted(new_a & old_a)[:6] or "none visible",
                               "added": sorted(new_a - old_a)[:6] or "none visible"}

    report["verdict"] = _verdict(report, regions, added_certs, new_a - old_a)
    return report


def _verdict(report, regions, added_certs, new_agesa):
    total = report["changed_bytes"]
    parts = []
    if added_certs:
        parts.append("signing-certificate rollover (security housekeeping)")
    if new_agesa:
        parts.append(f"new AGESA markers ({', '.join(sorted(new_agesa))}) — may change memory/board behaviour")
    if report["volumes_touched"] and report["largest_region"] and report["largest_region"]["bytes"] > 1_000_000:
        parts.append(f"a large module block was replaced ({report['largest_region']['bytes']:,} B) "
                     "in the main firmware volume")
    if len(regions) < 20 and total < 200_000:
        parts.append("only version stamps and small tables changed")
    if not parts:
        parts.append("diffuse small changes")
    return " + ".join(parts)
