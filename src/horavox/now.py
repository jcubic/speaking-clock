"""vox now — speak the current time once and exit."""

import argparse
import datetime

from horavox import core
from horavox.core import (
    beep_count_for_minute,
    configure,
    detect_language,
    get_spoken_time,
    load_language_data,
    log_error,
    parse_time_arg,
    resolve_voice,
    speak,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Speak the current time once and exit",
        prog="vox now",
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
        help="Say this time instead of the current time",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show log messages",
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

    # Load voice
    if core.NOSOUND:
        voice = None
    else:
        from piper import PiperVoice

        voice_path = resolve_voice(args.voice, lang)
        voice = PiperVoice.load(voice_path)

    if args.time:
        h, m = parse_time_arg(args.time)
    else:
        now = datetime.datetime.now()
        h, m = now.hour, now.minute

    text = get_spoken_time(lang_data, h, m)
    speak(voice, text, beep_count=beep_count_for_minute(m))


if __name__ == "__main__":
    main()
