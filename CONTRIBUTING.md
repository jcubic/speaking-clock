# Contributing to HoraVox

## Development setup

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

## Testing

Tests are written with [pytest](https://docs.pytest.org/). Run them with:

```bash
make test
```

To generate a coverage report (LCOV format for Coveralls):

```bash
make coverage
```

This outputs a terminal summary and writes `coverage.lcov`.

### Test structure

- `tests/test_core.py` -- unit tests for `horavox.core` (language, time utilities, voice management, sessions, logging, WAV scaling)
- `tests/test_cli.py` -- E2E tests for all CLI commands (`vox clock`, `vox now`, `vox stop`, `vox voice`)

### Writing tests

- Unit tests should import from `horavox.core` directly
- E2E tests should run commands via `subprocess` using `python -m horavox.<module>`
- Use `--debug` (alias for `--nosound --verbose`) to test CLI output without audio playback
- Clean up any background daemons started during tests

## Publishing to PyPI

Update the `VERSION` variable in the `Makefile`, then run:

```bash
make publish
```

This updates the version in `pyproject.toml`, `core.py`, and `README.md`, builds the package, and uploads it to PyPI.

To test on TestPyPI first:

```bash
make publish-test
```

## Project structure

```
src/horavox/
  __init__.py         Package init
  core.py             Shared library (paths, logging, language, TTS, voice, sessions)
  main.py             CLI dispatcher (vox <command>)
  clock.py            vox clock -- speaking clock loop + daemon
  now.py              vox now -- speak once
  stop.py             vox stop -- manage running instances
  voice.py            vox voice -- interactive voice browser
  data/
    lang/             Language JSON files (en.json, pl.json)
    blank.mp3         Silent MP3 for Bluetooth audio wake-up
    beep.mp3          Beep sound for hour/half-hour signals
tests/
  test_core.py        Unit tests
  test_cli.py         E2E tests
```
