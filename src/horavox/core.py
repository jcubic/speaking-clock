"""HoraVox shared library — paths, logging, language, TTS, voice, session management."""

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
import wave

__version__ = "0.2.0"

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

VOICES_JSON_URL = os.environ.get(
    "HORAVOX_VOICES_JSON_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json",
)
VOICES_BASE_URL = os.environ.get(
    "HORAVOX_VOICES_BASE_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main",
)
TEMP_WAV = f"/tmp/horavox-{os.getpid()}.wav"
LOG_FILE = os.path.join(USER_DIR, "horavox.log")
# ============================================

VERBOSE = False
NOSOUND = False
VOLUME = 100


def configure(verbose=False, nosound=False, volume=100, debug=False):
    """Set global audio/logging flags. Call from each subcommand's main()."""
    global VERBOSE, NOSOUND, VOLUME
    if debug:
        verbose = True
        nosound = True
    VERBOSE = verbose
    if not 0 <= volume <= 100:
        print(f"Error: --volume must be 0-100, got {volume}")
        sys.exit(1)
    VOLUME = volume
    if nosound:
        VOLUME = 0
    NOSOUND = nosound or VOLUME == 0


# ==================== LOGGING ====================


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


# ==================== LANGUAGE ====================


def detect_language():
    """Detect language from system locale, return 2-letter code."""
    try:
        loc = locale.getlocale()[0]  # e.g. "pl_PL", "en_US"
        if loc and len(loc) >= 2:
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
            print("Error: data/lang/en.json not found.")
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

    next_hour_name = hours[next_hour]
    next_hour_alt_name = hours_alt[next_hour]
    if next_hour == 0:
        next_hour_name = lang_data.get("next_hour_midnight", next_hour_name)
        next_hour_alt_name = lang_data.get("next_hour_midnight_alt", next_hour_alt_name)

    def fill(pattern, minute_val=None):
        result = pattern
        result = result.replace("{hour}", hours[hour])
        result = result.replace("{hour_alt}", hours_alt[hour])
        result = result.replace("{next_hour}", next_hour_name)
        result = result.replace("{next_hour_alt}", next_hour_alt_name)
        if minute_val is not None and ("{minutes}" in result or "{remaining}" in result):
            minute_key = str(minute_val)
            word = minutes_map.get(minute_key, minute_key)
            result = result.replace("{minutes}", word)
            result = result.replace("{remaining}", word)
        return result

    if minute == 0:
        return fill(patterns["full_hour"])

    if "time" in patterns:
        return fill(patterns["time"], minute)

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


def download_voice(voice_key, progress_cb=None):
    """Download a voice from Hugging Face to the voices directory.

    progress_cb(filename, block_num, block_size, total_size) is called
    during download if provided. Pass None for silent/default output.
    """
    catalog = get_voices_catalog()
    if voice_key not in catalog:
        print(f"Error: voice '{voice_key}' not found in catalog.")
        print("Use 'vox voice' to see available voices.")
        sys.exit(1)

    info = catalog[voice_key]
    os.makedirs(VOICES_DIR, exist_ok=True)

    for file_path, file_info in info.get("files", {}).items():
        filename = os.path.basename(file_path)
        dest = os.path.join(VOICES_DIR, filename)

        if os.path.exists(dest):
            continue

        url = f"{VOICES_BASE_URL}/{file_path}"

        if progress_cb is None:
            size_mb = file_info.get("size_bytes", 0) / (1024 * 1024)
            print(f"Downloading {filename} ({size_mb:.1f} MB)...")

        def hook(block_num, block_size, total_size):
            if progress_cb:
                progress_cb(filename, block_num, block_size, total_size)

        try:
            urllib.request.urlretrieve(url, dest, reporthook=hook)
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            if os.path.exists(dest):
                os.remove(dest)
            sys.exit(1)

    if progress_cb is None:
        print(f"Voice '{voice_key}' installed.")


def uninstall_voice(voice_key):
    """Remove a voice's files from ~/.horavox/voices/."""
    removed = False
    for ext in (".onnx", ".onnx.json"):
        path = os.path.join(VOICES_DIR, f"{voice_key}{ext}")
        if os.path.exists(path):
            os.remove(path)
            removed = True
    if removed:
        print(f"Voice '{voice_key}' uninstalled.")
    else:
        print(f"Voice '{voice_key}' not found.")


def find_voice_for_language(lang):
    """Find an installed voice matching the language. Returns .onnx path or None."""
    pattern = os.path.join(VOICES_DIR, f"{lang}_*.onnx")
    matches = [f for f in glob.glob(pattern) if not f.endswith(".onnx.json")]
    if matches:
        for m in matches:
            if "-medium." in m:
                return m
        return matches[0]
    return None


def resolve_voice(voice_name, lang):
    """Resolve which voice to use. Downloads if needed. Returns .onnx path."""
    if voice_name:
        onnx_path = os.path.join(VOICES_DIR, f"{voice_name}.onnx")
        if not os.path.exists(onnx_path):
            log(f"Voice '{voice_name}' not found locally, downloading...")
            download_voice(voice_name)
        return onnx_path

    voice_path = find_voice_for_language(lang)
    if voice_path:
        return voice_path

    print(f"No voice installed for language '{lang}'.")
    print(f"Run: vox voice --lang {lang} (then press 'i' to install)")
    print(f"Or list available voices: vox voice --list --lang {lang}")
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
    """Synthesize WAV and play blank MP3 to warm up Bluetooth audio."""
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
    subprocess.run(["aplay", TEMP_WAV], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(TEMP_WAV):
        os.remove(TEMP_WAV)


def speak(voice, text, beep_count=0):
    """Synthesize and play speech (no timing control)."""
    prepare_speech(voice, text)
    for _ in range(beep_count):
        play_beep()
    play_speech()


# ==================== SESSION MANAGEMENT ====================


def get_running_sessions():
    """Return list of active sessions as (filepath, data) tuples."""
    if not os.path.exists(SESSIONS_DIR):
        return []
    sessions = []
    for name in os.listdir(SESSIONS_DIR):
        path = os.path.join(SESSIONS_DIR, name)
        if not name.endswith(".json"):
            if name.endswith(".pid"):
                os.remove(path)
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pid = data["pid"]
            os.kill(pid, 0)
            sessions.append((path, data))
        except (json.JSONDecodeError, KeyError, ValueError):
            os.remove(path)
        except OSError:
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


def remove_session(session_id):
    """Remove session files for a given session ID."""
    for ext in (".json", ".pid"):
        path = os.path.join(SESSIONS_DIR, f"{session_id}{ext}")
        if os.path.exists(path):
            os.remove(path)


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
    pid_path = path.replace(".json", ".pid")
    if os.path.exists(pid_path):
        os.remove(pid_path)


# ==================== TIME UTILITIES ====================


def parse_time_range(value, name):
    """Parse a --start/--end value into (hour, minute)."""
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
        print(f"Error: {name} must be H, HH, H:MM, or HH:MM (e.g., 7, 07:30), got '{value}'")
        sys.exit(1)


def parse_time_arg(value):
    """Parse a --time HH:MM value into (hour, minute)."""
    try:
        h, m = map(int, value.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h, m
    except ValueError:
        print(f"Error: --time must be HH:MM (e.g., 16:00), got '{value}'")
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
