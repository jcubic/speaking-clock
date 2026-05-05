"""vox voice — manage Piper voice models with interactive browser."""

import argparse
import sys
import termios
import tty

from horavox.core import (
    detect_language,
    download_voice,
    get_voices_catalog,
    list_voices_for_language,
    log_error,
    uninstall_voice,
)

GREEN = "\033[32m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Manage Piper voice models",
        prog="vox voice",
    )

    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        metavar="LANG",
        help="Language code, e.g. pl, en (default: from system locale)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_voices",
        help="List available voices (non-interactive)",
    )

    args = parser.parse_args()
    return args


def get_lang_name(lang):
    """Get the English name for a language code."""
    catalog = get_voices_catalog()
    for _, info in catalog.items():
        if info.get("language", {}).get("family", "") == lang:
            return info.get("language", {}).get("name_english", lang)
    return lang


def cmd_list(lang):
    """Print voice list to stdout (non-interactive, no colors)."""
    voices = list_voices_for_language(lang)
    if not voices:
        print(f"No voices found for language '{lang}'.")
        return
    lang_name = get_lang_name(lang)
    print(f"Available voices for {lang_name} ({lang}):\n")
    print(f"  {'Voice':<40} {'Quality':<10} {'Size':<10} {'Installed'}")
    print(f"  {'-' * 40} {'-' * 10} {'-' * 10} {'-' * 10}")
    for v in voices:
        mark = "[*]" if v["installed"] else ""
        print(f"  {v['key']:<40} {v['quality']:<10} {v['size_mb']:.0f} MB     {mark}")


def getch():
    """Read a single keypress. Returns 'UP', 'DOWN', or a character."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                if ch3 == "A":
                    return "UP"
                if ch3 == "B":
                    return "DOWN"
            return None
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def render_list(voices, cursor, lang_name, lang, status=""):
    """Render the voice list with cursor and status line."""
    lines = []
    lines.append(f"Voices for {lang_name} ({lang}):")
    lines.append("")
    for i, v in enumerate(voices):
        arrow = ">" if i == cursor else " "
        if v["installed"]:
            mark = f" {GREEN}[*]{RESET}"
        else:
            mark = "    "
        line = f"  {arrow} {v['key']:<40} {v['quality']:<8} {v['size_mb']:>3.0f} MB{mark}"
        lines.append(line)
    lines.append("")
    nav = f"{BOLD}↑/↓{RESET} Navigate"
    inst = f"{BOLD}i{RESET} Install"
    uninst = f"{BOLD}u{RESET} Uninstall"
    quit_hint = f"{BOLD}q{RESET} Quit"
    lines.append(f"  {nav}  {inst}  {uninst}  {quit_hint}")
    if status:
        lines.append(f"  {status}")
    return lines


def draw(lines, prev_line_count):
    """Draw lines, clearing any previous output first."""
    # Move up to overwrite previous render
    if prev_line_count > 0:
        sys.stdout.write(f"\033[{prev_line_count}A")
    for line in lines:
        sys.stdout.write(f"{CLEAR_LINE}{line}\n")
    # Clear any leftover lines from previous longer render
    if prev_line_count > len(lines):
        for _ in range(prev_line_count - len(lines)):
            sys.stdout.write(f"{CLEAR_LINE}\n")
        sys.stdout.write(f"\033[{prev_line_count - len(lines)}A")
    sys.stdout.flush()


def progress_bar(filename, block_num, block_size, total_size):
    """Render a download progress bar on the current line."""
    if total_size <= 0:
        return
    downloaded = block_num * block_size
    pct = min(100, downloaded * 100 // total_size)
    bar_width = 30
    filled = bar_width * pct // 100
    bar = "█" * filled + "░" * (bar_width - filled)
    sys.stdout.write("\033[s")  # save cursor
    sys.stdout.write(f"\r{CLEAR_LINE}  Downloading {filename}... [{bar}] {pct}%")
    sys.stdout.flush()
    if pct >= 100:
        sys.stdout.write(f"\r{CLEAR_LINE}")
        sys.stdout.write("\033[u")  # restore cursor
        sys.stdout.flush()


def cmd_interactive(lang):
    """Interactive voice browser with install/uninstall."""
    voices = list_voices_for_language(lang)
    if not voices:
        print(f"No voices found for language '{lang}'.")
        return

    lang_name = get_lang_name(lang)
    cursor = 0
    prev_lines = 0
    status = ""

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            lines = render_list(voices, cursor, lang_name, lang, status)
            draw(lines, prev_lines)
            prev_lines = len(lines)
            status = ""

            key = getch()
            if key == "UP" and cursor > 0:
                cursor -= 1
            elif key == "DOWN" and cursor < len(voices) - 1:
                cursor += 1
            elif key in ("q", "\x03", "\x1b"):  # q, Ctrl-C, Esc
                break
            elif key == "i":
                v = voices[cursor]
                if v["installed"]:
                    status = f"'{v['key']}' is already installed."
                else:
                    # Render status before download
                    msg = f"Installing {v['key']}..."
                    lines = render_list(voices, cursor, lang_name, lang, msg)
                    draw(lines, prev_lines)
                    prev_lines = len(lines)
                    download_voice(v["key"], progress_cb=progress_bar)
                    v["installed"] = True
                    status = f"Installed '{v['key']}'."
            elif key == "u":
                v = voices[cursor]
                if not v["installed"]:
                    status = f"'{v['key']}' is not installed."
                else:
                    uninstall_voice(v["key"])
                    v["installed"] = False
                    status = f"Uninstalled '{v['key']}'."
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write("\n")
        sys.stdout.flush()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + "\n")
        sys.stdout.flush()
    except Exception:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()
        log_error()
        raise


def _main():
    args = parse_args()
    from horavox.config import apply_config

    apply_config(args)
    lang = args.lang or detect_language()

    if args.list_voices:
        cmd_list(lang)
    else:
        cmd_interactive(lang)


if __name__ == "__main__":
    main()
