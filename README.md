<h1 align="center">
  <img src="https://github.com/jcubic/horavox/blob/master/.github/logo.svg?raw=true"
       alt="HoraVox logotype: a simplistic analog clock and text HORAVOX" />
</h1>

[![pip](https://img.shields.io/badge/pip-0.2.0-blue.svg)](https://pypi.org/project/horavox/)
[![CI](https://github.com/jcubic/horavox/actions/workflows/ci.yml/badge.svg)](https://github.com/jcubic/horavox/actions/workflows/ci.yml)
[![horavox GitHub repo](https://img.shields.io/badge/github-horavox-orange?logo=github)](https://github.com/jcubic/horavox)
[![Coverage Status](https://coveralls.io/repos/github/jcubic/horavox/badge.svg?branch=master)](https://coveralls.io/github/jcubic/horavox?branch=master)
[![LICENSE GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://github.com/jcubic/horavox/blob/master/LICENSE)

A multi-language speaking clock that announces the time using [Piper](https://github.com/rhasspy/piper) text-to-speech. It runs entirely offline using local AI voice models -- no API key or internet connection required (except for the initial voice download). It speaks the current hour on the hour using natural language idioms (e.g., "quarter past two", "wpół do czwartej") and supports any language through JSON data files.

## Features

- **Natural time idioms** -- not just "it is 14:30" but "half past two" (English) or "wpół do trzeciej" (Polish)
- **Classic & modern modes** -- idiomatic ("quarter past five") or digital ("five fifteen")
- **Multi-language** -- add a new language by creating a JSON file in `data/lang/`
- **Fully offline** -- uses local AI voice models, no API key or cloud service needed
- **Voice management** -- browse, download, and auto-detect Piper voices from Hugging Face
- **Bluetooth audio fix** -- plays a silent MP3 before speech to prevent clipping on Bluetooth speakers
- **Flexible scheduling** -- restrict announcements to a time range (e.g., 7:00--22:00)
- **Configurable interval** -- announce every N minutes with `--freq` (e.g., every 30 min)
- **Volume control** -- set volume 0--100% with `--volume`
- **Background mode** -- run as a daemon with `--background`, stop with `--stop`
- **Autostart service** -- add as a system service with `vox service add`, runs on login
- **Hour beeps** -- 2 beeps on the full hour, 1 beep on the half hour
- **Simulated time** -- debug with `--time HH:MM` to set a fake starting time
- **Silent by default** -- no terminal output unless `--verbose` is passed

## Requirements

- **Python 3.10+** and **pip**
- `aplay` (ALSA utils, for WAV playback) -- `sudo apt install alsa-utils`
- `mpg123` (for MP3 playback) -- `sudo apt install mpg123`

## Installation

### From PyPI

```bash
pip install horavox
```

This installs the `vox` command.

### From source

```bash
git clone https://github.com/jcubic/horavox.git
cd horavox
pip install .
```

This installs the `vox` command from the local source, including all dependencies.

## Usage

HoraVox uses git-style subcommands:

```bash
vox <command> [options]
```

| Command | Description |
|---------|-------------|
| `vox clock` | Run the speaking clock |
| `vox now` | Speak the current time once |
| `vox list` | List running background instances |
| `vox stop` | Stop running background instances |
| `vox voice` | Manage Piper voice models |
| `vox at` | Speak the time at specified times (one-shot or recurring) |
| `vox config` | Get or set default configuration |
| `vox service` | Manage autostart service (add/delete/list/start) |
| `vox completion` | Generate shell completion scripts |

Run `vox <command> --help` for command-specific options.

### vox clock

Run the speaking clock in foreground or as a background daemon:

```bash
vox clock                                          # announce every hour
vox clock --freq 30                                # every 30 minutes
vox clock --start 7 --end 22                       # only between 7:00-22:00
vox clock --mode modern                            # digital style ("siedemnasta piętnaście")
vox clock --background                             # run as a daemon
vox clock --lang pl --voice pl_PL-darkman-medium   # specific language and voice
vox clock --volume 50                              # 50% volume
```

Time range accepts `H`, `HH`, `H:MM`, or `HH:MM`. Supports midnight wrap (e.g., `--start 22 --end 6`).

Valid `--freq` values must divide 60 evenly: 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60.

Classic mode (default) uses idiomatic expressions -- "quarter past five", "wpół do szóstej". Modern mode reads the time digitally -- "five fifteen", "siedemnasta piętnaście".

### vox now

Speak the current time once and exit:

```bash
vox now                        # speak current time
vox now --time 16:00           # speak a specific time
vox now --mode modern          # digital style
vox now --volume 30            # quiet
```

### vox stop / vox list

Stop and list running background instances:

```bash
vox list                       # print PIDs of running instances
vox list --verbose             # include command lines
vox stop                       # interactive selection if multiple instances
vox stop --pid 12345           # stop a specific instance
```

When multiple instances are running, `vox stop` shows an interactive menu with arrow-key selection.

### vox voice

Interactive voice browser -- navigate with arrow keys, press `i` to install, `u` to uninstall, `q` to quit:

```bash
vox voice                      # interactive voice browser
vox voice --lang en            # for a specific language
vox voice --list               # non-interactive list (for scripting)
vox voice --list --lang pl     # non-interactive for a specific language
```

Installed voices are marked with `[*]`. Downloads show a progress bar below the list.

### Volume and sound

`--nosound` is equivalent to `--volume 0` -- both skip voice loading and audio playback entirely. Available on `vox clock` and `vox now`.

### vox at

Speak the time at specific times — one-shot or recurring like Google Calendar:

```bash
# One-shot (waits, speaks, exits)
vox at 12:55                                  # speak at 12:55 today
vox at 12:55 2026-05-10                       # speak at 12:55 on a specific date
vox at 9:00,12:00,18:00                       # multiple times today

# Recurring (persistent loop)
vox at 12:55 --repeat everyday                # every day at 12:55
vox at 12:55 --repeat sunday,wednesday        # specific days of the week
vox at 9:00,18:00 --repeat weekdays           # weekdays only
vox at 8:00 --repeat weekends --lang pl       # Polish, weekends only

# Common flags
vox at 9:00 --repeat everyday --background    # run as a daemon
vox at 9:00 --repeat everyday --volume 30     # quiet
```

Times are comma-separated in `HH:MM` format. Day keywords: `monday`–`sunday`, `everyday`, `weekdays`, `weekends`. Without `--repeat`, the process exits after the last scheduled time passes. Supports the same `--lang`, `--voice`, `--mode`, `--volume`, `--background`, and `--debug` flags as `vox clock`.

Works with `vox service add` too:

```bash
vox service add "at 12:55 --repeat sunday,wednesday --volume 50"
```

### vox config

Set default values and aliases so you don't have to repeat common flags:

```bash
vox config lang=pl                     # default language
vox config voice=pl_PL-mc_speech-medium # default voice
vox config mode=classic                # default time style
vox config volume=30                   # default volume (0-100)
vox config                             # list all settings and aliases
vox config lang                        # show a single setting
vox config --unset voice               # remove a setting
```

Settings are stored in `~/.horavox/config.json` and apply to `vox clock`, `vox now`, `vox at`, and `vox voice`. Command-line flags always override config values.

#### Aliases

Aliases work like git aliases -- define default arguments for any subcommand:

```bash
vox config alias.clock '--start 9 --end 1 --background --freq 30 --volume 30'
vox config alias.now '--mode modern'
```

Now `vox clock` expands to `vox clock --start 9 --end 1 --background --freq 30 --volume 30`. Explicit arguments override alias defaults:

```bash
vox clock --volume 50    # overrides --volume 30 from the alias
```

Manage aliases the same way as settings:

```bash
vox config alias.clock                 # show an alias
vox config --unset alias.clock         # remove an alias
```

### vox service

Manage autostart service instances that run on login:

```bash
vox service add "clock --lang pl --voice pl_PL-mc_speech-medium --start 9 --end 1 --freq 30 --volume 30"
vox service list                       # list installed instances
vox service delete <id>                # delete a specific instance
vox service delete --all               # delete all instances
vox service delete                     # interactive selection if multiple
vox service start                      # start the service manually
```

The quoted argument is any valid `vox` subcommand with its flags. The `--background` flag is stripped automatically since the service manager handles that.

On the first install, a platform-specific service is registered and started:

| Platform | Mechanism |
|----------|-----------|
| Linux | systemd user service (`~/.config/systemd/user/horavox.service`) |
| macOS | launchd user agent (`~/Library/LaunchAgents/com.horavox.service.plist`) |
| Windows | Startup folder script (`%APPDATA%\...\Startup\horavox.vbs`) |

Subsequent installs add instances to the registry and signal the running service to reload. When the last instance is removed, the service is automatically unregistered.

### Shell completion

HoraVox supports tab completion for bash, zsh, and fish via [argcomplete](https://github.com/kislyuk/argcomplete). Generate and activate the completion script for your shell:

```bash
# Bash — add to ~/.bashrc
eval "$(vox completion --bash)"

# Zsh — add to ~/.zshrc
eval "$(vox completion --zsh)"

# Fish — add to ~/.config/fish/config.fish
vox completion --fish | source
```

Once activated, pressing Tab will complete command names, option flags, and values (e.g., `--mode classic|modern`).

### Custom commands

Like git, any executable named `vox-<name>` in your `$PATH` can be invoked as `vox <name>`. This lets you extend HoraVox with your own commands or scripts:

```bash
# Create a custom command
cat > ~/bin/vox-greet << 'EOF'
#!/bin/bash
vox now --lang en --voice en_US-lessac-medium
EOF
chmod +x ~/bin/vox-greet

# Use it
vox greet
```

## Adding a new language

Create a JSON file in `data/lang/<code>.json` (e.g., `de.json` for German). The file contains two mode sections:

```json
{
  "classic": {
    "hours": ["midnight", "one o'clock", "...", "eleven o'clock"],
    "hours_alt": ["midnight", "one", "...", "eleven"],
    "minutes": {
      "1": "one", "2": "two", "...": "...", "29": "twenty nine"
    },
    "patterns": {
      "full_hour": "{hour}",
      "quarter_past": "quarter past {hour_alt}",
      "half_past": "half past {hour_alt}",
      "quarter_to": "quarter to {next_hour_alt}",
      "minutes_past": "{minutes} past {hour_alt}",
      "minutes_to": "{minutes} to {next_hour_alt}"
    }
  },
  "modern": {
    "hours": ["midnight", "one o'clock", "..."],
    "hours_alt": ["twelve", "one", "..."],
    "minutes": {
      "1": "oh one", "...": "...", "59": "fifty nine"
    },
    "patterns": {
      "full_hour": "{hour}",
      "time": "{hour_alt} {minutes}"
    }
  }
}
```

### Fields

**Classic mode** (idiomatic -- quarters, halves, past/to):

| Field | Required | Description |
|---|---|---|
| `hours` | Yes | 24 entries (index 0 = midnight, 12 = noon, etc.) used in `{hour}` and `{next_hour}` |
| `hours_alt` | No | 24 entries for alternate forms (e.g., genitive case). Defaults to `hours` if omitted |
| `minutes` | Yes | Keys `"1"` through `"29"` -- spoken forms for minute counts |
| `patterns` | Yes | 6 patterns: `full_hour`, `quarter_past`, `half_past`, `quarter_to`, `minutes_past`, `minutes_to` |

**Modern mode** (digital -- hour + minutes):

| Field | Required | Description |
|---|---|---|
| `hours` | Yes | 24 entries for full-hour announcements (can include "midnight", "noon") |
| `hours_alt` | No | 24 entries for the hour in `{hour_alt} {minutes}` patterns. Defaults to `hours` |
| `minutes` | Yes | Keys `"1"` through `"59"` -- spoken forms for all minute values |
| `patterns` | Yes | 2 patterns: `full_hour` and `time` |

### Placeholders

| Placeholder | Meaning |
|---|---|
| `{hour}` | Current hour from `hours` |
| `{hour_alt}` | Current hour from `hours_alt` |
| `{next_hour}` | Next hour from `hours` |
| `{next_hour_alt}` | Next hour from `hours_alt` |
| `{minutes}` | Minute count from `minutes` map |
| `{remaining}` | Minutes remaining to next hour (same source as `{minutes}`) |

### Pattern rules

| Pattern | When | Example (English) |
|---|---|---|
| `full_hour` | :00 | "three o'clock" |
| `quarter_past` | :15 | "quarter past three" |
| `half_past` | :30 | "half past three" |
| `quarter_to` | :45 | "quarter to four" |
| `minutes_past` | :01--:29 (not :15) | "ten past three" |
| `minutes_to` | :31--:59 (not :45) | "ten to four" |

## Project structure

```
src/horavox/
  __init__.py         Package init
  main.py             CLI dispatcher (installed as `vox` via pip)
  core.py             Shared library — paths, logging, language, TTS, voice, sessions
  clock.py            vox clock — speaking clock loop + daemon
  now.py              vox now — speak once
  at.py               vox at — scheduled announcements (one-shot / recurring)
  stop.py             vox stop — stop daemons
  list.py             vox list — list running daemons
  voice.py            vox voice — interactive voice browser
  config.py           vox config — get/set defaults and aliases
  service.py          vox service — autostart service management
  registry.py         CRUD for service instance registry
  completion.py       vox completion — shell completion scripts
  platforms/
    linux.py          systemd user service backend
    macos.py          launchd user agent backend
    windows.py        Windows startup folder backend
  data/
    lang/
      en.json         English time data
      pl.json         Polish time data
    blank.mp3         Silent MP3 for Bluetooth audio wake-up
    beep.mp3          Beep sound for hour/half-hour signals
pyproject.toml        Package configuration

~/.horavox/           Runtime data (created automatically)
  voices/             Downloaded Piper voice models (.onnx)
  cache/              Voice catalog cache + PID file
  config.json         Default settings and aliases
  data.json           Installed service instances registry
  horavox.log         Spoken words + error log
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and publishing instructions.

## Name

The name of the project is takend from two words from Latin: *Hora* (hour) + *Vox* (voice) -- the voice of the hour.

## Acknowledge

The logo use [Clipart from OpenClipart](https://openclipart.org/detail/351967/clock) and font [Lovelo](https://www.dafontfree.io/lovelo-font-free/).

## License

Copyright (C) 2026 [Jakub T. Jankiewicz](https://jakub.jankiewicz.org)

Released under [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html) or later
