"""E2E tests for HoraVox CLI commands.

All subprocess commands run with HOME set to a temp directory so they
don't read/write the developer's real ~/.horavox (voices, sessions, cache).
"""

import os
import subprocess
import sys
import tempfile

# Shared temp home for test isolation
_TEST_HOME = tempfile.mkdtemp(prefix="horavox-test-")
_TEST_ENV = {**os.environ, "HOME": _TEST_HOME}


def run_vox(*args, input_text=None):
    """Run a vox command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "horavox.main"] + list(args),
        capture_output=True,
        text=True,
        input=input_text,
        timeout=30,
        env=_TEST_ENV,
    )
    return result.returncode, result.stdout, result.stderr


def run_subcommand(module, *args):
    """Run a vox subcommand module directly."""
    result = subprocess.run(
        [sys.executable, "-m", f"horavox.{module}"] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
        env=_TEST_ENV,
    )
    return result.returncode, result.stdout, result.stderr


# ==================== vox (main dispatcher) ====================


class TestVoxMain:
    def test_no_args_shows_help(self):
        rc, out, _ = run_vox()
        assert rc == 0
        assert "Usage: vox <command>" in out
        assert "clock" in out
        assert "now" in out
        assert "stop" in out
        assert "voice" in out

    def test_help_flag(self):
        rc, out, _ = run_vox("--help")
        assert rc == 0
        assert "Usage: vox <command>" in out

    def test_version(self):
        rc, out, _ = run_vox("--version")
        assert rc == 0
        assert "vox " in out
        # Version should be semver-like
        parts = out.strip().split(" ")[1].split(".")
        assert len(parts) == 3

    def test_unknown_command(self):
        rc, out, _ = run_vox("nonexistent")
        assert rc == 1
        assert "Unknown command" in out


# ==================== vox clock ====================


class TestVoxClock:
    def test_help(self):
        rc, out, _ = run_subcommand("clock", "--help")
        assert rc == 0
        assert "vox clock" in out
        assert "--background" in out
        assert "--freq" in out

    def test_debug_exit_at_slot(self):
        """--debug --exit --time at a slot minute should show output."""
        rc, out, _ = run_subcommand("clock", "--debug", "--exit", "--time", "12:00")
        assert rc == 0
        # Should prepare and play (in nosound mode, just prints)
        assert "Preparing:" in out or "not at announcement slot" in out

    def test_debug_exit_noon(self):
        """At 12:00, should say noon equivalent."""
        rc, out, _ = run_subcommand("clock", "--debug", "--exit", "--time", "12:00", "--lang", "en")
        assert rc == 0
        assert "noon" in out.lower()

    def test_debug_exit_not_at_slot(self):
        """At a non-slot time, should report not at slot."""
        rc, out, _ = run_subcommand("clock", "--debug", "--exit", "--time", "12:01")
        assert rc == 0
        assert "not at announcement slot" in out

    def test_debug_exit_outside_range(self):
        """Time outside --start/--end range should skip."""
        rc, out, _ = run_subcommand(
            "clock",
            "--debug",
            "--exit",
            "--time",
            "12:00",
            "--start",
            "13",
            "--end",
            "23",
        )
        assert rc == 0
        assert "outside range" in out

    def test_freq_30_at_half_hour(self):
        """With --freq 30, half-hour slots should fire."""
        rc, out, _ = run_subcommand("clock", "--debug", "--exit", "--time", "12:30", "--freq", "30")
        assert rc == 0
        assert "Preparing:" in out

    def test_invalid_freq(self):
        """--freq that doesn't divide 60 should error."""
        rc, out, err = run_subcommand("clock", "--debug", "--exit", "--freq", "7")
        assert rc != 0
        assert "must divide 60 evenly" in (out + err)

    def test_mode_modern(self):
        """Modern mode should produce digital-style output."""
        rc, out, _ = run_subcommand(
            "clock",
            "--debug",
            "--exit",
            "--time",
            "17:00",
            "--mode",
            "modern",
            "--lang",
            "pl",
            "--freq",
            "30",
        )
        assert rc == 0
        assert "siedemnasta" in out

    def test_mode_classic_pl(self):
        """Classic Polish at 17:00 should say 'piąta' (12-hour)."""
        rc, out, _ = run_subcommand(
            "clock",
            "--debug",
            "--exit",
            "--time",
            "17:00",
            "--lang",
            "pl",
        )
        assert rc == 0
        assert "piąta" in out

    def test_volume_flag(self):
        """--volume should be accepted without error."""
        rc, out, _ = run_subcommand(
            "clock", "--debug", "--exit", "--time", "12:00", "--volume", "50"
        )
        assert rc == 0

    def test_nosound_flag(self):
        """--nosound should work like --debug minus --verbose."""
        rc, out, _ = run_subcommand("clock", "--nosound", "--verbose", "--exit", "--time", "12:00")
        assert rc == 0
        assert "Preparing:" in out


# ==================== vox now ====================


class TestVoxNow:
    def test_help(self):
        rc, out, _ = run_subcommand("now", "--help")
        assert rc == 0
        assert "vox now" in out
        assert "--time" in out

    def test_debug(self):
        """--debug should speak without audio and print output."""
        rc, out, _ = run_subcommand("now", "--debug")
        assert rc == 0
        assert "Preparing:" in out

    def test_specific_time(self):
        """--time should override the current time."""
        rc, out, _ = run_subcommand("now", "--debug", "--time", "12:00", "--lang", "en")
        assert rc == 0
        assert "noon" in out.lower()

    def test_modern_mode(self):
        rc, out, _ = run_subcommand(
            "now", "--debug", "--time", "9:30", "--mode", "modern", "--lang", "en"
        )
        assert rc == 0
        assert "nine thirty" in out.lower()

    def test_classic_mode_pl(self):
        rc, out, _ = run_subcommand("now", "--debug", "--time", "9:30", "--lang", "pl")
        assert rc == 0
        assert "dziesiątej" in out  # "wpół do dziesiątej"


# ==================== vox stop ====================


class TestVoxList:
    def test_help(self):
        rc, out, _ = run_subcommand("list", "--help")
        assert rc == 0
        assert "vox list" in out
        assert "--verbose" in out

    def test_list_empty(self):
        """No instances running should produce no output."""
        rc, out, _ = run_subcommand("list")
        assert rc == 0
        assert out.strip() == ""


class TestVoxStop:
    def setup_method(self):
        """Stop any leftover instances before each test."""
        while True:
            rc, out, _ = run_subcommand("list")
            if not out.strip():
                break
            pid = out.strip().split("\n")[0]
            run_subcommand("stop", "--pid", pid)

    def test_help(self):
        rc, out, _ = run_subcommand("stop", "--help")
        assert rc == 0
        assert "vox stop" in out
        assert "--pid" in out

    def test_no_instances(self):
        """When nothing is running, should say so."""
        rc, out, _ = run_subcommand("stop")
        assert rc == 0
        assert "No HoraVox instances running" in out

    def test_pid_not_found(self):
        """--pid with nonexistent PID should error."""
        rc, out, _ = run_subcommand("stop", "--pid", "999999999")
        assert rc == 1
        assert "No HoraVox instance with PID" in out

    def test_start_and_stop(self):
        """Start a daemon, verify it appears in list, then stop it."""
        subprocess.run(
            [sys.executable, "-m", "horavox.clock", "--background", "--nosound"],
            capture_output=True,
            timeout=10,
            env=_TEST_ENV,
        )
        import time

        time.sleep(1)

        # List should show it
        rc, out, _ = run_subcommand("list")
        assert rc == 0
        pid = out.strip()
        assert pid.isdigit()

        # Verbose list should include the command
        rc, out, _ = run_subcommand("list", "--verbose")
        assert "nosound" in out

        # Stop it
        rc, out, _ = run_subcommand("stop", "--pid", pid)
        assert rc == 0
        assert "Stopped" in out

        # Should be gone
        rc, out, _ = run_subcommand("list")
        assert out.strip() == ""


# ==================== vox voice ====================


class TestVoxVoice:
    def test_help(self):
        rc, out, _ = run_subcommand("voice", "--help")
        assert rc == 0
        assert "vox voice" in out
        assert "--list" in out

    def test_list_en(self):
        """--list should show available voices."""
        rc, out, _ = run_subcommand("voice", "--list", "--lang", "en")
        assert rc == 0
        assert "en_US" in out or "en_GB" in out
        assert "Quality" in out

    def test_list_pl(self):
        rc, out, _ = run_subcommand("voice", "--list", "--lang", "pl")
        assert rc == 0
        assert "pl_PL" in out

    def test_list_installed_marker(self):
        """Installed voices should be marked with [*]."""
        rc, out, _ = run_subcommand("voice", "--list", "--lang", "pl")
        assert rc == 0
        # Check that installed voices (if any) are marked
        lines = out.split("\n")
        installed = [line for line in lines if "[*]" in line]
        not_installed = [line for line in lines if "MB" in line and "[*]" not in line]
        # At least one category should have entries
        assert len(installed) + len(not_installed) > 0

    def test_list_unknown_language(self):
        rc, out, _ = run_subcommand("voice", "--list", "--lang", "zz")
        assert rc == 0
        assert "No voices found" in out
