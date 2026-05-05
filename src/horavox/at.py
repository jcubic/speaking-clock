"""vox at — speak the time at specified times, optionally recurring."""

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

DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DAY_GROUPS = {
    "everyday": set(range(7)),
    "weekdays": {0, 1, 2, 3, 4},
    "weekends": {5, 6},
}


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
        print("Error: times requires at least one HH:MM value.")
        sys.exit(1)
    return sorted(times)


def parse_repeat(value):
    """Parse --repeat value into a set of weekday numbers (0=Monday..6=Sunday)."""
    days = set()
    for part in value.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in DAY_GROUPS:
            days |= DAY_GROUPS[part]
        elif part in DAY_NAMES:
            days.add(DAY_NAMES[part])
        else:
            valid = sorted(list(DAY_NAMES.keys()) + list(DAY_GROUPS.keys()))
            print(f"Error: unknown day '{part}'. Valid: {', '.join(valid)}")
            sys.exit(1)
    if not days:
        print("Error: --repeat requires at least one day.")
        sys.exit(1)
    return days


def parse_date(value):
    """Parse a YYYY-MM-DD date string."""
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: invalid date '{value}'. Use YYYY-MM-DD format.")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Speak the time at specified times",
        prog="vox at",
    )

    parser.add_argument(
        "times",
        type=str,
        help="Comma-separated times to announce (e.g. 12:55 or 9:00,12:00,18:00)",
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date to announce on (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--repeat",
        type=str,
        default=None,
        metavar="DAYS",
        help="Recurring schedule: day names (monday,friday), everyday, weekdays, weekends",
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


def _load_voice(args, lang):
    if core.NOSOUND:
        return None
    voice_path = resolve_voice(args.voice, lang)
    voice_name = os.path.basename(voice_path).replace(".onnx", "")
    log(f"Loading voice: {voice_name}")
    from piper import PiperVoice

    return PiperVoice.load(voice_path)


def run_at_once(args, lang, lang_data, time_offset, schedule, target_date):
    """One-shot mode: wait for the next matching time on target_date, speak, exit."""

    def get_now():
        return datetime.datetime.now() + time_offset

    voice = _load_voice(args, lang)

    now = get_now()
    targets = []
    for h, m in schedule:
        t = datetime.datetime.combine(target_date, datetime.time(h, m))
        if t > now - datetime.timedelta(seconds=5):
            targets.append(t)

    if not targets:
        times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
        log(f"All scheduled times ({times_str}) have passed for {target_date}.")
        return

    target = targets[0]
    times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
    log(f"\nHoraVox waiting (lang={lang})")
    log(f"  Schedule: {times_str} on {target_date}")
    if args.time:
        log(f"  Simulated start time: {args.time}")
    log("\n  (Ctrl+C to stop)")

    ANNOUNCE_OFFSET = 3
    TICK = 1.0
    last_announced = None
    announced_count = 0

    while announced_count < len(targets):
        now = get_now()
        target = targets[announced_count]
        seconds_to_target = (target - now).total_seconds()
        in_window = -5 <= seconds_to_target <= ANNOUNCE_OFFSET + 0.5

        if in_window and target != last_announced:
            last_announced = target
            text = get_spoken_time(lang_data, target.hour, target.minute)
            prepare_speech(voice, text)
            remaining = (target - get_now()).total_seconds()
            if remaining > 0:
                time.sleep(remaining)
            for _ in range(beep_count_for_minute(target.minute)):
                play_beep()
            play_speech()
            announced_count += 1
            continue

        if seconds_to_target < -5:
            announced_count += 1
            continue

        time.sleep(TICK)


def run_at_repeat(args, lang, lang_data, time_offset, schedule, repeat_days):
    """Recurring mode: loop forever, fire on matching days."""

    def get_now():
        return datetime.datetime.now() + time_offset

    voice = _load_voice(args, lang)

    if args.exit:
        now = get_now()
        weekday = now.weekday()
        frac_sec = now.second + now.microsecond / 1_000_000
        if weekday in repeat_days and (now.hour, now.minute) in schedule and frac_sec < 5:
            text = get_spoken_time(lang_data, now.hour, now.minute)
            speak(voice, text, beep_count=beep_count_for_minute(now.minute))
        else:
            times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
            days_str = _format_days(repeat_days)
            log(
                f"  Time: {now.strftime('%H:%M:%S')} ({_weekday_name(weekday)}) - not at a scheduled time ({times_str} on {days_str})."
            )
        return

    times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
    days_str = _format_days(repeat_days)
    log(f"\nHoraVox started (lang={lang})")
    log(f"  Schedule: {times_str}")
    log(f"  Repeat: {days_str}")
    if args.time:
        log(f"  Simulated start time: {args.time}")
    log("\n  (Ctrl+C to stop)")

    ANNOUNCE_OFFSET = 3
    TICK = 1.0
    last_announced = None

    while True:
        now = get_now()
        target = _next_repeat_target(now, schedule, repeat_days)
        seconds_to_target = (target - now).total_seconds()
        in_window = -5 <= seconds_to_target <= ANNOUNCE_OFFSET + 0.5

        if in_window and target != last_announced:
            last_announced = target
            text = get_spoken_time(lang_data, target.hour, target.minute)
            prepare_speech(voice, text)
            remaining = (target - get_now()).total_seconds()
            if remaining > 0:
                time.sleep(remaining)
            for _ in range(beep_count_for_minute(target.minute)):
                play_beep()
            play_speech()
            continue

        time.sleep(TICK)


def _next_repeat_target(now, schedule, repeat_days):
    """Return the next datetime matching schedule + repeat_days."""
    for day_offset in range(8):
        candidate_date = now.date() + datetime.timedelta(days=day_offset)
        if candidate_date.weekday() not in repeat_days:
            continue
        for h, m in schedule:
            candidate = datetime.datetime.combine(candidate_date, datetime.time(h, m))
            if candidate > now - datetime.timedelta(seconds=5):
                return candidate
    return datetime.datetime.combine(
        now.date() + datetime.timedelta(days=7),
        datetime.time(*schedule[0]),
    )


def _weekday_name(weekday_num):
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return names[weekday_num]


def _format_days(repeat_days):
    if repeat_days == set(range(7)):
        return "everyday"
    if repeat_days == {0, 1, 2, 3, 4}:
        return "weekdays"
    if repeat_days == {5, 6}:
        return "weekends"
    return ", ".join(_weekday_name(d) for d in sorted(repeat_days))


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

    if args.date and args.repeat:
        print("Error: --repeat and a specific date cannot be used together.")
        sys.exit(1)

    if args.time:
        h, m = parse_time_arg(args.time)
        real_now = datetime.datetime.now()
        fake_now = real_now.replace(hour=h, minute=m, second=0, microsecond=0)
        time_offset = fake_now - real_now
    else:
        time_offset = datetime.timedelta(0)

    if args.repeat:
        repeat_days = parse_repeat(args.repeat)

        if args.background:
            if not core.NOSOUND:
                voice_path = resolve_voice(args.voice, lang)
                if not os.path.exists(voice_path):
                    return

            ensure_user_dirs()
            session_id = str(uuid.uuid4())
            pid_file = os.path.join(SESSIONS_DIR, f"{session_id}.pid")

            def daemon_action_repeat():
                create_session(os.getpid(), session_id)
                try:
                    run_at_repeat(args, lang, lang_data, time_offset, schedule, repeat_days)
                except Exception:
                    log_error()
                    raise
                finally:
                    remove_session(session_id)

            daemon = Daemonize(
                app="horavox",
                pid=pid_file,
                action=daemon_action_repeat,
                chdir=PKG_DIR,
            )
            log("Starting HoraVox in the background...")
            daemon.start()
            return

        run_at_repeat(args, lang, lang_data, time_offset, schedule, repeat_days)
    else:
        target_date = parse_date(args.date) if args.date else datetime.date.today()

        if args.exit:
            now = datetime.datetime.now() + time_offset
            frac_sec = now.second + now.microsecond / 1_000_000
            if now.date() == target_date and (now.hour, now.minute) in schedule and frac_sec < 5:
                voice = _load_voice(args, lang)
                text = get_spoken_time(lang_data, now.hour, now.minute)
                speak(voice, text, beep_count=beep_count_for_minute(now.minute))
            else:
                times_str = ", ".join(f"{h}:{m:02d}" for h, m in schedule)
                log(f"  Time: {now.strftime('%H:%M:%S')} - not at a scheduled time ({times_str}).")
            return

        if args.background:
            if not core.NOSOUND:
                voice_path = resolve_voice(args.voice, lang)
                if not os.path.exists(voice_path):
                    return

            ensure_user_dirs()
            session_id = str(uuid.uuid4())
            pid_file = os.path.join(SESSIONS_DIR, f"{session_id}.pid")

            def daemon_action_once():
                create_session(os.getpid(), session_id)
                try:
                    run_at_once(args, lang, lang_data, time_offset, schedule, target_date)
                except Exception:
                    log_error()
                    raise
                finally:
                    remove_session(session_id)

            daemon = Daemonize(
                app="horavox",
                pid=pid_file,
                action=daemon_action_once,
                chdir=PKG_DIR,
            )
            log("Starting HoraVox in the background...")
            daemon.start()
            return

        run_at_once(args, lang, lang_data, time_offset, schedule, target_date)


if __name__ == "__main__":
    main()
