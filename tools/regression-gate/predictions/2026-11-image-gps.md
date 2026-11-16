# CI: refuse any tracked image that carries GPS (registered 2026-11-15, before the code)

The owner (2026-11-15): add the image-GPS CI check to this repo, the same check as Valar-Systems/Ropener #46/#47
(itself ported from valar-scopes #716), through review and CI, proven to refuse a planted GPS image first.

## Change
- `tools/check_image_gps.py`: Ropener's `scripts/check_image_gps.py` at 8d29c31, byte for byte except the docstring's
  provenance lines.
  - It reads every tracked file (git ls-files). An image is known by its magic or by a jpg/jpeg/png/webp name.
  - Findings: exif-gps, exif-unread, xmp-location (only a location property that holds a value), container
    (unreadable).
  - No allowlist. It prints paths and kinds only, never a coordinate.
- `.github/workflows/image-gps.yml`: Ropener's workflow, with the path changed to `tools/`. It runs on every pull
  request and on pushes to main: `--selftest`, `--sabotage`, then the check on every tracked file.
- Nothing else changes. No firmware, no build.

## Predictions
- **G1 selftest:** `--selftest` prints 24 rows, all ok, then "selftest PASSED: 24 rows"; exit 0. Locally (Windows,
  Python 3.14) and in CI (ubuntu-24.04).
- **G2 sabotage:** `--sabotage` shows the unplanted control ok (exit 0, 24 rows, none red). Each of the 11 sabotages
  turns exactly its rows red (exit 1), then "SABOTAGE PASSED"; exit 0. Locally and in CI.
- **G3 this repo:** the check on every tracked file of the branch head reads every file; findings 0; "image gps: OK";
  exit 0. The 4 tracked images (docs/images/*.jpg) carry no EXIF and no XMP (read-only check, 2026-11-14), and no
  container file is tracked.
- **G4 planted image, locally:** a throwaway clone of the branch head, plus one committed JPEG holding a synthetic GPS
  IFD (made by the script's own selftest builders, so not a real position).
  - The same command the workflow runs exits 1, with exactly one finding: "FINDING exif-gps: <that path>".
  - Control: the same clone without the plant exits 0.
  - The planted file is never pushed anywhere.
- **G5 CI:** the pull request's image-gps job passes all three steps, and the firmware build job still passes.
- **D:** the push gate passes on the diff, the commit messages and the PR text.

### Note 1 (before the code)
- The docstring's three usage lines name `scripts/check_image_gps.py`. Here they say `tools/check_image_gps.py`. So the
  copy differs from Ropener's in the docstring's provenance lines and those three path lines, nothing else.

## Results (2026-11-16, head fab05bf, Windows, Python 3.14.6)
- **G1:** 24 rows, all ok; "selftest PASSED: 24 rows"; exit 0. As predicted.
- **G2:** the control ok (exit 0, 24 rows, none red). All 11 sabotages turned exactly their rows red; "SABOTAGE
  PASSED"; exit 0. As predicted.
- **G3:** "image gps: 94 tracked file(s), 94 read; findings 0", then "image gps: OK"; exit 0. As predicted.
- **G4:** a local clone of fab05bf with no remote.
  - Control: 94 files, findings 0, exit 0.
  - Plant: a 100-byte JPEG built by the script's own selftest builders, committed as docs/images/planted-gps.jpg in
    the clone only. 95 files, findings 1, "FINDING exif-gps: docs/images/planted-gps.jpg", exit 1. As predicted.
- **The push gate's scan:** the code commit first hit the product-claims scan 5 times, on a variable name in the HEIF
  parser. The owner cleared it with 5 scoped exemptions for those exact lines; the copy is unchanged. Then 0 hits.
- G5 (CI) follows on the pull request.
- **G5 (CI on 4f2456c):** the image-gps job passed in 13 s, with "selftest PASSED: 24 rows", "SABOTAGE PASSED" and
  "image gps: 94 tracked file(s), 94 read; findings 0", "image gps: OK". The firmware build passed. As predicted.
