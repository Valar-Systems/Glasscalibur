# Glasscalibur update-download and web-server settings — predictions

Registered before the change, on branch `fw/update-download-settings` (from the review).

- Base: origin/main `b565d96`.
- Toolchain: ESPHome 2026.6.5 in an isolated venv.

## Change

Two settings, nothing else:
- The GitHub update download checks the server against ESP-IDF's built-in CA bundle.
  Core v0.3.0 turns that check off; `packages/system.yaml` overrides it until
  valar-motion carries the same setting.
- The web server no longer answers browsers' private-network preflights
  (`enable_private_network_access: false` in `packages/web-ui.yaml`; ESPHome's own
  default from 2026.10). The unit's own page, Home Assistant and REST clients don't
  use them.

## Checks (head vs base b565d96)

P1 Resolved config: both settings as above; nothing else in the `http_request` or
   `web_server` blocks differs from the base.
   Sabotage: the base fails it.
P2 Build: compiles; the CA bundle is in the build; the image grows by less than
   100 KB and still fits its partition. CI green.
   Sabotage: the base build has no CA bundle.
P3 Entity and behaviour gates: clean.
   Sabotage: a scratch head with an entity renamed and a step changed is flagged.
P4 Wording: the push scans pass on the diff, the commit messages and the PR text.

## Bench (joins the 2.2.0 list)

- T1 With this build, **Update Firmware (GitHub)** installs the latest release end to
  end, through GitHub's redirect.

## Amendment 1 — P2 re-registered (Daniel, 2026-11-06; appended, nothing above was edited)

The miss is kept on record. P2's sabotage said the base build has no CA bundle; it does
(the bundle is ESP-IDF's default, already in the base). The image also changed by
-272 bytes, not a growth.

Re-registered P2: the build no longer contains ESP-IDF's options that skip the server
check, the CA bundle stays, and the image changes by less than 100 KB either way; CI green.
Sabotage: the base build has both skip options on.
