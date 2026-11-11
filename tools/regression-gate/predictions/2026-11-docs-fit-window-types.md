# Docs: window types and the corrected fit

Ruling 44, 2026-11-11. Registered before any edit. Base: origin/main d707dc5. Branch
docs/fit-window-types. Docs only (README.md, plus the wiki's Home and Installation Guide pushed
separately); nothing under `firmware/` changes. Merges once CI is green.

## Changes
1. Window types: Glasscalibur also works on single-hung and double-hung windows, with one unit
   mounted at the center of the sash. Added to the README's opening line and its install
   overview, and to the wiki's Home and Installation Guide (which said horizontal sliding only).
   The two photo captions stay: the photos show a horizontal sliding window.
2. Fit, from the corrected v1.8 model (head 351.06 mm mount face to mount face, plus 1.1 mm VHB per
   side): 20.5-36.9 in (519-939 mm) between the frame and sash surfaces where the mounts go,
   measured along the direction the window slides, window closed. Replaces 21.1-37.6 in
   (535-956 mm), which used the September head length (369.8 mm).
3. Parts by span (README install overview and the wiki Installation Guide): 519-628 mm one tube +
   rod A (150 mm); 629-658 one tube + rod B (180 mm); 659-769 two tubes + A; 770-799 two tubes + B;
   800-909 three tubes + A; 910-939 three tubes + B.

## Checks
N1 The fit line in the README and the wiki reads 20.5-36.9 in (519-939 mm) with the measurement
   definition; the chart's spans are contiguous from 519 to 939 mm; each inch value is its mm value
   rounded inward to 0.1 in (519 -> 20.5, 939 -> 36.9). Sabotage: a chart with a gap, or an inch
   value rounded outward (20.4), is flagged.
O1 No old fit number (21.1, 37.6, 535, 956, 369.8) remains in README.md, hardware/README.md or the
   wiki (the predictions files are records and keep theirs). Sabotage: a planted old number is found.
D1 Links resolve; the entity reference is unchanged (66 rows).
W  The push gate passes on the diff, the commits, the messages and the PR text; the wiki push passes
   the same scans.
