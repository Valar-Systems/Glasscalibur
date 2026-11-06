# Glasscalibur README photos and confirmed facts — predictions

Written and committed before any doc change on branch `docs/readme-photos-facts`.
Read before this file: the four store photos (JPEG, 1000 x 667, 65-103 KB; EXIF held
only resolution fields and a processing host name, no location or author; that EXIF
block is removed without re-encoding, pixels identical, colour profile kept).

- Base: origin/main `9bc25e9` (hardware v1.8 merged).

## Changes

- `docs/images/`: glasscalibur.jpg (under the intro), glasscalibur-with-mounts.jpg
  ("How it works"), installed-closeup.jpg and installed-window.jpg side by side above
  "Install overview". Plain alt text saying what each shows.
- README: "horizontal sliding windows"; the sentence about stopping before 4 in is
  removed; "learned on each unit" stays; no travel figure until the bench confirms
  the v1.8 carriage. Daniel's confirmed facts (in the session, 2026-11-06): power
  (the supplied 24 V DC adapter only; USB powers the board for flashing but cannot
  run the motor), opening by hand (lift the unit off its mounts, no tools; with
  Tamper Detection on, that sounds the tamper alarm — the code only checks while it
  is on), the kit contents and the fit range (21.1-37.6 in / 535-956 mm between the
  jamb and sash mount faces, window closed, one to three tubes). No store link.
- firmware/README.md: the power note under flashing; the opening-by-hand note under
  tamper.

## Checks

P1 Each docs/images file is byte-identical to its EXIF-stripped copy, decodes at
   1000 x 667, and carries no EXIF.
   Sabotage: the unstripped download fails the no-EXIF check.
P2 Every image and relative link in README.md and firmware/README.md resolves, and
   every image has non-empty alt text.
   Sabotage: a planted missing image is reported.
P3 Docs wording scan (public terms, product claims, motor vendor) over both docs'
   new lines and the PR text: 0 hits; the local pre-push hook passes on the push.
   Sabotage: a planted claim line is caught.
P4 The README contains neither "4 in" nor any opening-distance figure.
   Sabotage: the base README contains the removed sentence.
