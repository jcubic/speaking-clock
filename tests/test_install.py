"""Unit tests for registry, install, remove, and service modules."""

import json
import os
import sys
import tempfile
from unittest import mock

import pytest

from horavox import core


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

    def test_remove_all_empty(self):
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


# ==================== install.py ====================


class TestInstallCommand:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="horavox-test-inst-")
        self.registry_path = os.path.join(self.tmpdir, "data.json")

    def _patch_registry(self):
        return (
            mock.patch("horavox.registry.REGISTRY_PATH", self.registry_path),
            mock.patch("horavox.registry.USER_DIR", self.tmpdir),
            mock.patch("horavox.install.list_instances", wraps=self._list),
            mock.patch("horavox.install.add_instance", wraps=self._add),
        )

    def _list(self):
        from horavox.registry import list_instances
        return list_instances()

    def _add(self, command):
        from horavox.registry import add_instance
        return add_instance(command)

    def test_install_help(self, capsys):
        from horavox.install import parse_args
        with mock.patch.object(sys, "argv", ["vox install", "--help"]):
            with pytest.raises(SystemExit) as exc:
                parse_args()
            assert exc.value.code == 0

    def test_list_empty(self, capsys):
        from horavox import install
        with mock.patch.object(sys, "argv", ["vox install", "--list"]):
            with mock.patch.object(install, "list_instances", return_value=[]):
                install.main()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_list_with_instances(self, capsys):
        from horavox import install
        instances = [
            {"id": "abc123", "command": "clock --lang pl", "installed_at": "2026-05-05T10:00:00+00:00"},
            {"id": "def456", "command": "clock --lang en", "installed_at": "2026-05-05T11:00:00+00:00"},
        ]
        with mock.patch.object(sys, "argv", ["vox install", "--list"]):
            with mock.patch.object(install, "list_instances", return_value=instances):
                install.main()
        out = capsys.readouterr().out
        assert "abc123" in out
        assert "def456" in out
        assert "clock --lang pl" in out
        assert "clock --lang en" in out

    def test_no_command_error(self, capsys):
        from horavox import install
        with mock.patch.object(sys, "argv", ["vox install"]):
            with pytest.raises(SystemExit) as exc:
                install.main()
            assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "Error" in out

    def test_install_new_registers_and_starts(self, capsys):
        from horavox import install
        platform = mock.MagicMock()
        platform.is_registered.return_value = False
        with mock.patch.object(sys, "argv", ["vox install", "clock --lang pl --freq 30"]):
            with mock.patch.object(install, "add_instance", return_value={"id": "aaa111", "command": "clock --lang pl --freq 30"}):
                with mock.patch.object(install, "get_platform", return_value=platform):
                    install.main()
        out = capsys.readouterr().out
        assert "Installed instance aaa111" in out
        assert "registered and started" in out
        platform.register.assert_called_once()
        platform.start.assert_called_once()

    def test_install_existing_running_reloads(self, capsys):
        from horavox import install
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        platform.is_running.return_value = True
        with mock.patch.object(sys, "argv", ["vox install", "clock --lang en"]):
            with mock.patch.object(install, "add_instance", return_value={"id": "bbb222", "command": "clock --lang en"}):
                with mock.patch.object(install, "get_platform", return_value=platform):
                    install.main()
        out = capsys.readouterr().out
        assert "reloaded" in out.lower()
        platform.reload.assert_called_once()

    def test_install_registered_but_stopped_starts(self, capsys):
        from horavox import install
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        platform.is_running.return_value = False
        with mock.patch.object(sys, "argv", ["vox install", "clock --lang en"]):
            with mock.patch.object(install, "add_instance", return_value={"id": "ccc333", "command": "clock --lang en"}):
                with mock.patch.object(install, "get_platform", return_value=platform):
                    install.main()
        out = capsys.readouterr().out
        assert "started" in out.lower()
        platform.start.assert_called_once()

    def test_strips_background_flag(self, capsys):
        from horavox import install
        platform = mock.MagicMock()
        platform.is_registered.return_value = False
        captured_command = []

        def fake_add(command):
            captured_command.append(command)
            return {"id": "ddd444", "command": command}

        with mock.patch.object(sys, "argv", ["vox install", "clock --background --lang pl"]):
            with mock.patch.object(install, "add_instance", side_effect=fake_add):
                with mock.patch.object(install, "get_platform", return_value=platform):
                    install.main()
        assert "--background" not in captured_command[0]
        assert "clock --lang pl" == captured_command[0]

    def test_keyboard_interrupt(self):
        from horavox import install
        with mock.patch.object(sys, "argv", ["vox install", "--list"]):
            with mock.patch.object(install, "list_instances", side_effect=KeyboardInterrupt):
                install.main()

    def test_exception_logs_error(self):
        from horavox import install
        with mock.patch.object(sys, "argv", ["vox install", "--list"]):
            with mock.patch.object(install, "list_instances", side_effect=RuntimeError("boom")):
                with mock.patch.object(install, "log_error") as mock_log:
                    with pytest.raises(RuntimeError):
                        install.main()
                    mock_log.assert_called_once()


# ==================== remove.py ====================


class TestRemoveCommand:
    def test_remove_help(self, capsys):
        from horavox.remove import parse_args
        with mock.patch.object(sys, "argv", ["vox remove", "--help"]):
            with pytest.raises(SystemExit) as exc:
                parse_args()
            assert exc.value.code == 0

    def test_remove_by_id(self, capsys):
        from horavox import remove
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox remove", "abc123"]):
            with mock.patch.object(remove, "remove_instance", return_value=True):
                with mock.patch.object(remove, "list_instances", return_value=[{"id": "other"}]):
                    with mock.patch.object(remove, "get_platform", return_value=platform):
                        remove.main()
        out = capsys.readouterr().out
        assert "Removed instance abc123" in out
        platform.reload.assert_called_once()

    def test_remove_by_id_not_found(self, capsys):
        from horavox import remove
        with mock.patch.object(sys, "argv", ["vox remove", "zzzzzz"]):
            with mock.patch.object(remove, "remove_instance", return_value=False):
                with pytest.raises(SystemExit) as exc:
                    remove.main()
                assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "No instance with ID" in out

    def test_remove_last_unregisters(self, capsys):
        from horavox import remove
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox remove", "abc123"]):
            with mock.patch.object(remove, "remove_instance", return_value=True):
                with mock.patch.object(remove, "list_instances", return_value=[]):
                    with mock.patch.object(remove, "get_platform", return_value=platform):
                        remove.main()
        out = capsys.readouterr().out
        assert "unregistered" in out.lower()
        platform.unregister.assert_called_once()

    def test_remove_all(self, capsys):
        from horavox import remove
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            with mock.patch.object(remove, "remove_all", return_value=3):
                with mock.patch.object(remove, "get_platform", return_value=platform):
                    remove.main()
        out = capsys.readouterr().out
        assert "Removed 3 instances" in out
        assert "unregistered" in out.lower()
        platform.unregister.assert_called_once()

    def test_remove_all_singular(self, capsys):
        from horavox import remove
        platform = mock.MagicMock()
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            with mock.patch.object(remove, "remove_all", return_value=1):
                with mock.patch.object(remove, "get_platform", return_value=platform):
                    remove.main()
        out = capsys.readouterr().out
        assert "Removed 1 instance." in out

    def test_remove_all_empty(self, capsys):
        from horavox import remove
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            with mock.patch.object(remove, "remove_all", return_value=0):
                remove.main()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_remove_no_args_empty(self, capsys):
        from horavox import remove
        with mock.patch.object(sys, "argv", ["vox remove"]):
            with mock.patch.object(remove, "list_instances", return_value=[]):
                remove.main()
        out = capsys.readouterr().out
        assert "No installed instances" in out

    def test_remove_interactive_select(self, capsys):
        from horavox import remove
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
            {"id": "bbb222", "command": "clock --lang en"},
        ]
        platform = mock.MagicMock()
        platform.is_running.return_value = True
        platform.is_registered.return_value = True
        with mock.patch.object(sys, "argv", ["vox remove"]):
            with mock.patch.object(remove, "list_instances") as mock_list:
                mock_list.side_effect = [instances, [instances[1]]]
                with mock.patch.object(remove, "remove_instance", return_value=True):
                    with mock.patch.object(remove, "get_platform", return_value=platform):
                        with mock.patch("inquirer.prompt", return_value={"instance": "aaa111"}):
                            remove.main()
        out = capsys.readouterr().out
        assert "Removed instance aaa111" in out

    def test_remove_interactive_cancel(self, capsys):
        from horavox import remove
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
        ]
        with mock.patch.object(sys, "argv", ["vox remove"]):
            with mock.patch.object(remove, "list_instances", return_value=instances):
                with mock.patch.object(remove, "remove_instance") as mock_rm:
                    with mock.patch("inquirer.prompt", return_value=None):
                        remove.main()
                    mock_rm.assert_not_called()

    def test_remove_interactive_keyboard_interrupt(self):
        from horavox import remove
        instances = [
            {"id": "aaa111", "command": "clock --lang pl"},
        ]
        with mock.patch.object(sys, "argv", ["vox remove"]):
            with mock.patch.object(remove, "list_instances", return_value=instances):
                with mock.patch("inquirer.prompt", side_effect=KeyboardInterrupt):
                    remove.main()

    def test_keyboard_interrupt(self):
        from horavox import remove
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            with mock.patch.object(remove, "remove_all", side_effect=KeyboardInterrupt):
                remove.main()

    def test_exception_logs_error(self):
        from horavox import remove
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            with mock.patch.object(remove, "remove_all", side_effect=RuntimeError("boom")):
                with mock.patch.object(remove, "log_error") as mock_log:
                    with pytest.raises(RuntimeError):
                        remove.main()
                    mock_log.assert_called_once()

    def test_parse_args_id(self):
        from horavox.remove import parse_args
        with mock.patch.object(sys, "argv", ["vox remove", "abc123"]):
            args = parse_args()
        assert args.id == "abc123"
        assert args.remove_all is False

    def test_parse_args_all(self):
        from horavox.remove import parse_args
        with mock.patch.object(sys, "argv", ["vox remove", "--all"]):
            args = parse_args()
        assert args.remove_all is True


# ==================== service.py ====================


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


# ==================== main.py dispatcher ====================


class TestMainDispatcherNewCommands:
    def test_dispatches_to_install(self):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox", "install"]):
            with mock.patch("horavox.install.main") as m:
                main()
                m.assert_called_once()

    def test_dispatches_to_remove(self):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox", "remove"]):
            with mock.patch("horavox.remove.main") as m:
                main()
                m.assert_called_once()

    def test_dispatches_to_service(self):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox", "service"]):
            with mock.patch("horavox.service.main") as m:
                main()
                m.assert_called_once()

    def test_help_shows_new_commands(self, capsys):
        from horavox.main import main
        with mock.patch.object(sys, "argv", ["vox"]):
            main()
        out = capsys.readouterr().out
        assert "install" in out
        assert "remove" in out
        assert "service" in out


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
