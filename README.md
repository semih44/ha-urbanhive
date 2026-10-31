# urbanhive homefarm for Home Assistant

Unofficial Home Assistant integration for the **urbanhive homefarm** indoor farm.
It reads the farm **locally on your network** and only uses the urbanhive cloud for
signing in (and, optionally, as a fallback).

> **Not affiliated with urbanhive GmbH.** This integration talks to an undocumented
> interface of the farm and the urbanhive backend. It can stop working whenever
> urbanhive changes that interface. Use at your own risk.

## Features

**Farm device**

- Live values read directly from the farm: humidity, temperature, Wi-Fi signal
- Cleaning date
- Light schedule: mode (custom / grow), light on and off time, brightness
- Dimming: on/off, from/until and brightness (edits the first dimming window)
- Tasks as a to-do list (complete; delete = hide for a week) — *experimental*

**One sub-device per level** (works for farms with one or more levels)

- Plant light on/off with brightness
- Water tank empty (problem sensor) and water check on/off
- One select per slot: shows the planted plant, lets you plant, swap or harvest
  (choose "empty"); attributes: planted at, days, harvest window, progress
- Action `urbanhive.set_plant_date` to correct the planting date

**General**

- Local first, cloud optional — the cloud is used for sign-in, the plant catalog
  and tasks
- The farm's address is picked up automatically, also after it changes

Completing and hiding tasks follows what the app sends but has not been verified
against the backend yet (no task existed while building it).

## How it works

| Part | Where |
|---|---|
| Sign-in | Firebase Auth with your urbanhive email and password |
| Farm data and light control | HTTP API of the farm on your local network (port 80) |
| Fallback when the farm is not reachable | urbanhive cloud backend (values may be outdated) |

The farm's address is detected automatically from your account during setup.
Make sure the farm keeps the same IP address (DHCP reservation in your router).

## Installation

### HACS (custom repository)

1. HACS → three dots → **Custom repositories**
2. Add this repository as type **Integration**
3. Install **urbanhive homefarm** and restart Home Assistant

### Manual

Copy `custom_components/urbanhive` into your Home Assistant `config/custom_components`
folder and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → urbanhive homefarm**, then sign in
with the email and password of your urbanhive account.

Options (after setup): change the local address, or force cloud access if the farm is
not reachable on your network.

Accounts that sign in with Google or Apple only are not supported yet.

## Credits

Built for personal use. No urbanhive app code, texts or images are included in this
repository; everything is fetched at runtime with the user's own account.

## License

MIT
