# Changelog

## v0.3.1

First release on GitHub. Install it through HACS as a custom repository; HACS will
offer new releases as updates from now on.

### Features

- **Local first:** live values and control come directly from the farm on your
  network. The cloud is only used for signing in, the plant catalog and tasks, and
  to find the farm again when its IP address changes.
- **Farm:** humidity, temperature, Wi-Fi signal, last and next cleaning, and a
  "cleaning done" button
- **Light schedule:** mode (custom / grow), on and off time, brightness
- **Dimming:** up to five dimming windows like the app, each with start, end and
  brightness
- **Levels** as sub-devices: light on/off with brightness, water level, water check
- **Plant slots:** choose what is planted in each of the five slots per level from
  the urbanhive catalog, with planting date, days planted and harvest window; the
  `urbanhive.set_plant_date` action corrects the planting date
- **Tasks** from the app as a to-do list (experimental)
- Re-authentication when the sign-in expires; only a refresh token is stored, not
  your password
- Diagnostics download with email, tokens, IP and MAC address removed
- German and English translations

### Not supported

- Accounts that sign in with Google or Apple
- Shop, recipes and support from the app
