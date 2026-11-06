# Glasscalibur hardware v1.8 CAD — predictions

Written and committed before any file is added on branch `feature/hardware-v1.8`.
Read before this file: the source folder (29 files; one solid per STEP, millimetres,
empty author/organisation; binary STL files with consistent sizes; no flagged text) and
the CERN-OHL-S-2.0 text from CERN's own copy (13,419 bytes).

- Base: origin/main `3a4cc10`.
- Source: Daniel's `Glasscalibur-v1.8-2026-11-05` folder (printed/, machined/, extrusion/).

Rules as before: a result that differs from its prediction stops the work and is
reported; every check has a sabotage that must turn it red.

## Plan

`hardware/printed/`, `hardware/machined/`, `hardware/extrusion/` (the 29 files,
copied byte for byte); `hardware/README.md` (title, intro, the printed / machined /
extrusion tables as Daniel gave them, the thread note, "Not in these files" with the
motor described by specification only, the licence); `hardware/LICENSE` (CERN-OHL-S-2.0,
CERN's text byte for byte); the root README's License section gains a hardware line
(firmware stays GPL v3). No firmware, workflow or tool change.

## Checks

H1 The 29 files under hardware/printed, machined and extrusion have the same SHA-256 as
   the source files, and nothing else is in those folders.
   Sabotage: a copy with one byte changed gives a different hash.
H2 Every part named in the README tables has its STEP file (and, for printed parts,
   its STL), and every CAD file has a table row.
   Sabotage: the same check with one file missing reports it.
H3 hardware/LICENSE is byte-identical to CERN's text (SHA-256 prefix 253ad3f89603e728).
   Sabotage: a one-word change gives a different hash.
H4 Term checks: the local pre-push hook (motor terms) passes on the push; the docs
   wording scan finds 0 hits in hardware/README.md, the root README change and the PR
   text.
   Sabotage: a planted term is refused by the hook (its self-test, run in this
   session) and a planted claim is caught by the docs scan.
H5 Every relative link in hardware/README.md and the root README resolves.
   Sabotage: a planted broken link is reported.
C1 Only hardware/, README.md and this predictions file change; CI green.
