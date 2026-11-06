# Glasscalibur docs rewrite — predictions

Written and committed before any doc change on branch `docs/current-design`.
No check below had been run when this file was committed, except the docs-wording
baseline on main (22 hits in the old docs, 5 of them in CHANGELOG.md).

- Base: origin/main `ac01bd3` (firmware split into packages).

Rules as before: a result that differs from its prediction stops the work and is
reported; no reading = instrument failure, rerun, reported; every check has a
sabotage that must turn it red.

## The request (Daniel, 2026-11-05)

Rewrite README.md (what it is, how it works, features, install overview, Home
Assistant and the browser UI, updates, links to the firmware docs) and
firmware/README.md (flashing, OTA updates, first setup, calibration and the Fast
speed lock, the learned open stroke, each fault and what to do, the bench self-test
if merged, an entity reference). Fold firmware/esphome/README.md and
Glasscalibur-auto-calibrate.md into these two. Every firmware fact from the code;
hardware facts only from Daniel's list; licence as firmware/LICENSE says. No claims of
child safety, fall prevention, compliance with any window-opening-control standard, or
any certification; never name the motor vendor. Anything unverifiable is left out and
listed in the reply.

## Plan

- README.md and firmware/README.md rewritten; firmware/esphome/README.md and
  firmware/esphome/Glasscalibur-auto-calibrate.md removed (folded in). No firmware,
  workflow or tool file changes.
- CHANGELOG.md: one 2.2.0 line for the repo changes; the unreleased 2.2.0 entry titled
  "fail-safe" retitled "speed lock"; the old Child Lock line reworded to say what the
  switch does. Other existing lines are left as released.
- Not documented (not in the code or not verifiable): a bench self-test (none is
  merged), power input, lifting the unit off its mounts, kit contents, window sizes,
  which carriage's opening to quote, images.

## Checks (head vs base ac01bd3)

D1 Every relative link in README.md and firmware/README.md resolves to a file or
   directory in the repo, and no file in the repo references the two removed docs.
   Sabotage: a planted link to a missing file is reported.
D2 Docs-wording scan (`docscan.py`: the P8 push terms plus child-safety, fall,
   compliance, certification, standard and motor-vendor terms; "Child Lock" allowed
   only as the entity name; the placeholder host `glasscalibur-XXXXXX.local` allowed)
   over README.md, firmware/README.md and the lines this PR adds to CHANGELOG.md:
   0 hits. Its self-test passes (10 cases).
   Sabotage: a planted claim line is caught.
D3 The entity reference in firmware/README.md lists exactly the 64 entity names of
   the resolved config (same set, no extras).
   Sabotage: the same check with one row removed reports the missing name.
D4 Firmware facts quoted in the docs are checked against the code (a table in the
   PR: each number, its file and line).
C1 No file under firmware/ other than the two removed docs, nor .github/ or tools/
   (outside this predictions file), changes; CI green.
   Sabotage: n/a for the file list (it is a `git diff --stat` reading); CI's own
   sabotage is the compile, unchanged since PR #14.
