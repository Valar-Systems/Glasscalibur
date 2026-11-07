#!/usr/bin/env python3
"""Find the bench unit's current address by its MAC — BENCH ONLY.

    python tools/bench/find_unit.py --mac <MAC from the USB flash>

The address can change, and no other Glasscalibur on the network may ever get bench
commands, so the unit is found by its MAC, never by its name or a remembered address:
1. the PC's neighbour table (`arp -a`) gives the addresses that have that MAC;
2. only if none does, the ESPHome devices announced on the network are listed;
3. an address is accepted only if the device itself reports the MAC (native API device
   info, read only; no command is sent to any device).
It prints the address on this screen only; nothing is written to a file.
"""
import argparse, asyncio, re, subprocess, sys

ARP_LINE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5})\b")


def norm_mac(m):
    return "".join(c for c in str(m or "").lower() if c in "0123456789abcdef")


def arp_candidates(arp_text, mac):
    """Addresses whose neighbour-table entry has this MAC."""
    want = norm_mac(mac)
    return [m.group(1) for m in map(ARP_LINE.match, arp_text.splitlines()) if m and norm_mac(m.group(2)) == want]


def read_arp():
    return subprocess.run(["arp", "-a"], capture_output=True, text=True).stdout


async def device_mac(addr):
    """The MAC the device at addr reports (native API device info), or None."""
    from aioesphomeapi import APIClient
    cli = APIClient(addr, 6053, None, client_info="glasscalibur-find")
    try:
        await asyncio.wait_for(cli.connect(login=True), 10)
        return (await cli.device_info()).mac_address
    except Exception:
        return None
    finally:
        try:
            await cli.disconnect()
        except Exception:
            pass


async def esphome_addresses(seconds=6.0):
    """Addresses of ESPHome devices announced on the network (any name)."""
    from aioesphomeapi.host_resolver import SERVICE_TYPE      # ESPHome's mDNS service type
    from zeroconf import ServiceStateChange
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
    found, names = set(), set()
    azc = AsyncZeroconf()

    def on_change(zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            names.add(name)

    browser = AsyncServiceBrowser(azc.zeroconf, SERVICE_TYPE, handlers=[on_change])
    await asyncio.sleep(seconds)
    for n in names:
        info = AsyncServiceInfo(SERVICE_TYPE, n)
        if await info.async_request(azc.zeroconf, 3000):
            found.update(info.parsed_addresses())
    await browser.async_cancel()
    await azc.async_close()
    return sorted(found)


async def find(mac, arp_text=None, mac_of=device_mac, announced=esphome_addresses):
    want = norm_mac(mac)
    if len(want) != 12:
        raise SystemExit("give the full MAC (12 hex digits)")
    cands = arp_candidates(arp_text if arp_text is not None else read_arp(), mac)
    if not cands:
        cands = await announced()
    return [a for a in cands if norm_mac(await mac_of(a)) == want]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mac", required=True)
    hits = asyncio.run(find(ap.parse_args().mac))
    if len(hits) != 1:
        print(f"Not found uniquely ({len(hits)} match(es)). Is the unit powered and on the network?")
        return 1
    print(f"The unit with this MAC is at: {hits[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
