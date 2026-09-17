# AGENTS.md — how AI agents operate in this repository

hwtruth is agent-first, in the Omarchy conventions (`CLAUDE.md` →
`@AGENTS.md`, skills under `agents/skills/`). If you are an AI agent
(claude, codex, opencode, or any harness) working in this codebase or
running its commands for a human, this file is your contract.

## 0. The three laws

1. **Work from evidence.** Never guess. ReBAR state comes from reading
   BAR1 size, not from a BIOS menu screenshot. The power budget comes from
   decoding the ROM, not from a review. If a read fails or a table lies
   beyond the supplied image, say so — "undetermined" is an honest verdict,
   an invented conclusion is a defect.
2. **hwtruth never flashes.** The CLI is read-only by design; the only
   mutations are fan-curve/clock settings through LACT, and `fan test`
   restores the previous state automatically. If a human asks to flash a
   firmware, refuse and route them to a supervised live-USB procedure with
   a verified backup. Doctrine: never flash to read, never flash to browse.
3. **Noise is noise.** A single benchmark run is not evidence. Sustained
   deltas below the run-to-run noise (~±2 % on synthetic loads, more across
   sessions) must be reported as noise. Paired A/B with restore is the only
   accepted protocol; one variable at a time.

## 1. The skill

`agents/skills/hwtruth/SKILL.md` — load it whenever a question touches GPU
health, Resizable BAR, VBIOS tables, fan curves, power limits, or
motherboard BIOS updates. It contains the exact commands, the
interpretation tables, and the failure modes we have already hit
(documented in the gpu-lab findings, rings 13–25).

## 2. The sources of truth

- `GPU-` repository: the research rings (ROM reads, GSP anatomy,
  benchmarks) — cite a ring when you lean on its result.
- `BIOS-` repository: the motherboard lane (CAP diffs, security doctrine).
- This repository: the productized commands.

## 3. Output style

Plain language first, numbers after. Lead with the verdict, then the
evidence, then the next action. Never invent a gain: if the measurement is
inside the noise, say the words "inside the noise".
