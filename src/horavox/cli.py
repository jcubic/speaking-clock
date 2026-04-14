#!/usr/bin/env python

import argparse
import array
import datetime
import glob
import json
import locale
import os
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
import uuid
import wave

from daemonize import Daemonize
from piper import PiperVoice

__version__ = "0.1.0"

# ================== PATHS ==================
# Package data (ships with the package, read-only)
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PKG_DIR, "data")
LANG_DIR = os.path.join(DATA_DIR, "lang")
BLANK_MP3 = os.path.join(DATA_DIR, "blank.mp3")
BEEP_MP3 = os.path.join(DATA_DIR, "beep.mp3")

# User data (writable, created at runtime)
USER_DIR = os.path.expanduser("~/.horavox")
VOICES_DIR = os.path.join(USER_DIR, "voices")
CACHE_DIR = os.path.join(USER_DIR, "cache")

SESSIONS_DIR = os.path.join(USER_DIR, "sessions")

VOICES_JSON_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json"
VOICES_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
TEMP_WAV = "/tmp/horavox.wav"
LOG_FILE = os.path.join(USER_DIR, "horavox.log")
# ============================================

VERBOSE = False
NOSOUND = False
VOLUME = 100


def log(msg):
    """Print a message only when --verbose is enabled."""
    if VERBOSE:
        print(msg)


def log_to_file(message):
    """Append a timestamped message to ~/.horavox.log."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def log_spoken(text):
    """Append a spoken-words entry to ~/.horavox.log."""
    log_to_file(text)


def log_error():
    """Append the current exception traceback to ~/.horavox.log."""
    log_to_file(traceback.format_exc().rstrip())


def parse_args():
    parser = argparse.ArgumentParser(
        description="HoraVox — announces the time using text-to-speech",
        prog="vox",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Language & voice
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        metavar="LANG",
        help="Language code, e.g. pl, en (default: from system locale)",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=None,
        metavar="NAME",
        help="Voice name, e.g. en_US-lessac-medium (auto-downloads if missing)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="classic",
        choices=["classic", "modern"],
        help="Time style: classic (idiomatic) or modern (digital) (default: classic)",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available Piper voices for the current language and exit",
    )

    # Time range
    parser.add_argument(
        "--start",
        type=str,
        default="0:00",
        metavar="HH:MM",
        help="Start time for speaking range (default: 0:00)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="23:59",
        metavar="HH:MM",
        help="End time for speaking range (default: 23:59)",
    )
    parser.add_argument(
        "--freq",
        type=int,
        default=60,
        metavar="MIN",
        help="Announcement interval in minutes (default: 60)",
    )

    # Debug
    parser.add_argument(
        "--time",
        type=str,
        default=None,
        metavar="HH:MM",
        help="Set simulated start time for debugging (e.g., 16:00)",
    )
    parser.add_argument(
        "--exit", action="store_true", help="Run once and exit (for debugging)"
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Speak the current time (with minutes) and exit",
    )

    # Background / daemon
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run as a background daemon",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop the background daemon and exit",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show log messages (silent by default)",
    )
    parser.add_argument(
        "--volume",
        type=int,
        default=100,
        metavar="PCT",
        help="Volume level 0-100 percent (default: 100, 0 = no sound)",
    )
    parser.add_argument(
        "--nosound",
        action="store_true",
        help="Same as --volume 0 — skip voice loading and audio playback",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Alias for --nosound --verbose",
    )

    return parser.parse_args()


# ==================== LANGUAGE ====================


def detect_language():
    """Detect language from system locale, return 2-letter code."""
    try:
        loc = locale.getlocale()[0]  # e.g. "pl_PL", "en_US"
        if loc:
            return loc.split("_")[0]
    except Exception:
        pass
    return "en"


def load_language_data(lang, mode="classic"):
    """Load language JSON data. Falls back to English if not found."""
    lang_file = os.path.join(LANG_DIR, f"{lang}.json")
    if not os.path.exists(lang_file):
        if lang != "en":
            log(f"Warning: data/lang/{lang}.json not found, falling back to English.")
            lang_file = os.path.join(LANG_DIR, "en.json")
            lang = "en"
        else:
            print(f"Error: data/lang/en.json not found.")
            sys.exit(1)

    with open(lang_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract mode-specific data if present
    if "classic" in data:
        if mode not in data:
            print(f"Error: mode '{mode}' not found in data/lang/{lang}.json.")
            sys.exit(1)
        data = data[mode]

    # Validate
    if len(data.get("hours", [])) != 24:
        print(f"Error: data/lang/{lang}.json 'hours' must have 24 entries.")
        sys.exit(1)

    # hours_alt defaults to hours if not provided
    if "hours_alt" not in data:
        data["hours_alt"] = data["hours"]
    elif len(data["hours_alt"]) != 24:
        print(f"Error: data/lang/{lang}.json 'hours_alt' must have 24 entries.")
        sys.exit(1)

    # Validate required patterns based on mode
    if "time" in data.get("patterns", {}):
        required_patterns = ["full_hour", "time"]
    else:
        required_patterns = [
            "full_hour",
            "quarter_past",
            "half_past",
            "quarter_to",
            "minutes_past",
            "minutes_to",
        ]
    for p in required_patterns:
        if p not in data.get("patterns", {}):
            print(f"Error: data/lang/{lang}.json missing pattern '{p}'.")
            sys.exit(1)

    return data, lang


def get_spoken_time(lang_data, hour, minute):
    """Return spoken time string using language data patterns."""
    hours = lang_data["hours"]
    hours_alt = lang_data["hours_alt"]
    minutes_map = lang_data["minutes"]
    patterns = lang_data["patterns"]

    next_hour = (hour + 1) % 24

    # When next_hour wraps to midnight, some languages use a different name
    # for "the upcoming hour 0" vs "the current hour 0" (e.g., Polish uses
    # "dwunasta" when approaching midnight but "północ" when AT midnight).
    next_hour_name = hours[next_hour]
    next_hour_alt_name = hours_alt[next_hour]
    if next_hour == 0:
        next_hour_name = lang_data.get("next_hour_midnight", next_hour_name)
        next_hour_alt_name = lang_data.get(
            "next_hour_midnight_alt", next_hour_alt_name
        )

    def fill(pattern, minute_val=None):
        result = pattern
        result = result.replace("{hour}", hours[hour])
        result = result.replace("{hour_alt}", hours_alt[hour])
        result = result.replace("{next_hour}", next_hour_name)
        result = result.replace("{next_hour_alt}", next_hour_alt_name)
        if minute_val is not None and (
            "{minutes}" in result or "{remaining}" in result
        ):
            word = minutes_map[str(minute_val)]
            result = result.replace("{minutes}", word)
            result = result.replace("{remaining}", word)
        return result

    if minute == 0:
        return fill(patterns["full_hour"])

    # Modern mode: simple hour + minutes
    if "time" in patterns:
        return fill(patterns["time"], minute)

    # Classic mode: idiomatic quarters, halves, past/to
    if minute == 15:
        return fill(patterns["quarter_past"])
    elif minute == 30:
        return fill(patterns["half_past"])
    elif minute == 45:
        return fill(patterns["quarter_to"])
    elif minute < 30:
        return fill(patterns["minutes_past"], minute)
    else:
        return fill(patterns["minutes_to"], 60 - minute)


# ==================== VOICE MANAGEMENT ====================


def ensure_user_dirs():
    """Create ~/.horavox/ subdirectories for cache, voices, and sessions."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(VOICES_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def get_voices_catalog():
    """Fetch and cache the Piper voices catalog from Hugging Face."""
    ensure_user_dirs()
    cache_file = os.path.join(CACHE_DIR, "voices.json")

    # Use cache if less than 24 hours old
    if os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < 86400:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    log("Fetching voice catalog from Hugging Face...")
    try:
        req = urllib.request.Request(VOICES_JSON_URL)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        if os.path.exists(cache_file):
            log(f"Warning: could not refresh catalog ({e}), using cached version.")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        print(f"Error: could not fetch voice catalog: {e}")
        sys.exit(1)


def list_voices_for_language(lang):
    """List available Piper voices for a language family."""
    catalog = get_voices_catalog()
    matches = []
    for key, info in catalog.items():
        family = info.get("language", {}).get("family", "")
        if family == lang:
            size_bytes = sum(
                f.get("size_bytes", 0)
                for f in info.get("files", {}).values()
                if f.get("size_bytes")
            )
            size_mb = size_bytes / (1024 * 1024)
            installed = is_voice_installed(key)
            matches.append(
                {
                    "key": key,
                    "name": info.get("name", ""),
                    "quality": info.get("quality", ""),
                    "region": info.get("language", {}).get("country_english", ""),
                    "speakers": info.get("num_speakers", 1),
                    "size_mb": size_mb,
                    "installed": installed,
                }
            )

    matches.sort(key=lambda v: v["key"])
    return matches


def is_voice_installed(voice_key):
    """Check if a voice's .onnx file exists in the voices directory."""
    onnx_path = os.path.join(VOICES_DIR, f"{voice_key}.onnx")
    return os.path.exists(onnx_path)


def download_voice(voice_key):
    """Download a voice from Hugging Face to the voices directory."""
    catalog = get_voices_catalog()
    if voice_key not in catalog:
        print(f"Error: voice '{voice_key}' not found in catalog.")
        print("Use --list-voices to see available voices.")
        sys.exit(1)

    info = catalog[voice_key]
    os.makedirs(VOICES_DIR, exist_ok=True)

    for file_path, file_info in info.get("files", {}).items():
        filename = os.path.basename(file_path)
        dest = os.path.join(VOICES_DIR, filename)

        if os.path.exists(dest):
            continue

        url = f"{VOICES_BASE_URL}/{file_path}"
        size_mb = file_info.get("size_bytes", 0) / (1024 * 1024)
        log(f"Downloading {filename} ({size_mb:.1f} MB)...")

        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            if os.path.exists(dest):
                os.remove(dest)
            sys.exit(1)

    log(f"Voice '{voice_key}' installed.")


def find_voice_for_language(lang):
    """Find an installed voice matching the language. Returns .onnx path or None."""
    pattern = os.path.join(VOICES_DIR, f"{lang}_*.onnx")
    matches = [f for f in glob.glob(pattern) if not f.endswith(".onnx.json")]
    if matches:
        # Prefer medium quality
        for m in matches:
            if "-medium." in m:
                return m
        return matches[0]
    return None


def resolve_voice(args, lang):
    """Resolve which voice to use. Downloads if needed. Returns .onnx path."""
    if args.voice:
        onnx_path = os.path.join(VOICES_DIR, f"{args.voice}.onnx")
        if not os.path.exists(onnx_path):
            log(f"Voice '{args.voice}' not found locally, downloading...")
            download_voice(args.voice)
        return onnx_path

    # Try to find an installed voice for the language
    voice_path = find_voice_for_language(lang)
    if voice_path:
        return voice_path

    print(f"No voice installed for language '{lang}'.")
    print(f"Run: vox --list-voices --lang {lang}")
    print(f"Then: vox --voice <name> --lang {lang}")
    sys.exit(1)


# ==================== TTS ====================


def play_blank():
    """Play blank MP3 to wake up Bluetooth audio (avoids clipping the start)."""
    if NOSOUND:
        return
    if os.path.exists(BLANK_MP3):
        subprocess.run(
            ["mpg123", "-q", BLANK_MP3],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def play_beep():
    """Play the beep MP3 once, respecting VOLUME."""
    if NOSOUND:
        return
    if os.path.exists(BEEP_MP3):
        cmd = ["mpg123", "-q"]
        if VOLUME < 100:
            cmd += ["-f", str(int(VOLUME * 32768 / 100))]
        cmd.append(BEEP_MP3)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def beep_count_for_minute(minute):
    """Return number of beeps to play: 2 on the hour, 1 on the half hour."""
    if minute == 0:
        return 2
    if minute == 30:
        return 1
    return 0


def scale_wav_volume(path):
    """Scale WAV sample amplitudes to match VOLUME (1-100)."""
    if VOLUME >= 100:
        return
    scale = VOLUME / 100.0
    with wave.open(path, "rb") as r:
        params = r.getparams()
        frames = r.readframes(r.getnframes())
    samples = array.array("h", frames)
    for i in range(len(samples)):
        samples[i] = max(-32768, min(32767, int(samples[i] * scale)))
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(samples.tobytes())


def prepare_speech(voice, text):
    """Synthesize WAV and play blank MP3 to warm up Bluetooth audio.

    Returns when the system is ready to play the speech immediately.
    """
    log(f"Preparing: {text}")
    if NOSOUND:
        return
    log_spoken(text)
    with wave.open(TEMP_WAV, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    scale_wav_volume(TEMP_WAV)
    play_blank()


def play_speech():
    """Play the previously prepared speech WAV."""
    log("Playing speech")
    if NOSOUND:
        return
    subprocess.run(
        ["aplay", TEMP_WAV], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if os.path.exists(TEMP_WAV):
        os.remove(TEMP_WAV)


def speak(voice, text, beep_count=0):
    """Synthesize and play speech (no timing control — used by --now/--exit)."""
    prepare_speech(voice, text)
    for _ in range(beep_count):
        play_beep()
    play_speech()


# ==================== DAEMON ====================


def get_running_sessions():
    """Return list of active sessions as (filepath, data) tuples.

    Each session file is a JSON with {"pid": int, "command": str}.
    Stale sessions (dead processes) are cleaned up automatically.
    """
    if not os.path.exists(SESSIONS_DIR):
        return []
    sessions = []
    for name in os.listdir(SESSIONS_DIR):
        path = os.path.join(SESSIONS_DIR, name)
        if not name.endswith(".json"):
            # Clean up orphaned .pid files from Daemonize
            if name.endswith(".pid"):
                os.remove(path)
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pid = data["pid"]
            os.kill(pid, 0)  # check if alive
            sessions.append((path, data))
        except (json.JSONDecodeError, KeyError, ValueError):
            os.remove(path)
        except OSError:
            # Process is dead, clean up stale session
            os.remove(path)
    return sessions


def create_session(pid, session_id):
    """Create a session file for a new daemon instance."""
    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    data = {
        "pid": pid,
        "command": " ".join(sys.argv),
    }
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return session_file


def kill_session(path, data):
    """Kill a daemon process and remove its session file."""
    pid = data["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            os.kill(pid, signal.SIGKILL)
        print(f"Stopped (PID {pid}).")
    except OSError as e:
        print(f"Error stopping process {pid}: {e}")
    if os.path.exists(path):
        os.remove(path)
    # Remove the companion .pid file left by Daemonize
    pid_path = path.replace(".json", ".pid")
    if os.path.exists(pid_path):
        os.remove(pid_path)


def stop_daemon():
    """Stop running daemon(s). Interactive selection when multiple are running."""
    sessions = get_running_sessions()
    if not sessions:
        print("No HoraVox instances running.")
        return

    if len(sessions) == 1:
        path, data = sessions[0]
        kill_session(path, data)
        return

    # Multiple instances: interactive selection with arrow keys
    import inquirer

    STOP_ALL = "__all__"
    choices = []
    for path, data in sessions:
        label = f"PID {data['pid']}  {data.get('command', '?')}"
        choices.append((label, path))
    choices.append(("Stop all", STOP_ALL))

    try:
        questions = [
            inquirer.List(
                "session",
                message=f"{len(sessions)} instances running. Select to stop",
                choices=choices,
            )
        ]
        answer = inquirer.prompt(questions)
    except KeyboardInterrupt:
        return

    if answer is None:
        return

    selected = answer["session"]
    if selected == STOP_ALL:
        for path, data in sessions:
            kill_session(path, data)
    else:
        for path, data in sessions:
            if path == selected:
                kill_session(path, data)
                break


# ==================== MAIN ====================


def parse_time_range(value, name):
    """Parse a --start/--end value into (hour, minute).

    Accepts 'H', 'HH', 'H:MM', or 'HH:MM'.
    """
    try:
        if ":" in value:
            h, m = map(int, value.split(":"))
        else:
            h = int(value)
            m = 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h, m
    except ValueError:
        print(
            f"Error: {name} must be H, HH, H:MM, or HH:MM (e.g., 7, 07:30), got '{value}'"
        )
        sys.exit(1)


def time_to_minutes(hour, minute):
    """Convert hour:minute to total minutes since midnight (0-1439)."""
    return hour * 60 + minute


def is_in_range(hour, minute, start_minutes, end_minutes):
    """Check if hour:minute is within range (handles midnight wrap)."""
    t = time_to_minutes(hour, minute)
    if start_minutes <= end_minutes:
        return start_minutes <= t <= end_minutes
    else:
        return t >= start_minutes or t <= end_minutes


def run_vox(args, lang, lang_data, time_offset, start_minutes, end_minutes):
    """Main loop. Runs in foreground or as daemon action."""

    def get_now():
        return datetime.datetime.now() + time_offset

    # Load voice (intentionally here — after daemon fork to avoid threading issues)
    if NOSOUND:
        voice = None
    else:
        voice_path = resolve_voice(args, lang)
        voice_name = os.path.basename(voice_path).replace(".onnx", "")
        log(f"Loading voice: {voice_name}")
        voice = PiperVoice.load(voice_path)

    freq = args.freq
    range_str = f"{start_minutes // 60}:{start_minutes % 60:02d}-{end_minutes // 60}:{end_minutes % 60:02d}"

    # --now mode: speak current time and exit
    if args.now:
        now = get_now()
        text = get_spoken_time(lang_data, now.hour, now.minute)
        speak(voice, text, beep_count=beep_count_for_minute(now.minute))
        return

    # Warm-up offset: start synthesizing + playing blank MP3 this many
    # seconds before the target so speech starts on the dot.
    # Measured: synthesis ~0.05s + blank MP3 ~2.2s = ~2.3s total.
    # Use 3s to leave margin for system jitter.
    ANNOUNCE_OFFSET = 3

    def next_announcement(now):
        """Return (target_datetime, hour, minute) for the upcoming slot.

        Within the 5-second grace window after a slot boundary, the
        just-passed slot is returned so a slightly late tick can still
        fire it.
        """
        current_min = now.hour * 60 + now.minute
        frac = now.second + now.microsecond / 1_000_000
        if frac >= 5:
            current_min += 1
        slot = current_min + (freq - current_min % freq) % freq
        if current_min % freq == 0 and frac < 5:
            slot = current_min
        target_hour = (slot // 60) % 24
        target_minute = slot % 60
        target = now.replace(
            hour=target_hour, minute=target_minute, second=0, microsecond=0
        )
        # Wrap to tomorrow only if the target is meaningfully past
        # (outside the 5s grace window).
        if target < now - datetime.timedelta(seconds=5):
            target += datetime.timedelta(days=1)
        return target, target_hour, target_minute

    # --exit mode: fire once if we're at a slot right now, then exit
    if args.exit:
        now = get_now()
        frac_sec = now.second + now.microsecond / 1_000_000
        if now.minute % freq == 0 and frac_sec < 5:
            if is_in_range(now.hour, now.minute, start_minutes, end_minutes):
                text = get_spoken_time(lang_data, now.hour, now.minute)
                speak(voice, text, beep_count=beep_count_for_minute(now.minute))
            else:
                log(
                    f"  {now.hour}:{now.minute:02d} outside range"
                    f" ({range_str}), skipping."
                )
        else:
            log(f"  Time: {now.strftime('%H:%M:%S')} - not at announcement slot.")
        return

    # Main polling loop
    log(f"\nHoraVox started (lang={lang})")
    if start_minutes != 0 or end_minutes != 23 * 60 + 59:
        log(f"  Time range: {range_str}")
    if freq != 60:
        log(f"  Announcement interval: every {freq} minutes")
    if args.time:
        log(f"  Simulated start time: {args.time}")
    log(f"  Announces every {freq} min on aligned boundaries.\n")
    log("  (Ctrl+C to stop)")

    # Tick interval. Must be strictly less than ANNOUNCE_OFFSET so every
    # target's warm-up window is guaranteed to catch at least one tick,
    # even under moderate scheduling jitter.
    TICK = 1.0

    last_announced = None

    while True:
        now = get_now()
        target, target_hour, target_minute = next_announcement(now)
        seconds_to_target = (target - now).total_seconds()

        # Fire when we're within the warm-up window (up to ANNOUNCE_OFFSET
        # seconds before target) or within the 5s grace window after (to
        # recover from tick jitter, startup, or a stalled tick).
        in_window = -5 <= seconds_to_target <= ANNOUNCE_OFFSET + 0.5

        if in_window and target != last_announced:
            last_announced = target
            if is_in_range(target_hour, target_minute, start_minutes, end_minutes):
                text = get_spoken_time(lang_data, target_hour, target_minute)
                prepare_speech(voice, text)
                remaining = (target - get_now()).total_seconds()
                if remaining > 0:
                    time.sleep(remaining)
                for _ in range(beep_count_for_minute(target_minute)):
                    play_beep()
                play_speech()
            else:
                log(
                    f"  {target_hour}:{target_minute:02d} outside range"
                    f" ({range_str}), skipping."
                )
            continue

        time.sleep(TICK)


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log_error()
        raise


def _main():
    global VERBOSE, NOSOUND, VOLUME
    args = parse_args()
    if args.debug:
        args.verbose = True
        args.nosound = True
    VERBOSE = args.verbose
    if not 0 <= args.volume <= 100:
        print(f"Error: --volume must be 0-100, got {args.volume}")
        sys.exit(1)
    VOLUME = args.volume
    if args.nosound:
        VOLUME = 0
    NOSOUND = args.nosound or VOLUME == 0

    # --stop mode: kill background daemon and exit
    if args.stop:
        stop_daemon()
        return

    # Resolve language
    lang = args.lang or detect_language()

    # --list-voices mode
    if args.list_voices:
        voices = list_voices_for_language(lang)
        if not voices:
            log(f"No voices found for language '{lang}'.")
            return

        lang_name = ""
        catalog = get_voices_catalog()
        for v in voices:
            info = catalog.get(v["key"], {})
            lang_name = info.get("language", {}).get("name_english", lang)
            break

        print(f"Available voices for {lang_name} ({lang}):\n")
        print(f"  {'Voice':<40} {'Quality':<10} {'Size':<10} {'Installed'}")
        print(f"  {'-' * 40} {'-' * 10} {'-' * 10} {'-' * 10}")
        for v in voices:
            mark = "*" if v["installed"] else ""
            print(
                f"  {v['key']:<40} {v['quality']:<10} {v['size_mb']:.0f} MB     {mark}"
            )
        print(f"\nInstall a voice: vox --voice <name>")
        return

    # Load language data
    lang_data, lang = load_language_data(lang, args.mode)

    # Parse and validate time range
    start_h, start_m = parse_time_range(args.start, "--start")
    end_h, end_m = parse_time_range(args.end, "--end")
    start_minutes = time_to_minutes(start_h, start_m)
    end_minutes = time_to_minutes(end_h, end_m)

    # Validate frequency
    if args.freq < 1 or args.freq > 60:
        print(f"Error: --freq must be 1-60, got {args.freq}")
        return
    if 60 % args.freq != 0:
        print(
            f"Error: --freq must divide 60 evenly"
            f" (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60), got {args.freq}"
        )
        return

    # Compute time offset for --time option
    if args.time:
        try:
            h, m = map(int, args.time.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            print(f"Error: --time must be HH:MM (e.g., 16:00), got '{args.time}'")
            return
        real_now = datetime.datetime.now()
        fake_now = real_now.replace(hour=h, minute=m, second=0, microsecond=0)
        time_offset = fake_now - real_now
    else:
        time_offset = datetime.timedelta(0)

    # --background mode: daemonize using the daemonize library
    if args.background:
        # Validate voice exists before forking (so errors are visible)
        if not NOSOUND:
            voice_path = resolve_voice(args, lang)
            if not os.path.exists(voice_path):
                return

        ensure_user_dirs()

        # Each instance gets its own session with a unique PID file
        session_id = str(uuid.uuid4())
        pid_file = os.path.join(SESSIONS_DIR, f"{session_id}.pid")

        def daemon_action():
            # Write session JSON now that we're in the forked process
            create_session(os.getpid(), session_id)
            try:
                run_vox(
                    args, lang, lang_data, time_offset, start_minutes, end_minutes
                )
            except Exception:
                log_error()
                raise

        daemon = Daemonize(
            app="horavox",
            pid=pid_file,
            action=daemon_action,
            chdir=PKG_DIR,
        )
        log(f"Starting HoraVox in the background...")
        daemon.start()
        return

    # Foreground mode
    run_vox(args, lang, lang_data, time_offset, start_minutes, end_minutes)


if __name__ == "__main__":
    main()
