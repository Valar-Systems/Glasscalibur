# Glasscalibur v1.8 carriage re-export — predictions

Written and committed before the files are replaced, on branch
`hardware/carriage-trim`. No check below had been run when this file was committed.

- Base: origin/main `a3da69c` (hardware v1.8 merged in #16).
- Source: the v1.8 CAD folder (2026-11-05), where `printed/carriage.step` and
  `printed/carriage.stl` were re-exported 2026-11-06 11:47.

## The request (Daniel, 2026-11-06)

The carriage changed today: 0.8 mm trims at both bumper faces, for more
limit-switch margin. Nothing else in the design changed. Replace
`hardware/printed/carriage.step` and `hardware/printed/carriage.stl` with the
re-export; every other file is unchanged, and the hardware README stays as written.

## Change

Only those two files. No README, license, firmware, workflow or tool file changes.

## Checks

K0 Source read before adding: the new STEP file is one solid, in millimetres, with
   empty author and organisation fields; the new STL file is binary, its size matching
   its triangle count; neither contains the motor terms (local check, text and
   printable runs).
   Sabotage: the check reports a planted second solid and a truncated STL.
K1 Every other file in the source folder (27) is byte-identical to its copy in
   `hardware/`; the two carriage files differ from theirs.
   Sabotage: a copy with one byte flipped is reported as different.
K2 After the copy: all 29 files in `hardware/printed`, `hardware/machined` and
   `hardware/extrusion` have the same SHA-256 as the source, nothing else is in those
   folders, and the PR diff touches exactly the two carriage files plus this file.
   Sabotage: the base fails K2 for the two carriage files.
K3 Geometry (STL): the new carriage's bounding box is the same as the old one's or
   smaller along one axis only, by at most 1.6 mm (0.8 mm per face); its volume is
   smaller than the old one's, by less than 5 %.
   Sabotage: the old file compared with itself shows no change.
K4 Wording: the P8 push scan, the docs claims scan and the local motor-term check
   pass on the diff, the commit messages and the PR text.
   Sabotage: each is caught by a planted line, as before.
