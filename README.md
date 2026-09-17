# hwtruth — the hardware truth CLI

Born from 25 reverse-engineering rings on an RTX 3070 and an ASUS B550
board. The doctrine: **read the truth (ROM, firmware tables, live state),
cross it, apply only what is safe, refuse the rest.**

Built for [Omarchy](https://omarchy.org) and every other Linux: pure
Python standard library, no daemons of its own, read-only by default.

## Why

Your distribution will not tell you the hardware truth. Resizable BAR is
"enabled" while CSM silently kills it. Your power limit hides the real
firmware budget. Fan curves are chosen blind. `hwtruth` replaces
assumptions with cross-verified measurements:

- **`hwtruth rebar-check`** — the founding fix: is Resizable BAR *actually*
  live (8 GiB of BAR1), or silently killed by CSM?
- **`hwtruth rom read`** — dual-read the GPU ROM through two independent
  paths (kernel sysfs + the expansion-ROM BAR window), cross-verified by
  sha256. Read-only; the BAR is restored afterwards.
- **`hwtruth tables <rom>`** — decode the board's real firmware tables
  (power budget, stock fan curve, vP-states) and cross them against the
  live NVML power range. Honestly refuses when a table lies beyond the
  supplied image.
- **`hwtruth fan test`** — paired A/B of two fan curves on your own load
  with automatic restore. Decide with data, not vibes.
- **`hwtruth bios-diff old.CAP new.CAP`** — what does a motherboard BIOS
  update actually change? Firmware volumes, replaced module blocks,
  certificate rollovers and AGESA markers, in plain language — before you
  flash. No public tool does this.

## Install

```bash
pip install --user git+https://github.com/Cheurteenyt/hwtruth
```

Or without installing:

```bash
PYTHONPATH=. python3 -m hwtruth rebar-check
```

## Usage

```console
$ hwtruth rebar-check
GPU 0000:07:00.0
BAR1: 8 GiB
ReBAR: LIVE — Above-4G decoding is up and the CPU sees the full aperture.

$ hwtruth tables rom-full.rom
{
  "power_budget_W": { "min": 100.0, "avg": 240.0, "peak": 250.0 },
  "fan_policy": [
    { "duty_pct": [17, 45, 100], "temp_c": [55.0, 75.0, 80.0], "rpm": [1000, 2100, 3250] }
  ],
  "live_nvml_power_W": { "min": 100.0, "default": 240.0, "max": 250.0 }
}
firmware peak 250 W vs live max 250 W -> AGREES
```

## The research behind it

hwtruth is the product of two research repositories:

- [GPU-](https://github.com/Cheurteenyt/GPU-) — the graphics card, 25
  rings: VBIOS grammar, ROM reads, GSP firmware anatomy, benchmarks.
- [BIOS-](https://github.com/Cheurteenyt/BIOS-) — the motherboard:
  firmware audits, CAP diffing, security doctrine.

The labs produce the truth; hwtruth makes it universal.

## Omarchy plugin

The repository is itself an Omarchy shell plugin (bar widget + panel):

```bash
omarchy plugin add https://github.com/Cheurteenyt/hwtruth --enable
```

The bar widget shows live GPU temperature and power; the panel runs the
read-only hwtruth checks (ReBAR verification with graceful fallback if the
CLI is not installed yet).

## Agentic by design

`agents/AGENTS.md` is the contract AI agents work under (evidence over
assumptions, never flash, noise is noise), and
`agents/skills/hwtruth/SKILL.md` packages the 25-ring knowledge —
interpretation tables, failure modes, escalation paths — so any Omarchy
agent can diagnose hardware with evidence instead of vibes.

## Roadmap

- [x] `rebar-check`, `rom read`, `tables`, `bios-diff`, `fan test`
- [ ] Omarchy plugin packaging
- [ ] ROM reads beyond the 512 KiB BAR window (SPI paging)

## License

MIT.
