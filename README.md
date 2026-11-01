# urbanhive homefarm for Home Assistant

[![release](https://img.shields.io/github/v/release/semih44/ha-urbanhive?label=release)](https://github.com/semih44/ha-urbanhive/releases)
[![downloads](https://img.shields.io/github/downloads/semih44/ha-urbanhive/total?label=downloads&color=brightgreen)](https://github.com/semih44/ha-urbanhive/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5)](https://hacs.xyz/docs/faq/custom_repositories)
[![License](https://img.shields.io/badge/License-MIT-yellow)](https://github.com/semih44/ha-urbanhive/blob/main/LICENSE)

Unofficial Home Assistant integration for the **urbanhive homefarm** indoor farm.
It reads the farm **locally on your network** and only uses the urbanhive cloud for
signing in, catalog and tasks (and, optionally, instead of the local connection).

> **Not affiliated with urbanhive GmbH.** This integration talks to an undocumented
> interface of the farm and the urbanhive backend. It can stop working whenever
> urbanhive changes that interface. Use at your own risk.

## Features

**Farm device**

- Live values read directly from the farm: humidity, temperature, Wi-Fi signal
- Last and next cleaning (the app treats a cleaning as valid for 28 days) and a
  "cleaning done" button
- Light schedule: mode (custom / grow), light on and off time, brightness
- Up to five dimming windows (like the app), each with from/until and brightness
- Tasks as a to-do list (complete; delete = hide for a week) - *experimental*
- Diagnostics download with credentials and addresses redacted

**One sub-device per level** (works for farms with one or more levels)

- Plant light on/off with brightness
- Water tank empty (problem sensor) and water check on/off
- One select per slot: shows the planted plant, lets you plant, swap or harvest
  (choose "empty"); attributes: planted at, days, harvest window, progress
- Action `urbanhive.set_plant_date` to correct the planting date

**General**

- Local first: live values and control come from the farm itself. The cloud is used
  for sign-in, the plant catalog, plant slots and tasks. If the farm is not reachable,
  its entities become unavailable instead of showing outdated cloud values.
- Only a refresh token is stored, not your password; Home Assistant asks you to sign
  in again if it stops working.
- The farm's address is picked up automatically, also after it changes.

Completing and hiding tasks follows what the app sends but has not been verified
against the backend yet (no task existed while building it).

## How it works

| Part | Where |
|---|---|
| Sign-in | Firebase Auth with your urbanhive email and password |
| Farm data and light control | HTTP API of the farm on your local network (port 80) |
| Farm not reachable locally | cloud is only asked for the farm's new IP address; otherwise the entities become unavailable |

The farm's address is detected automatically from your account during setup.
Make sure the farm keeps the same IP address (DHCP reservation in your router).

## Installation

### HACS (custom repository)

1. HACS → three dots → **Custom repositories**
2. Add `https://github.com/semih44/ha-urbanhive` as type **Integration**
3. Install **urbanhive homefarm** and restart Home Assistant

HACS installs tagged releases and shows new ones as updates in Home Assistant.

### Manual

Download `urbanhive.zip` from the [latest release](https://github.com/semih44/ha-urbanhive/releases/latest),
extract it into `config/custom_components/urbanhive` and restart Home Assistant.

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
