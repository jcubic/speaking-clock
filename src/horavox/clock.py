"""vox clock — run the speaking clock."""

import argparse
import datetime
import os
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
    is_in_range,
    load_language_data,
    log,
    log_error,
    parse_time_arg,
    parse_time_range,
    play_beep,
    play_speech,
    prepare_speech,
    remove_session,
    resolve_voice,
    speak,
    time_to_minutes,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the speaking clock",
        prog="vox clock",
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
    parser.add_argument(
        "--time",
        type=str,
        default=None,
        metavar="HH:MM",
        help="Set simulated start time for debugging (e.g., 16:00)",
    )
    parser.add_argument("--exit", action="store_true", help="Run once and exit (for debugging)")
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


def run_clock(args, lang, lang_data, time_offset, start_minutes, end_minutes):
    """Main clock loop. Runs in foreground or as daemon action."""

    def get_now():
        return datetime.datetime.now() + time_offset

    # Load voice (intentionally here — after daemon fork to avoid threading issues)
    if core.NOSOUND:
        voice = None
    else:
        voice_path = resolve_voice(args.voice, lang)
        voice_name = os.path.basename(voice_path).replace(".onnx", "")
        log(f"Loading voice: {voice_name}")
        from piper import PiperVoice

        voice = PiperVoice.load(voice_path)

    freq = args.freq
    sh, sm = start_minutes // 60, start_minutes % 60
    eh, em = end_minutes // 60, end_minutes % 60
    range_str = f"{sh}:{sm:02d}-{eh}:{em:02d}"

    ANNOUNCE_OFFSET = 3

    def next_announcement(now):
        """Return (target_datetime, hour, minute) for the upcoming slot."""
        current_min = now.hour * 60 + now.minute
        frac = now.second + now.microsecond / 1_000_000
        if frac >= 5:
            current_min += 1
        slot = current_min + (freq - current_min % freq) % freq
        if current_min % freq == 0 and frac < 5:
            slot = current_min
        target_hour = (slot // 60) % 24
        target_minute = slot % 60
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target < now - datetime.timedelta(seconds=5):
            target += datetime.timedelta(days=1)
        return target, target_hour, target_minute

    # --exit mode
    if args.exit:
        now = get_now()
        frac_sec = now.second + now.microsecond / 1_000_000
        if now.minute % freq == 0 and frac_sec < 5:
            if is_in_range(now.hour, now.minute, start_minutes, end_minutes):
                text = get_spoken_time(lang_data, now.hour, now.minute)
                speak(voice, text, beep_count=beep_count_for_minute(now.minute))
            else:
                log(f"  {now.hour}:{now.minute:02d} outside range ({range_str}), skipping.")
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

    TICK = 1.0
    last_announced = None

    while True:
        now = get_now()
        target, target_hour, target_minute = next_announcement(now)
        seconds_to_target = (target - now).total_seconds()

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
                log(f"  {target_hour}:{target_minute:02d} outside range ({range_str}), skipping.")
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

    start_h, start_m = parse_time_range(args.start, "--start")
    end_h, end_m = parse_time_range(args.end, "--end")
    start_minutes = time_to_minutes(start_h, start_m)
    end_minutes = time_to_minutes(end_h, end_m)

    if args.freq < 1 or args.freq > 60:
        raise SystemExit(f"Error: --freq must be 1-60, got {args.freq}")
    if 60 % args.freq != 0:
        raise SystemExit(
            f"Error: --freq must divide 60 evenly"
            f" (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60), got {args.freq}"
        )

    if args.time:
        h, m = parse_time_arg(args.time)
        real_now = datetime.datetime.now()
        fake_now = real_now.replace(hour=h, minute=m, second=0, microsecond=0)
        time_offset = fake_now - real_now
    else:
        time_offset = datetime.timedelta(0)

    # --background mode
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
                run_clock(args, lang, lang_data, time_offset, start_minutes, end_minutes)
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

    # Foreground mode
    run_clock(args, lang, lang_data, time_offset, start_minutes, end_minutes)


if __name__ == "__main__":
    main()
