"""Unit tests for command modules — main, clock, now, stop, voice.

Tests the option parsing and dispatch logic by mocking core functions.
"""

import sys
from unittest import mock

import pytest

from horavox import core

# ==================== main.py ====================


class TestMainDispatcher:
    def test_no_args_prints_help(self, capsys):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox"]):
            main()
        out = capsys.readouterr().out
        assert "Usage: vox <command>" in out
        assert "clock" in out
        assert "now" in out
        assert "stop" in out
        assert "voice" in out

    def test_help_flag(self, capsys):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "--help"]):
            main()
        out = capsys.readouterr().out
        assert "Usage: vox <command>" in out

    def test_version_flag(self, capsys):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "--version"]):
            main()
        out = capsys.readouterr().out
        assert core.__version__ in out

    def test_version_short_flag(self, capsys):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "-V"]):
            main()
        out = capsys.readouterr().out
        assert core.__version__ in out

    def test_unknown_command(self, capsys):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "bogus"]):
            with mock.patch("horavox.main.shutil.which", return_value=None):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "Unknown command: bogus" in out

    def test_dispatches_to_clock(self):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "clock"]):
            with mock.patch("horavox.clock.main") as m:
                main()
                m.assert_called_once()

    def test_dispatches_to_now(self):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "now"]):
            with mock.patch("horavox.now.main") as m:
                main()
                m.assert_called_once()

    def test_dispatches_to_stop(self):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "stop"]):
            with mock.patch("horavox.stop.main") as m:
                main()
                m.assert_called_once()

    def test_dispatches_to_voice(self):
        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "voice"]):
            with mock.patch("horavox.voice.main") as m:
                main()
                m.assert_called_once()

    def test_external_command(self):
        import shutil as _shutil

        from horavox.main import main

        with mock.patch.object(sys, "argv", ["vox", "my-plugin"]):
            with mock.patch.object(_shutil, "which", return_value="/usr/bin/vox-my-plugin"):
                with mock.patch("os.execvp") as m:
                    main()
                    m.assert_called_once_with("/usr/bin/vox-my-plugin", ["vox-my-plugin"])

    def test_argv_rewrite(self):
        from horavox.main import main

        captured_argv = []

        def fake_main():
            captured_argv.extend(sys.argv)

        with mock.patch.object(sys, "argv", ["vox", "clock", "--verbose"]):
            with mock.patch("horavox.clock.main", side_effect=fake_main):
                main()
        assert captured_argv == ["vox clock", "--verbose"]


# ==================== now.py ====================


class TestNowCommand:
    def test_debug_with_time(self):
        from horavox import now

        with mock.patch.object(
            sys, "argv", ["vox now", "--debug", "--time", "12:00", "--lang", "en"]
        ):
            with mock.patch.object(now, "speak") as mock_speak:
                now.main()
                mock_speak.assert_called_once()
                text = mock_speak.call_args[0][1]
                assert "noon" in text.lower()

    def test_debug_current_time(self):
        from horavox import now

        with mock.patch.object(sys, "argv", ["vox now", "--debug", "--lang", "en"]):
            with mock.patch.object(now, "speak") as mock_speak:
                now.main()
                mock_speak.assert_called_once()

    def test_modern_mode(self):
        from horavox import now

        with mock.patch.object(
            sys,
            "argv",
            ["vox now", "--debug", "--time", "9:30", "--mode", "modern", "--lang", "en"],
        ):
            with mock.patch.object(now, "speak") as mock_speak:
                now.main()
                text = mock_speak.call_args[0][1]
                assert text == "nine thirty"

    def test_nosound_flag(self):
        from horavox import now

        with mock.patch.object(sys, "argv", ["vox now", "--nosound", "--lang", "en"]):
            with mock.patch.object(now, "speak") as mock_speak:
                now.main()
                mock_speak.assert_called_once()

    def test_keyboard_interrupt(self):
        from horavox import now

        with mock.patch.object(sys, "argv", ["vox now", "--debug"]):
            with mock.patch.object(now, "speak", side_effect=KeyboardInterrupt):
                now.main()  # should not raise

    def test_exception_logs_error(self):
        from horavox import now

        with mock.patch.object(sys, "argv", ["vox now", "--debug"]):
            with mock.patch.object(now, "speak", side_effect=RuntimeError("boom")):
                with mock.patch.object(now, "log_error") as mock_log:
                    with pytest.raises(RuntimeError):
                        now.main()
                    mock_log.assert_called_once()


# ==================== stop.py ====================


class TestListCommand:
    def test_list_pids(self, capsys):
        from horavox import list as list_cmd

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock --freq 30"}),
        ]
        with mock.patch.object(sys, "argv", ["vox list"]):
            with mock.patch.object(list_cmd, "get_running_sessions", return_value=sessions):
                list_cmd.main()
        out = capsys.readouterr().out
        assert "111" in out
        assert "222" in out
        assert "vox clock" not in out  # no --verbose

    def test_list_verbose(self, capsys):
        from horavox import list as list_cmd

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock --freq 30"}),
        ]
        with mock.patch.object(sys, "argv", ["vox list", "--verbose"]):
            with mock.patch.object(list_cmd, "get_running_sessions", return_value=sessions):
                list_cmd.main()
        out = capsys.readouterr().out
        assert "111" in out
        assert "vox clock --freq 30" in out

    def test_list_empty(self, capsys):
        from horavox import list as list_cmd

        with mock.patch.object(sys, "argv", ["vox list"]):
            with mock.patch.object(list_cmd, "get_running_sessions", return_value=[]):
                list_cmd.main()
        out = capsys.readouterr().out
        assert out.strip() == ""


class TestStopCommand:
    def test_pid_mode(self):
        from horavox import stop

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock"}),
        ]
        with mock.patch.object(sys, "argv", ["vox stop", "--pid", "222"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch.object(stop, "kill_session") as mock_kill:
                    stop.main()
                    mock_kill.assert_called_once_with(
                        "/tmp/b.json", {"pid": 222, "command": "vox clock"}
                    )

    def test_pid_not_found(self, capsys):
        from horavox import stop

        with mock.patch.object(sys, "argv", ["vox stop", "--pid", "999"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=[]):
                with pytest.raises(SystemExit):
                    stop.main()
        out = capsys.readouterr().out
        assert "No HoraVox instance with PID 999" in out

    def test_no_instances(self, capsys):
        from horavox import stop

        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=[]):
                stop.main()
        out = capsys.readouterr().out
        assert "No HoraVox instances running" in out

    def test_single_instance_direct_kill(self):
        from horavox import stop

        sessions = [("/tmp/a.json", {"pid": 111, "command": "vox clock"})]
        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch.object(stop, "kill_session") as mock_kill:
                    stop.main()
                    mock_kill.assert_called_once()

    def test_keyboard_interrupt(self):
        from horavox import stop

        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", side_effect=KeyboardInterrupt):
                stop.main()  # should not raise

    def test_multiple_inquirer_stop_all(self):
        from horavox import stop

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock"}),
        ]
        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch.object(stop, "kill_session") as mock_kill:
                    with mock.patch("inquirer.prompt", return_value={"session": "__all__"}):
                        stop.main()
                        assert mock_kill.call_count == 2

    def test_multiple_inquirer_stop_one(self):
        from horavox import stop

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock"}),
        ]
        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch.object(stop, "kill_session") as mock_kill:
                    with mock.patch("inquirer.prompt", return_value={"session": "/tmp/b.json"}):
                        stop.main()
                        mock_kill.assert_called_once_with(
                            "/tmp/b.json", {"pid": 222, "command": "vox clock"}
                        )

    def test_multiple_inquirer_cancel(self):
        from horavox import stop

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock"}),
        ]
        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch.object(stop, "kill_session") as mock_kill:
                    with mock.patch("inquirer.prompt", return_value=None):
                        stop.main()
                        mock_kill.assert_not_called()

    def test_multiple_inquirer_keyboard_interrupt(self):
        from horavox import stop

        sessions = [
            ("/tmp/a.json", {"pid": 111, "command": "vox clock"}),
            ("/tmp/b.json", {"pid": 222, "command": "vox clock"}),
        ]
        with mock.patch.object(sys, "argv", ["vox stop"]):
            with mock.patch.object(stop, "get_running_sessions", return_value=sessions):
                with mock.patch("inquirer.prompt", side_effect=KeyboardInterrupt):
                    stop.main()  # should not raise

    def test_parse_args(self):
        from horavox.stop import parse_args

        with mock.patch.object(sys, "argv", ["vox stop", "--pid", "123"]):
            args = parse_args()
        assert args.pid == 123


# ==================== clock.py ====================


class TestClockCommand:
    def test_debug_exit_at_slot(self):
        from horavox import clock

        with mock.patch.object(
            sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:00", "--lang", "en"]
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                mock_speak.assert_called_once()
                text = mock_speak.call_args[0][1]
                assert "noon" in text.lower()

    def test_debug_exit_not_at_slot(self, capsys):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:01"]):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                mock_speak.assert_not_called()
        out = capsys.readouterr().out
        assert "not at announcement slot" in out

    def test_debug_exit_outside_range(self, capsys):
        from horavox import clock

        with mock.patch.object(
            sys,
            "argv",
            ["vox clock", "--debug", "--exit", "--time", "12:00", "--start", "13", "--end", "23"],
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                mock_speak.assert_not_called()
        out = capsys.readouterr().out
        assert "outside range" in out

    def test_freq_30(self):
        from horavox import clock

        with mock.patch.object(
            sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:30", "--freq", "30"]
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                mock_speak.assert_called_once()

    def test_invalid_freq(self):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--debug", "--exit", "--freq", "7"]):
            with pytest.raises(SystemExit, match="must divide 60 evenly"):
                clock.main()

    def test_invalid_freq_too_high(self):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--debug", "--exit", "--freq", "99"]):
            with pytest.raises(SystemExit, match="must be 1-60"):
                clock.main()

    def test_modern_mode(self):
        from horavox import clock

        with mock.patch.object(
            sys,
            "argv",
            [
                "vox clock",
                "--debug",
                "--exit",
                "--time",
                "17:00",
                "--mode",
                "modern",
                "--lang",
                "pl",
            ],
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                text = mock_speak.call_args[0][1]
                assert "siedemnasta" in text

    def test_keyboard_interrupt(self):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:00"]):
            with mock.patch.object(clock, "speak", side_effect=KeyboardInterrupt):
                clock.main()  # should not raise

    def test_classic_12_hour(self):
        from horavox import clock

        with mock.patch.object(
            sys, "argv", ["vox clock", "--debug", "--exit", "--time", "17:00", "--lang", "pl"]
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                text = mock_speak.call_args[0][1]
                assert "piąta" in text  # 12-hour idiomatic

    def test_beep_count_full_hour(self):
        from horavox import clock

        with mock.patch.object(
            sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:00", "--lang", "en"]
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                _, kwargs = mock_speak.call_args
                assert kwargs.get("beep_count") == 2

    def test_beep_count_half_hour(self):
        from horavox import clock

        with mock.patch.object(
            sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:30", "--freq", "30"]
        ):
            with mock.patch.object(clock, "speak") as mock_speak:
                clock.main()
                _, kwargs = mock_speak.call_args
                assert kwargs.get("beep_count") == 1

    def test_background_mode(self):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--background", "--nosound"]):
            with mock.patch.object(clock, "Daemonize") as mock_daemon:
                mock_instance = mock.MagicMock()
                mock_daemon.return_value = mock_instance
                clock.main()
                mock_daemon.assert_called_once()
                mock_instance.start.assert_called_once()

    def test_run_clock_exit_mode_directly(self):
        """Test run_clock --exit path with a mock args object."""
        import datetime

        from horavox import clock as clock_mod
        from horavox.clock import run_clock

        core.configure(debug=True)
        lang_data, lang = core.load_language_data("en", "classic")
        args = mock.MagicMock()
        args.freq = 60
        args.exit = True
        args.time = "12:00"
        args.voice = None
        now = datetime.datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        time_offset = now - datetime.datetime.now()
        with mock.patch.object(clock_mod, "speak") as mock_speak:
            run_clock(args, lang, lang_data, time_offset, 0, 1439)
            mock_speak.assert_called_once()

    def test_parse_args_defaults(self):
        from horavox.clock import parse_args

        with mock.patch.object(sys, "argv", ["vox clock"]):
            args = parse_args()
        assert args.freq == 60
        assert args.mode == "classic"
        assert args.volume == 100
        assert args.background is False

    def test_parse_args_all_options(self):
        from horavox.clock import parse_args

        with mock.patch.object(
            sys,
            "argv",
            [
                "vox clock",
                "--lang",
                "pl",
                "--voice",
                "test",
                "--mode",
                "modern",
                "--start",
                "9",
                "--end",
                "22",
                "--freq",
                "30",
                "--time",
                "12:00",
                "--exit",
                "--background",
                "--verbose",
                "--volume",
                "50",
            ],
        ):
            args = parse_args()
        assert args.lang == "pl"
        assert args.voice == "test"
        assert args.mode == "modern"
        assert args.freq == 30
        assert args.exit is True
        assert args.background is True

    def test_run_clock_loop_one_tick(self):
        """Test the main loop fires once then breaks via side effect."""
        import datetime

        from horavox import clock as clock_mod
        from horavox.clock import run_clock

        core.configure(debug=True)
        lang_data, lang = core.load_language_data("en", "classic")
        args = mock.MagicMock()
        args.freq = 60
        args.exit = False
        args.time = None
        args.voice = None
        # Set time to exactly 12:00:00 so the loop fires immediately
        now = datetime.datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        time_offset = now - datetime.datetime.now()
        call_count = [0]

        def fake_sleep(t):
            call_count[0] += 1
            if call_count[0] > 3:
                raise KeyboardInterrupt

        with mock.patch.object(clock_mod, "speak"):
            with mock.patch.object(clock_mod, "prepare_speech"):
                with mock.patch.object(clock_mod, "play_speech"):
                    with mock.patch.object(clock_mod, "play_beep"):
                        with mock.patch.object(clock_mod.time, "sleep", side_effect=fake_sleep):
                            try:
                                run_clock(args, lang, lang_data, time_offset, 0, 1439)
                            except KeyboardInterrupt:
                                pass
        assert call_count[0] > 0

    def test_exception_logs_error(self):
        from horavox import clock

        with mock.patch.object(sys, "argv", ["vox clock", "--debug", "--exit", "--time", "12:00"]):
            with mock.patch.object(clock, "speak", side_effect=RuntimeError("boom")):
                with mock.patch.object(clock, "log_error") as mock_log:
                    with pytest.raises(RuntimeError):
                        clock.main()
                    mock_log.assert_called_once()


# ==================== voice.py ====================


class TestVoiceCommand:
    def test_list_flag(self, capsys):
        from horavox import voice

        with mock.patch.object(sys, "argv", ["vox voice", "--list", "--lang", "pl"]):
            voice.main()
        out = capsys.readouterr().out
        assert "pl_PL" in out

    def test_list_unknown_lang(self, capsys):
        from horavox import voice

        with mock.patch.object(sys, "argv", ["vox voice", "--list", "--lang", "zz"]):
            voice.main()
        out = capsys.readouterr().out
        assert "No voices found" in out

    def test_list_has_installed_marker(self, capsys):
        from horavox import voice

        with mock.patch.object(core, "is_voice_installed", return_value=True):
            with mock.patch.object(sys, "argv", ["vox voice", "--list", "--lang", "pl"]):
                voice.main()
        out = capsys.readouterr().out
        assert "[*]" in out

    def test_interactive_no_voices(self, capsys):
        from horavox import voice

        with mock.patch.object(sys, "argv", ["vox voice", "--lang", "zz"]):
            voice.main()
        out = capsys.readouterr().out
        assert "No voices found" in out

    def test_get_lang_name(self):
        from horavox.voice import get_lang_name

        name = get_lang_name("en")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_lang_name_unknown(self):
        from horavox.voice import get_lang_name

        name = get_lang_name("zz")
        assert name == "zz"

    def test_cmd_list(self, capsys):
        from horavox.voice import cmd_list

        cmd_list("pl")
        out = capsys.readouterr().out
        assert "pl_PL" in out
        assert "Quality" in out

    def test_cmd_list_no_voices(self, capsys):
        from horavox.voice import cmd_list

        cmd_list("zz")
        out = capsys.readouterr().out
        assert "No voices found" in out

    def test_render_list(self):
        from horavox.voice import render_list

        voices = [
            {"key": "test_voice", "quality": "medium", "size_mb": 60, "installed": True},
            {"key": "other_voice", "quality": "high", "size_mb": 100, "installed": False},
        ]
        lines = render_list(voices, 0, "Test", "tt")
        text = "\n".join(lines)
        assert "test_voice" in text
        assert "other_voice" in text
        assert "[*]" in text
        assert ">" in text

    def test_progress_bar(self, capsys):
        from horavox.voice import progress_bar

        progress_bar("test.onnx", 5, 1024, 10240)
        # Just verify it doesn't crash; output goes to stdout

    def test_progress_bar_zero_total(self):
        from horavox.voice import progress_bar

        progress_bar("test.onnx", 0, 0, 0)  # should return early

    def test_progress_bar_complete(self, capsys):
        from horavox.voice import progress_bar

        progress_bar("test.onnx", 10, 1024, 10240)  # 100%

    def test_render_list_no_status(self):
        from horavox.voice import render_list

        voices = [{"key": "v1", "quality": "low", "size_mb": 30, "installed": False}]
        lines = render_list(voices, 0, "Test", "tt")
        assert any("v1" in line for line in lines)
        assert not any("status" in line.lower() for line in lines)

    def test_render_list_with_status(self):
        from horavox.voice import render_list

        voices = [{"key": "v1", "quality": "low", "size_mb": 30, "installed": False}]
        lines = render_list(voices, 0, "Test", "tt", status="Done!")
        assert any("Done!" in line for line in lines)

    def test_draw(self, capsys):
        from horavox.voice import draw

        draw(["line1", "line2"], 0)
        out = capsys.readouterr().out
        assert "line1" in out
        assert "line2" in out

    def test_draw_overwrite(self, capsys):
        from horavox.voice import draw

        draw(["first"], 0)
        draw(["second"], 1)
        out = capsys.readouterr().out
        assert "second" in out

    def test_parse_args_list(self):
        from horavox.voice import parse_args

        with mock.patch.object(sys, "argv", ["vox voice", "--list", "--lang", "en"]):
            args = parse_args()
        assert args.list_voices is True
        assert args.lang == "en"

    def test_parse_args_no_args_default(self):
        from horavox.voice import parse_args

        with mock.patch.object(sys, "argv", ["vox voice", "--lang", "en"]):
            args = parse_args()
        assert args.list_voices is False

    def test_keyboard_interrupt(self):
        from horavox import voice

        with mock.patch.object(sys, "argv", ["vox voice", "--lang", "zz"]):
            # No voices = early return, won't crash
            voice.main()

    def test_exception_logs(self):
        from horavox import voice

        with mock.patch.object(sys, "argv", ["vox voice", "--list", "--lang", "en"]):
            with mock.patch.object(voice, "cmd_list", side_effect=RuntimeError("boom")):
                with mock.patch.object(voice, "log_error"):
                    with pytest.raises(RuntimeError):
                        voice.main()

    def test_cmd_list_output(self, capsys):
        from horavox.voice import cmd_list

        cmd_list("en")
        out = capsys.readouterr().out
        assert "en_US" in out or "en_GB" in out
        assert "Quality" in out

    def test_getch_regular_key(self):
        from horavox.voice import getch

        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.return_value = "q"
            with mock.patch("termios.tcgetattr", return_value=[]):
                with mock.patch("termios.tcsetattr"):
                    with mock.patch("tty.setraw"):
                        result = getch()
        assert result == "q"

    def test_getch_arrow_up(self):
        from horavox.voice import getch

        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\x1b", "[", "A"]
            with mock.patch("termios.tcgetattr", return_value=[]):
                with mock.patch("termios.tcsetattr"):
                    with mock.patch("tty.setraw"):
                        result = getch()
        assert result == "UP"

    def test_getch_arrow_down(self):
        from horavox.voice import getch

        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\x1b", "[", "B"]
            with mock.patch("termios.tcgetattr", return_value=[]):
                with mock.patch("termios.tcsetattr"):
                    with mock.patch("tty.setraw"):
                        result = getch()
        assert result == "DOWN"

    def test_getch_escape_other(self):
        from horavox.voice import getch

        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            mock_stdin.read.side_effect = ["\x1b", "x"]
            with mock.patch("termios.tcgetattr", return_value=[]):
                with mock.patch("termios.tcsetattr"):
                    with mock.patch("tty.setraw"):
                        result = getch()
        assert result is None

    def test_cmd_interactive_quit(self):
        """Test interactive mode exits on 'q' key."""
        from horavox import voice

        voices = [
            {"key": "test_v", "quality": "medium", "size_mb": 60, "installed": False},
        ]
        with mock.patch.object(sys, "argv", ["vox voice", "--lang", "en"]):
            with mock.patch.object(voice, "list_voices_for_language", return_value=voices):
                with mock.patch.object(voice, "get_lang_name", return_value="English"):
                    with mock.patch.object(voice, "getch", return_value="q"):
                        with mock.patch.object(voice, "draw"):
                            voice.cmd_interactive("en")

    def test_cmd_interactive_install(self):
        """Test interactive mode installs on 'i' key then quits."""
        from horavox import voice

        voices = [
            {"key": "test_v", "quality": "medium", "size_mb": 60, "installed": False},
        ]
        call_count = [0]

        def fake_getch():
            call_count[0] += 1
            if call_count[0] == 1:
                return "i"
            return "q"

        with mock.patch.object(sys, "argv", ["vox voice", "--lang", "en"]):
            with mock.patch.object(voice, "list_voices_for_language", return_value=voices):
                with mock.patch.object(voice, "get_lang_name", return_value="English"):
                    with mock.patch.object(voice, "getch", side_effect=fake_getch):
                        with mock.patch.object(voice, "draw"):
                            with mock.patch.object(voice, "download_voice") as mock_dl:
                                voice.cmd_interactive("en")
                                mock_dl.assert_called_once_with(
                                    "test_v", progress_cb=voice.progress_bar
                                )
        assert voices[0]["installed"] is True

    def test_cmd_interactive_uninstall(self):
        """Test interactive mode uninstalls on 'u' key then quits."""
        from horavox import voice

        voices = [
            {"key": "test_v", "quality": "medium", "size_mb": 60, "installed": True},
        ]
        call_count = [0]

        def fake_getch():
            call_count[0] += 1
            if call_count[0] == 1:
                return "u"
            return "q"

        with mock.patch.object(voice, "list_voices_for_language", return_value=voices):
            with mock.patch.object(voice, "get_lang_name", return_value="English"):
                with mock.patch.object(voice, "getch", side_effect=fake_getch):
                    with mock.patch.object(voice, "draw"):
                        with mock.patch.object(voice, "uninstall_voice") as mock_rm:
                            voice.cmd_interactive("en")
                            mock_rm.assert_called_once_with("test_v")
        assert voices[0]["installed"] is False

    def test_cmd_interactive_already_installed(self):
        """Pressing 'i' on installed voice shows status."""
        from horavox import voice

        voices = [
            {"key": "v", "quality": "medium", "size_mb": 60, "installed": True},
        ]
        call_count = [0]

        def fake_getch():
            call_count[0] += 1
            if call_count[0] == 1:
                return "i"
            return "q"

        with mock.patch.object(voice, "list_voices_for_language", return_value=voices):
            with mock.patch.object(voice, "get_lang_name", return_value="Test"):
                with mock.patch.object(voice, "getch", side_effect=fake_getch):
                    with mock.patch.object(voice, "draw"):
                        with mock.patch.object(voice, "download_voice") as mock_dl:
                            voice.cmd_interactive("en")
                            mock_dl.assert_not_called()

    def test_cmd_interactive_not_installed_uninstall(self):
        """Pressing 'u' on not-installed voice shows status."""
        from horavox import voice

        voices = [
            {"key": "v", "quality": "medium", "size_mb": 60, "installed": False},
        ]
        call_count = [0]

        def fake_getch():
            call_count[0] += 1
            if call_count[0] == 1:
                return "u"
            return "q"

        with mock.patch.object(voice, "list_voices_for_language", return_value=voices):
            with mock.patch.object(voice, "get_lang_name", return_value="Test"):
                with mock.patch.object(voice, "getch", side_effect=fake_getch):
                    with mock.patch.object(voice, "draw"):
                        with mock.patch.object(voice, "uninstall_voice") as mock_rm:
                            voice.cmd_interactive("en")
                            mock_rm.assert_not_called()
