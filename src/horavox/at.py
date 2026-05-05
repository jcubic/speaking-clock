"""vox at — speak the time at specified times."""

import argparse
import datetime
import os
import sys
import time
import uuid

from daemonize import Daemonize

from horavox import core
from horavox.core import (
    PKG_DIR,
    SESSIONS_DIR,
    beep_count_for_minute,
    configure,
    create_session,
    detect_language,
    ensure_user_dirs,
    get_spoken_time,
    load_language_data,
    log,
    log_error,
    parse_time_arg,
    play_beep,
    play_speech,
    prepare_speech,
    remove_session,
    resolve_voice,
    speak,
)


def parse_times(value):
    """Parse comma-separated HH:MM times into sorted list of (hour, minute)."""
    times = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        h, m = parse_time_arg(part)
        times.add((h, m))
    if not times:
        print("Error: --times requires at least one HH:MM value.")
        sys.exit(1)
    return sorted(times)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Speak the time at specified times",
        prog="vox at",
    )

    parser.add_argument(
        "times",
        type=str,
        help="Comma-separated times to announce (e.g. 9:00,12:00,18:00)",
    )
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
        "--time",
        type=str,
        default=None,
        metavar="HH:MM",
        help="Set simulated start time for debugging (e.g., 16:00)",
    )
    parser.add_argument("--exit", action="store_true", help="Check once and exit (for debugging)")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Run as a background daemon",
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


def run_at(args, lang, lang_data, time_offset, schedule):
    """Main loop. Fires at each scheduled (hour, minute)."""

    def get_now():
        return datetime.datetime.now() + time_offset

    if core.NOSOUND:
        voice = None
    else:
        voice_path = resolve_voice(args.voice, lang)
        voice_name = os.path.basename(voice_path).replace(".onnx", "")
        log(f"Loading voice: {voice_name}")
        from piper import PiperVoice

        voice = PiperVoice.load(voice_path)

    ANNOUNCE_OFFSET = 3

    def next_target(now):
        """Return the next scheduled datetime."""
        today = now.date()
        for h, m in schedule:
            candidate = datetime.datetime.combine(today, datetime.time(h, m))
            if candidate > now - datetime.timedelta(seconds=5):
                return candidate
        first_h, first_m = schedule[0]
        return datetime.datetime.combine(
            today + datetime.timedelta(days=1),
            datetime.time(first_h, first_m),
        )

    if args.exit:
        now = get_now()
        frac_sec = now.second + now.microsecond / 1_000_000
        if (now.hour, now.minute) in schedule and frac_sec < 5:
            text = get_spoken_time(lang_data, now.hour, now.minute)
            speak(voice, text, beep_count=beep_count_for_minute(now.minute))
        else:
            times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
            log(f"  Time: {now.strftime('%H:%M:%S')} - not at a scheduled time ({times_str}).")
        return

    times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
    log(f"\nHoraVox started (lang={lang})")
    log(f"  Schedule: {times_str}")
    if args.time:
        log(f"  Simulated start time: {args.time}")
    log("\n  (Ctrl+C to stop)")

    TICK = 1.0
    last_announced = None

    while True:
        now = get_now()
        target = next_target(now)
        seconds_to_target = (target - now).total_seconds()

        in_window = -5 <= seconds_to_target <= ANNOUNCE_OFFSET + 0.5

        if in_window and target != last_announced:
            last_announced = target
            target_hour, target_minute = target.hour, target.minute
            text = get_spoken_time(lang_data, target_hour, target_minute)
            prepare_speech(voice, text)
            remaining = (target - get_now()).total_seconds()
            if remaining > 0:
                time.sleep(remaining)
            for _ in range(beep_count_for_minute(target_minute)):
                play_beep()
            play_speech()
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
    args = parse_args()
    from horavox.config import apply_config
    apply_config(args)
    configure(
        verbose=args.verbose,
        nosound=args.nosound,
        volume=args.volume,
        debug=args.debug,
    )

    lang = args.lang or detect_language()
    lang_data, lang = load_language_data(lang, args.mode)

    schedule = parse_times(args.times)

    if args.time:
        h, m = parse_time_arg(args.time)
        real_now = datetime.datetime.now()
        fake_now = real_now.replace(hour=h, minute=m, second=0, microsecond=0)
        time_offset = fake_now - real_now
    else:
        time_offset = datetime.timedelta(0)

    if args.background:
        if not core.NOSOUND:
            voice_path = resolve_voice(args.voice, lang)
            if not os.path.exists(voice_path):
                return

        ensure_user_dirs()

        session_id = str(uuid.uuid4())
        pid_file = os.path.join(SESSIONS_DIR, f"{session_id}.pid")

        def daemon_action():
            create_session(os.getpid(), session_id)
            try:
                run_at(args, lang, lang_data, time_offset, schedule)
            except Exception:
                log_error()
                raise
            finally:
                remove_session(session_id)

        daemon = Daemonize(
            app="horavox",
            pid=pid_file,
            action=daemon_action,
            chdir=PKG_DIR,
        )
        log("Starting HoraVox in the background...")
        daemon.start()
        return

    run_at(args, lang, lang_data, time_offset, schedule)


if __name__ == "__main__":
    main()
