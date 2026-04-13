# HoraVox

[![pip](https://img.shields.io/badge/pip-0.1.0-blue.svg)](https://pypi.org/project/horavox/)
[![LICENSE MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/jcubic/horavox/blob/master/LICENSE)

*Hora* (Latin: hour) + *Vox* (Latin: voice) -- the voice of the hour.

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

### Speak the current time and exit

```bash
vox --now
```

### Run as a clock (announces on the hour)

```bash
vox
```

### Switch between classic and modern time style

```bash
vox --mode classic   # "quarter past five", "za kwadrans szósta" (default)
vox --mode modern    # "five fifteen", "siedemnasta piętnaście"
```

Classic mode uses idiomatic expressions (quarters, halves, past/to) with 12-hour names. Modern mode reads the time digitally (hour + minutes) using 24-hour names in Polish.

### List available voices for a language

```bash
vox --list-voices --lang pl
vox --list-voices --lang en
```

### Install and use a specific voice

```bash
vox --voice en_US-lessac-medium
```

Voices are auto-downloaded from Hugging Face if not already installed.

### Limit speaking hours

```bash
vox --start 7 --end 22
vox --start 7:30 --end 22:30
```

Accepts `H`, `HH`, `H:MM`, or `HH:MM`. Supports midnight wrap (e.g., `--start 22 --end 6`).

### Announce every 30 minutes

```bash
vox --freq 30
```

Valid values for `--freq` must divide 60 evenly: 1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60.

### Debug with simulated time

```bash
vox --time 16:00 --exit
```

### Run in the background

```bash
vox --lang pl --voice pl_PL-darkman-medium --start 8 --end 0 --background
```

Stop the background daemon:

```bash
vox --stop
```

### Set volume

```bash
vox --volume 50          # 50% volume
vox --volume 0           # silent, same as --nosound
```

`--nosound` is equivalent to `--volume 0` -- both skip voice loading and audio playback entirely.

### Enable log output

```bash
vox --verbose
```

### All options

```
usage: vox [-h] [--lang LANG] [--mode {classic,modern}] [--voice NAME]
           [--list-voices] [--start HH:MM] [--end HH:MM] [--freq MIN]
           [--time HH:MM] [--exit] [--now] [--background] [--stop]
           [--verbose] [--volume PCT] [--nosound] [--debug]

HoraVox — announces the time using text-to-speech

options:
  --lang LANG    Language code, e.g. pl, en (default: from system locale)
  --mode MODE    Time style: classic (idiomatic) or modern (digital) (default: classic)
  --voice NAME   Voice name, e.g. en_US-lessac-medium (auto-downloads if missing)
  --list-voices  List available Piper voices for the current language and exit
  --start HH:MM  Start time for speaking range (default: 0:00)
  --end HH:MM    End time for speaking range (default: 23:59)
  --freq MIN     Announcement interval in minutes (default: 60)
  --time HH:MM   Set simulated start time for debugging (e.g., 16:00)
  --exit         Run once and exit (for debugging)
  --now          Speak the current time (with minutes) and exit
  --background   Run as a background daemon
  --stop         Stop the background daemon and exit
  --verbose      Show log messages (silent by default)
  --volume PCT   Volume level 0-100 percent (default: 100, 0 = no sound)
  --nosound      Same as --volume 0 — skip voice loading and audio playback
  --debug        Alias for --nosound --verbose
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
  cli.py              Main script (installed as `vox` via pip)
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
  horavox.log         Spoken words + error log
```

## Development

```bash
git clone https://github.com/jcubic/horavox.git
cd horavox
pip install -r requirements.txt
```

This installs only the dependencies without installing the package itself. You can then run the script directly:

```bash
python src/horavox/cli.py --now
```

Alternatively, install in editable mode to get the `vox` command that reflects your source changes:

```bash
pip install -e .
```

## License

Copyright (C) 2026 [Jakub T. Jankiewicz](https://jakub.jankiewicz.org)

Released under MIT license
