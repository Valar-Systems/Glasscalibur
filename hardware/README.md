# Glasscalibur hardware — v1.8 (2026-11-05)

STEP files are one solid each, in millimetres. STL files are binary, in millimetres.

## Printed parts — [`printed/`](printed)

| Part | Qty | Material and process | Notes |
| --- | --- | --- | --- |
| motor-cradle | 1 | SLS nylon, glass-bead filled | Side rails form the thermal-filler pockets beside the motor |
| motor-housing-top | 1 | SLS nylon, glass-bead filled | |
| bearing-holder | 1 | SLS nylon, glass-bead filled | 634ZZ bearing seat |
| back-plate | 1 | SLS nylon, white | |
| front-plate | 1 | SLS nylon, white | |
| end-cap | 1 | SLS nylon, white | |
| wall-mount | 2 | SLS nylon, white | |
| button-big | 1 | SLS nylon, white | |
| button-small | 1 | SLS nylon, white | |
| carriage | 1 | MJF PA12 | Tr6×1 and M12×1 threads |
| pinion-gear-12t | 1 | MJF PA12 | |
| lead-screw-gear-23t | 1 | MJF PA12 | |
| egress-flange-nut | 1 | MJF PA11 | M10×1.5 thread |

Threads are modeled. Run a tap through them after printing.

## Machined parts — [`machined/`](machined)

| Part | Qty | Material and process | Notes |
| --- | --- | --- | --- |
| ram | 1 | Aluminum tube, Ø12 mm, 140.5 mm long, anodized | M12×1 external thread, M10×1.5 internal thread |
| extension-tube | 3 | Same tube stock as the ram | M10×1.5 internal thread, full length |

## Extrusion — [`extrusion/`](extrusion)

| Part | Qty | Material and process | Notes |
| --- | --- | --- | --- |
| extrusion | 1 | Aluminum extrusion, 48.2 × 27.6 mm profile | Cut to 188 mm; holes as modeled |

## Not in these files

- **Motor:** NEMA 8 stepper. 20 × 20 mm frame, 47.5 mm body, Ø15 mm pilot, Ø4 mm
  shaft with a flat, 4 × M2 mounting holes, rated 0.6 A/phase (the firmware caps
  motor current at that rating).
- **Other purchased parts:** Tr6×1 leadscrew, 634ZZ bearing, rod wiper seal,
  M10×1.5 rods and jam nuts, screws, circuit boards, mounting tape, thermal gap
  filler.

## License

The hardware is licensed under the CERN Open Hardware Licence Version 2 — Strongly
Reciprocal (**CERN-OHL-S-2.0**). See [`LICENSE`](LICENSE).
