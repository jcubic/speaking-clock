"""Unit tests for registry, service subcommands, and service manager."""

import json
import os
import sys
import tempfile
from unittest import mock

import pytest

# ==================== registry.py ====================


class TestRegistry:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="horavox-test-reg-")
        self.registry_path = os.path.join(self.tmpdir, "data.json")
        self._patch_path = mock.patch("horavox.registry.REGISTRY_PATH", self.registry_path)
        self._patch_user = mock.patch("horavox.registry.USER_DIR", self.tmpdir)
        self._patch_path.start()
        self._patch_user.start()

    def teardown_method(self):
        self._patch_path.stop()
        self._patch_user.stop()

    def test_list_empty_no_file(self):
        from horavox.registry import list_instances
        assert list_instances() == []

    def test_add_and_list(self):
        from horavox.registry import add_instance, list_instances
        entry = add_instance("clock --lang pl --freq 30")
        assert entry["command"] == "clock --lang pl --freq 30"
        assert len(entry["id"]) == 6
        assert "installed_at" in entry
        instances = list_instances()
        assert len(instances) == 1
        assert instances[0]["id"] == entry["id"]

    def test_add_multiple(self):
        from horavox.registry import add_instance, list_instances
        add_instance("clock --lang pl")
        add_instance("clock --lang en")
        assert len(list_instances()) == 2

    def test_remove_instance(self):
        from horavox.registry import add_instance, list_instances, remove_instance
        e1 = add_instance("clock --lang pl")
        e2 = add_instance("clock --lang en")
        assert remove_instance(e1["id"]) is True
        instances = list_instances()
        assert len(instances) == 1
        assert instances[0]["id"] == e2["id"]

    def test_remove_nonexistent(self):
        from horavox.registry import remove_instance
        assert remove_instance("zzzzzz") is False

    def test_remove_all(self):
        from horavox.registry import add_instance, list_instances, remove_all
        add_instance("clock --lang pl")
        add_instance("clock --lang en")
        count = remove_all()
        assert count == 2
        assert list_instances() == []

    def test_delete_all_empty(self):
        from horavox.registry import remove_all
        assert remove_all() == 0

    def test_get_instance(self):
        from horavox.registry import add_instance, get_instance
        entry = add_instance("clock --lang pl")
        found = get_instance(entry["id"])
        assert found is not None
        assert found["command"] == "clock --lang pl"

    def test_get_instance_not_found(self):
        from horavox.registry import get_instance
        assert get_instance("zzzzzz") is None

    def test_persistence(self):
        from horavox.registry import add_instance
        add_instance("clock --lang pl")
        assert os.path.exists(self.registry_path)
        with open(self.registry_path, "r") as f:
            data = json.load(f)
        assert len(data["instances"]) == 1

    def test_unique_ids(self):
        from horavox.registry import add_instance
        ids = set()
        for _ in range(20):
            entry = add_instance("clock")
            ids.add(entry["id"])
        assert len(ids) == 20


# ==================== service add ====================


class TestServiceAdd:
    def test_add_help(self, capsys):
        from horavox.service import _parse_add_args
        with mock.patch.object(sys, "argv", ["vox service add", "--help"]):
            with pytest.raises(SystemExit) as exc:
                _parse_add_args()
            assert exc.value.code == 0

    def test_add_new_registers_and_starts(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = False
        with mock.patch.object(sys, "argv", ["vox service add", "clock --lang pl --freq 30"]):
            with mock.patch.object(service, "add_instance", return_value={"id": "aaa111", "command": "clock --lang pl --freq 30"}):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_add()
        out = capsys.readouterr().out
        assert "Installed instance aaa111" in out
        assert "registered and started" in out
        platform.register.assert_called_once()
        platform.start.assert_called_once()

    def test_add_existing_running_reloads(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        platform.is_running.return_value = True
        with mock.patch.object(sys, "argv", ["vox service add", "clock --lang en"]):
            with mock.patch.object(service, "add_instance", return_value={"id": "bbb222", "command": "clock --lang en"}):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_add()
        out = capsys.readouterr().out
        assert "reloaded" in out.lower()
        platform.reload.assert_called_once()

    def test_add_registered_but_stopped_starts(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        platform.is_running.return_value = False
        with mock.patch.object(sys, "argv", ["vox service add", "clock --lang en"]):
            with mock.patch.object(service, "add_instance", return_value={"id": "ccc333", "command": "clock --lang en"}):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_add()
        out = capsys.readouterr().out
        assert "started" in out.lower()
        platform.start.assert_called_once()

    def test_strips_background_flag(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = False
        captured_command = []

        def fake_add(command):
            captured_command.append(command)
            return {"id": "ddd444", "command": command}

        with mock.patch.object(sys, "argv", ["vox service add", "clock --background --lang pl"]):
            with mock.patch.object(service, "add_instance", side_effect=fake_add):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_add()
        assert "--background" not in captured_command[0]
        assert "clock --lang pl" == captured_command[0]


# ==================== service delete ====================


class TestServiceDelete:
    def test_delete_help(self, capsys):
        from horavox.service import _parse_delete_args
        with mock.patch.object(sys, "argv", ["vox service delete", "--help"]):
            with pytest.raises(SystemExit) as exc:
                _parse_delete_args()
            assert exc.value.code == 0

    def test_delete_by_id(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox service delete", "abc123"]):
            with mock.patch.object(service, "remove_instance", return_value=True):
                with mock.patch.object(service, "list_instances", return_value=[{"id": "other"}]):
                    with mock.patch.object(service, "get_platform", return_value=platform):
                        service._cmd_delete()
        out = capsys.readouterr().out
        assert "Removed instance abc123" in out
        platform.reload.assert_called_once()

    def test_delete_by_id_not_found(self, capsys):
        from horavox import service
        with mock.patch.object(sys, "argv", ["vox service delete", "zzzzzz"]):
            with mock.patch.object(service, "remove_instance", return_value=False):
                with pytest.raises(SystemExit) as exc:
                    service._cmd_delete()
                assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "No instance with ID" in out

    def test_delete_last_unregisters(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox service delete", "abc123"]):
            with mock.patch.object(service, "remove_instance", return_value=True):
                with mock.patch.object(service, "list_instances", return_value=[]):
                    with mock.patch.object(service, "get_platform", return_value=platform):
                        service._cmd_delete()
        out = capsys.readouterr().out
        assert "unregistered" in out.lower()
        platform.unregister.assert_called_once()

    def test_delete_all(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox service delete", "--all"]):
            with mock.patch.object(service, "remove_all", return_value=3):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_delete()
        out = capsys.readouterr().out
        assert "Removed 3 instances" in out
        assert "unregistered" in out.lower()
        platform.unregister.assert_called_once()

    def test_delete_all_singular(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox service delete", "--all"]):
            with mock.patch.object(service, "remove_all", return_value=1):
                with mock.patch.object(service, "get_platform", return_value=platform):
                    service._cmd_delete()
        out = capsys.readouterr().out
        assert "Removed 1 instance." in out

    def test_delete_all_empty(self, capsys):
        from horavox import service
        with mock.patch.object(sys, "argv", ["vox service delete", "--all"]):
            with mock.patch.object(service, "remove_all", return_value=0):
                service._cmd_delete()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_delete_no_args_empty(self, capsys):
        from horavox import service
        with mock.patch.object(sys, "argv", ["vox service delete"]):
            with mock.patch.object(service, "list_instances", return_value=[]):
                service._cmd_delete()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_delete_interactive_select(self, capsys):
        from horavox import service
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
            {"id": "bbb222", "command": "clock --lang en"},
        ]
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox service delete"]):
            with mock.patch.object(service, "list_instances") as mock_list:
                mock_list.side_effect = [instances, [instances[1]]]
                with mock.patch.object(service, "remove_instance", return_value=True):
                    with mock.patch.object(service, "get_platform", return_value=platform):
                        with mock.patch("inquirer.prompt", return_value={"instance": "aaa111"}):
                            service._cmd_delete()
        out = capsys.readouterr().out
        assert "Removed instance aaa111" in out

    def test_delete_interactive_cancel(self, capsys):
        from horavox import service
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
        ]
        with mock.patch.object(sys, "argv", ["vox service delete"]):
            with mock.patch.object(service, "list_instances", return_value=instances):
                with mock.patch.object(service, "remove_instance") as mock_rm:
                    with mock.patch("inquirer.prompt", return_value=None):
                        service._cmd_delete()
                    mock_rm.assert_not_called()

    def test_delete_interactive_keyboard_interrupt(self):
        from horavox import service
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
        ]
        with mock.patch.object(sys, "argv", ["vox service delete"]):
            with mock.patch.object(service, "list_instances", return_value=instances):
                with mock.patch("inquirer.prompt", side_effect=KeyboardInterrupt):
                    service._cmd_delete()

    def test_parse_args_id(self):
        from horavox.service import _parse_delete_args
        with mock.patch.object(sys, "argv", ["vox service delete", "abc123"]):
            args = _parse_delete_args()
        assert args.id == "abc123"
        assert args.remove_all is False

    def test_parse_args_all(self):
        from horavox.service import _parse_delete_args
        with mock.patch.object(sys, "argv", ["vox service delete", "--all"]):
            args = _parse_delete_args()
        assert args.remove_all is True


# ==================== service list ====================


class TestServiceList:
    def test_list_empty(self, capsys):
        from horavox import service
        with mock.patch.object(service, "list_instances", return_value=[]):
            service._cmd_list()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_list_with_instances(self, capsys):
        from horavox import service
        instances = [
            {"id": "abc123", "command": "clock --lang pl", "installed_at": "2026-05-05T10:00:00+00:00"},
            {"id": "def456", "command": "clock --lang en", "installed_at": "2026-05-05T11:00:00+00:00"},
        ]
        with mock.patch.object(service, "list_instances", return_value=instances):
            service._cmd_list()
        out = capsys.readouterr().out
        assert "abc123" in out
        assert "def456" in out
        assert "clock --lang pl" in out
        assert "clock --lang en" in out


# ==================== service start ====================


class TestServiceStart:
    def test_start_no_instances(self, capsys):
        from horavox import service
        with mock.patch.object(service, "list_instances", return_value=[]):
            with pytest.raises(SystemExit) as exc:
                service._cmd_start()
            assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_start_already_running(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        platform.is_running.return_value = True
        with mock.patch.object(service, "list_instances", return_value=[{"id": "aaa"}]):
            with mock.patch.object(service, "get_platform", return_value=platform):
                service._cmd_start()
        out = capsys.readouterr().out
        assert "already running" in out

    def test_start_registers_if_needed(self, capsys):
        from horavox import service
        platform = mock.MagicMock()
        platform.is_registered.return_value = False
        platform.is_running.return_value = False
        with mock.patch.object(service, "list_instances", return_value=[{"id": "aaa"}]):
            with mock.patch.object(service, "get_platform", return_value=platform):
                service._cmd_start()
        platform.register.assert_called_once()
        platform.start.assert_called_once()


# ==================== service dispatch ====================


class TestServiceDispatch:
    def test_help_no_args(self, capsys):
        from horavox import service
        with mock.patch.object(sys, "argv", ["vox service"]):
            service._main()
        out = capsys.readouterr().out
        assert "add" in out
        assert "delete" in out
        assert "list" in out
        assert "start" in out

    def test_help_flag(self, capsys):
        from horavox import service
        with mock.patch.object(sys, "argv", ["vox service", "--help"]):
            service._main()
        out = capsys.readouterr().out
        assert "Usage:" in out

    def test_unknown_subcommand(self, capsys):
        from horavox import service
        with pytest.raises(SystemExit) as exc:
            with mock.patch.object(sys, "argv", ["vox service", "bogus"]):
                service._main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "Unknown subcommand" in out

    def test_keyboard_interrupt(self):
        from horavox import service
        with mock.patch.object(service, "_main", side_effect=KeyboardInterrupt):
            service.main()

    def test_exception_logs_error(self):
        from horavox import service
        with mock.patch.object(service, "_main", side_effect=RuntimeError("boom")):
            with mock.patch.object(service, "log_error") as mock_log:
                with pytest.raises(RuntimeError):
                    service.main()
                mock_log.assert_called_once()


# ==================== service manager (run) ====================


class TestServiceManager:
    def test_reconcile_starts_new(self):
        from horavox.service import _reconcile
        children = {}
        instances = [{"id": "aaa", "command": "clock --lang pl"}]
        with mock.patch("horavox.service.list_instances", return_value=instances):
            with mock.patch("horavox.service.subprocess.Popen") as mock_popen:
                mock_popen.return_value = mock.MagicMock()
                with mock.patch("horavox.service.log_to_file"):
                    _reconcile("/usr/bin/vox", children)
        assert "aaa" in children
        mock_popen.assert_called_once()

    def test_reconcile_stops_removed(self):
        from horavox.service import _reconcile
        proc = mock.MagicMock()
        proc.poll.return_value = None
        children = {"old_id": proc}
        with mock.patch("horavox.service.list_instances", return_value=[]):
            with mock.patch("horavox.service.log_to_file"):
                _reconcile("/usr/bin/vox", children)
        assert "old_id" not in children
        proc.terminate.assert_called_once()

    def test_reconcile_keeps_existing(self):
        from horavox.service import _reconcile
        proc = mock.MagicMock()
        children = {"aaa": proc}
        instances = [{"id": "aaa", "command": "clock --lang pl"}]
        with mock.patch("horavox.service.list_instances", return_value=instances):
            with mock.patch("horavox.service.log_to_file"):
                _reconcile("/usr/bin/vox", children)
        assert children["aaa"] is proc

    def test_stop_child_terminate(self):
        from horavox.service import _stop_child
        proc = mock.MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        children = {"aaa": proc}
        _stop_child(children, "aaa")
        assert "aaa" not in children
        proc.terminate.assert_called_once()

    def test_stop_child_kill_on_timeout(self):
        import subprocess

        from horavox.service import _stop_child
        proc = mock.MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = subprocess.TimeoutExpired("vox", 10)
        children = {"aaa": proc}
        _stop_child(children, "aaa")
        proc.kill.assert_called_once()

    def test_stop_child_already_dead(self):
        from horavox.service import _stop_child
        proc = mock.MagicMock()
        proc.poll.return_value = 0
        children = {"aaa": proc}
        _stop_child(children, "aaa")
        proc.terminate.assert_not_called()

    def test_stop_child_missing_id(self):
        from horavox.service import _stop_child
        children = {}
        _stop_child(children, "nonexistent")

    def test_stop_all(self):
        from horavox.service import _stop_all
        proc1 = mock.MagicMock()
        proc1.poll.return_value = None
        proc1.wait.return_value = 0
        proc2 = mock.MagicMock()
        proc2.poll.return_value = None
        proc2.wait.return_value = 0
        children = {"aaa": proc1, "bbb": proc2}
        _stop_all(children)
        assert len(children) == 0
        proc1.terminate.assert_called_once()
        proc2.terminate.assert_called_once()

    def test_check_children_restarts_exited(self):
        from horavox.service import _check_children
        proc = mock.MagicMock()
        proc.poll.return_value = 1
        children = {"aaa": proc}
        instances = [{"id": "aaa", "command": "clock --lang pl"}]
        with mock.patch("horavox.service.list_instances", return_value=instances):
            with mock.patch("horavox.service.subprocess.Popen") as mock_popen:
                new_proc = mock.MagicMock()
                mock_popen.return_value = new_proc
                with mock.patch("horavox.service.log_to_file"):
                    _check_children("/usr/bin/vox", children)
        assert children["aaa"] is new_proc

    def test_check_children_removes_orphan(self):
        from horavox.service import _check_children
        proc = mock.MagicMock()
        proc.poll.return_value = 1
        children = {"aaa": proc}
        with mock.patch("horavox.service.list_instances", return_value=[]):
            with mock.patch("horavox.service.log_to_file"):
                _check_children("/usr/bin/vox", children)
        assert "aaa" not in children

    def test_check_children_ignores_running(self):
        from horavox.service import _check_children
        proc = mock.MagicMock()
        proc.poll.return_value = None
        children = {"aaa": proc}
        instances = [{"id": "aaa", "command": "clock --lang pl"}]
        with mock.patch("horavox.service.list_instances", return_value=instances):
            with mock.patch("horavox.service.log_to_file"):
                _check_children("/usr/bin/vox", children)
        assert children["aaa"] is proc

    def test_start_child_oserror(self):
        from horavox.service import _start_child
        children = {}
        with mock.patch("horavox.service.subprocess.Popen", side_effect=OSError("no such file")):
            with mock.patch("horavox.service.log_to_file") as mock_log:
                _start_child("/nonexistent/vox", children, "aaa", "clock")
        assert "aaa" not in children
        mock_log.assert_called()


# ==================== main.py dispatcher ====================


class TestMainDispatcherService:
    def test_dispatches_to_service(self):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox", "service"]):
            with mock.patch("horavox.service.main") as m:
                main()
                m.assert_called_once()

    def test_help_shows_service(self, capsys):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox"]):
            main()
        out = capsys.readouterr().out
        assert "service" in out
        assert "install" not in out or "service" in out


# ==================== platforms/__init__.py ====================


class TestPlatformDetection:
    def test_linux(self):
        with mock.patch("sys.platform", "linux"):
            from horavox.platforms import get_platform
            plat = get_platform()
            assert hasattr(plat, "register")
            assert hasattr(plat, "unregister")
            assert hasattr(plat, "start")
            assert hasattr(plat, "stop")
            assert hasattr(plat, "reload")
            assert hasattr(plat, "is_registered")
            assert hasattr(plat, "is_running")

    def test_unsupported(self):
        with mock.patch("sys.platform", "freebsd"):
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                from horavox import platforms
                platforms.get_platform()
