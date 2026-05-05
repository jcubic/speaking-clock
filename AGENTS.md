# HoraVox — Agent Context

## What this is

A multi-language speaking clock CLI using [Piper](https://github.com/rhasspy/piper) TTS. Runs offline with local AI voice models. Git-style subcommands (`vox <command>`).

## Project structure

```text
src/horavox/
  __init__.py     re-exports __version__ and main
  core.py         shared library — paths, logging, language, TTS, voice, sessions
  main.py         CLI dispatcher (vox <command>)
  clock.py        vox clock — speaking clock loop + daemon
  now.py          vox now — speak once
  list.py         vox list — list running daemons
  stop.py         vox stop — stop daemons (interactive if multiple)
  voice.py        vox voice — interactive voice browser (i/u keys, arrow nav)
  service.py      vox service — install/remove/list/start/run autostart instances
  registry.py     CRUD for ~/.horavox/data.json instance registry
  config.py       vox config — get/set defaults and aliases
  platforms/
    __init__.py   platform detection
    linux.py      systemd user service backend
    macos.py      launchd user agent backend
    windows.py    Windows startup folder backend
  data/
    lang/{en,pl}.json  time idiom data per language
    blank.mp3   silent MP3 for Bluetooth audio wake-up
    beep.mp3    beep sound for hour/half-hour signals
tests/
  test_core.py        unit tests for core (90% target)
  test_commands.py    command tests with mocked core
  test_install.py     service/registry/platform tests
  test_cli.py         E2E subprocess tests (HOME isolated to /tmp)
```

## Runtime data (`~/.horavox/`)

- `voices/` — downloaded `.onnx` Piper models
- `cache/voices.json` — Hugging Face catalog cache (24h TTL)
- `sessions/<uuid>.json` — running daemon metadata `{pid, command}`
- `sessions/<uuid>.pid` — daemon PID file (from daemonize lib)
- `horavox.log` — spoken words + error tracebacks

## Commands

| Command | Purpose |
|---------|---------|
| `vox clock` | Run the clock (foreground or `--background`) |
| `vox now` | Speak current time once (`--time HH:MM` to override) |
| `vox list` | List running daemon PIDs (`--verbose` shows command line) |
| `vox stop` | Stop daemon(s) — direct if one, interactive (inquirer) if multiple, `--pid N` for specific |
| `vox at` | Speak time at specified times, one-shot or recurring (`--repeat`) |
| `vox voice` | Interactive voice browser (arrow keys, `i`=install, `u`=uninstall, `q`=quit) |
| `vox service add` | Add a command as an autostart service instance |
| `vox service delete` | Delete installed service instances (`--all` for all) |
| `vox service list` | List installed service instances |
| `vox service start` | Start the service (register and run) |
| `vox service run` | Internal — manager process that supervises installed instances |

`vox-<name>` executables in `$PATH` work as `vox <name>` (git-style plugins).

## Time modes

- **classic** (default) — idiomatic ("quarter past five", "wpół do szóstej"). 12-hour names in Polish.
- **modern** — digital ("five fifteen", "siedemnasta piętnaście"). 24-hour in Polish.

Selected with `--mode classic|modern` on `vox clock` and `vox now`.

## Polling architecture (clock loop)

Every 1 second, recompute next slot from wall clock. Fire when within `[-5s, +3.5s]` of target (warm-up window). Why: avoids drift bugs from `time.sleep(big_number)` overshooting past the grace window. Resilient to laptop suspend, NTP jumps, scheduler stalls.

`prepare_speech` synthesizes WAV + plays `blank.mp3` (~2.3s) **before** target so speech starts on the dot. `play_speech` fires at exactly target. `beep_count_for_minute`: 2 beeps on the hour, 1 on the half hour.

## Key invariants

- **`NOSOUND`/`VOLUME`/`VERBOSE`** are module-level globals in `core.py`. Subcommands set them via `core.configure(...)`. **Always reference as `core.NOSOUND` etc.**, never `from horavox.core import NOSOUND` — that copies the value at import time and breaks `--debug`/`--nosound`.
- **Polish 12-hour next-hour overrides**: at 23:30 we say "wpół do dwunastej" not "wpół do północy". Implemented via optional `next_hour_midnight` / `next_hour_midnight_alt` fields in language JSON.
- **Voice catalog URLs**: overridable via `HORAVOX_VOICES_JSON_URL` and `HORAVOX_VOICES_BASE_URL` env vars (for CI/mirrors).
- **TEMP_WAV** is per-process (`/tmp/horavox-<pid>.wav`) — safe for concurrent instances.

## Testing

- `make test` — run pytest
- `make coverage` — pytest with coverage, writes `coverage.lcov`
- `make lint` — ruff check + format check
- E2E tests use `HOME=/tmp/horavox-test-...` to avoid touching real `~/.horavox`
- `--debug` flag (alias for `--nosound --verbose`) lets tests inspect output without audio

## Publishing

- Bump `VERSION` in `Makefile` (single source of truth)
- `make publish` — updates version in `pyproject.toml` + `cli.py` + README badge, builds, uploads to PyPI
- `make publish-test` — uploads to TestPyPI

## CI

`.github/workflows/ci.yml`: lint → test (uploads `coverage.lcov` artifact) → coveralls (only on push to `jcubic/horavox`, not PRs/forks). Concurrency group cancels older runs on same ref.
