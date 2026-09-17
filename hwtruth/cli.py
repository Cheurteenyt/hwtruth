"""hwtruth command-line interface."""
import argparse
import json
import sys
from pathlib import Path

from . import bench, rom


def cmd_rebar_check(_args):
    """Is Resizable BAR actually live? CSM silently kills it on many boards."""
    dev = rom.nvidia_pci_path()
    resource = (dev / "resource").read_text().splitlines()
    bar1 = None
    for index, line in enumerate(resource):
        fields = line.split()
        if len(fields) >= 3 and index == 1:
            start, end = int(fields[0], 16), int(fields[1], 16)
            if end > start:
                bar1 = end - start + 1
    size_gib = bar1 / 2**30 if bar1 else 0
    print(f"GPU {dev.name}")
    print(f"BAR1: {size_gib:.0f} GiB")
    if size_gib >= 8:
        print("ReBAR: LIVE — Above-4G decoding is up and the CPU sees the full aperture.")
    elif size_gib > 0:
        print("ReBAR: SMALL — Above-4G/ReBAR are likely off. "
              "In your firmware: CSM -> Disabled, Above-4G Decoding -> Enabled, ReBAR -> Auto.")
    else:
        print("ReBAR: no BAR1 exposed.")
    return 0


def cmd_rom_read(args):
    report = rom.dual_read(args.out, window_size=args.window * 1024)
    print(json.dumps(report, indent=1))
    if not report["prefix_match"]:
        print("MISMATCH — the two independent reads disagree. Trust neither. STOP.", file=sys.stderr)
        return 1
    print("CROSS-VERIFIED: two independent paths, one truth. Read-only; nothing was written to the GPU.")
    return 0


def cmd_tables(args):
    report = rom.decode_tables(args.rom)
    print(json.dumps(report, indent=1))
    if "power_budget_W" in report and "live_nvml_power_W" in report:
        peak, live_max = report["power_budget_W"]["peak"], report["live_nvml_power_W"]["max"]
        state = "AGREES" if abs(peak - live_max) < 1 else "DISAGREES — investigate"
        print(f"firmware peak {peak:.0f} W vs live max {live_max:.0f} W -> {state}")
    return 0


def cmd_fan_test(args):
    curve_a = json.loads(Path(args.curve_a).read_text())
    curve_b = json.loads(Path(args.curve_b).read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = bench.run_ab(curve_a, curve_b, args.load, args.instances, args.seconds, out_dir)
    print(f"sustained boost delta B-A: {results['delta_core_mhz']:+.0f} MHz "
          f"(compare against the run-to-run noise you have seen)")
    print(f"curve A restored. Decide with real data; keep the winner yourself.")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="hwtruth",
        description="The hardware truth CLI: cross-verified GPU/motherboard truth, "
                    "born from 25 reverse-engineering rings.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("rebar-check", help="is Resizable BAR actually live?").set_defaults(func=cmd_rebar_check)

    rom_p = sub.add_parser("rom", help="GPU ROM operations")
    rom_sub = rom_p.add_subparsers(dest="rom_command", required=True)
    read_p = rom_sub.add_parser("read", help="dual-read the ROM (sysfs + BAR window) and cross-verify")
    read_p.add_argument("--out", default="day0/hwtruth-rom")
    read_p.add_argument("--window", type=int, default=512, help="BAR window size to read, in KiB (default 512)")
    read_p.set_defaults(func=cmd_rom_read)

    tables_p = sub.add_parser("tables", help="decode the board's firmware tables, cross-checked with live state")
    tables_p.add_argument("rom", help="path to a ROM image (full dump preferred)")
    tables_p.set_defaults(func=cmd_tables)

    fan_p = sub.add_parser("fan", help="fan-curve experiments")
    fan_sub = fan_p.add_subparsers(dest="fan_command", required=True)
    test_p = fan_sub.add_parser("test", help="paired A/B of two fan curves with automatic restore")
    test_p.add_argument("--curve-a", required=True, help="JSON file: {temperature: duty 0-1}")
    test_p.add_argument("--curve-b", required=True, help="JSON file: {temperature: duty 0-1}")
    test_p.add_argument("--load", nargs="+", required=True, help="load command, e.g. --load glmark2-wayland --off-screen")
    test_p.add_argument("--instances", type=int, default=3)
    test_p.add_argument("--seconds", type=int, default=300)
    test_p.add_argument("--out", default="day0/hwtruth-fan")
    test_p.set_defaults(func=cmd_fan_test)
    return parser


def main():
    args = build_parser().parse_args()
    sys.exit(args.func(args) or 0)
