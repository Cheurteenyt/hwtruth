---
name: hwtruth
description: >
  Hardware truth for NVIDIA GPUs and ASUS motherboards: Resizable BAR
  verification, VBIOS table decoding, power-budget cross-checks, fan-curve
  A/B testing, and pre-flash BIOS update advisories. Use whenever a
  question touches ReBAR, Above-4G, CSM, VBIOS, GPU power limit, GPU
  temperature, fan curves, boost clocks, underperformance, "is my GPU
  dying", "why is my GPU slow", BIOS update, flashing a BIOS, CAP file,
  AGESA, or a hardware purchase/upgrade decision. Triggers: ReBAR,
  Resizable BAR, Above-4G, CSM, BAR1, VBIOS, ROM, power limit, power
  budget, watt, fan curve, fan noise, boost clock, underperformance,
  thermal, BIOS update, flash, CAP, AGESA, hwtruth, LACT. This skill is
  read-only; the only mutations are reversible LACT settings.
---

# HWTruth Skill — evidence over assumptions

## The commands

| Command | What it proves | Requires |
|---|---|---|
| `hwtruth rebar-check` | BAR1 size → is ReBAR actually live | LACT daemon optional |
| `hwtruth rom read` | dual ROM read (sysfs + BAR), sha256 cross-check | root (sudo) |
| `hwtruth tables <rom>` | real power budget, stock fan policy vs live NVML | the ROM file |
| `hwtruth bios-diff old.CAP new.CAP` | what a BIOS update really changes | the two CAPs |
| `hwtruth fan test --curve-a A.json --curve-b B.json --load <cmd>` | sustained-boost delta between curves | LACT + a load |

## Interpretation tables (from the founding rings)

### ReBAR
- BAR1 = 8 GiB → live. Done; never touch it again.
- BAR1 = 256 MiB or small → almost always **CSM disabled Above-4G at
  boot**. Fix: firmware setup → Boot → CSM → Disabled, Above-4G Decoding →
  Enabled, ReBAR → Auto. Ring 18 proved it: the VBIOS supported ReBAR all
  along.

### Power budget
- The decoded `power_budget_W.peak` is the silicon ceiling. If it equals
  the live NVML max (typical: 250 W), there is **no hidden headroom** — do
  not promise gains from power mods. Ring 23 proved the agreement to the
  watt on the founding board.

### Benchmarks
- glmark2-family loads saturate at ~110 W of 250 W and never reach the
  thermal region where fan curves matter. For fan/thermal verdicts use the
  human's actual game with MangoHud, one variable at a time, paired runs.
- A delta inside the run-to-run noise (~±2 %) is **noise**. Say so.

### BIOS updates
- Run `bios-diff` first. A "certificate rollover + replaced module" pattern
  is housekeeping — the update can wait. A new AGESA marker may change
  memory behavior — flag it. hwtruth never flashes; the human decides and
  flashes from firmware setup.

## Failure modes already hit (do not repeat)

- `LACT vbios_dump` is AMD-only ("Not supported on Nvidia").
- sysfs `rom` is capped at the PCI image-chain length by the kernel.
- The ROM BAR window is 512 KiB of hardware; the rest of a 976 KiB chip
  needs SPI paging (nvflash) — in-session routes are sealed (ring 22).
- nvflash refuses to run with the kernel driver loaded. `nomodeset` does
  NOT prevent the module load (initramfs does it); the fix is
  `nvidia_drm.modeset=0 nvidia_drm.fbdev=0` on a maintenance boot entry.
- `sudo` with a heredoc pipes the script as the password → faillock. Use
  file-based scripts and `sudo -n` with allowlisted commands.
- LACT's GUI Revert button can fail; the daemon socket API is the reliable
  path (`batch_set_clocks_value` + `confirm_pending_config`).

## Escalation

Deep evidence lives in the labs: gpu-lab rings (cite the ring number) for
the GPU, the BIOS- repository for the motherboard. When evidence is
missing, say "undetermined" and propose the measurement that would decide.
