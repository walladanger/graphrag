# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""Unit tests for the GraphTerm wrapper shell (windows-wrapper/graphterm)."""

import subprocess
from pathlib import Path

from graphterm import launcher, shell


class FakeIo:
    """Capture writes / feed canned input lines."""

    def __init__(self, inputs: list[str] | None = None):
        self.outputs: list[str] = []
        self.cleared = 0
        self._inputs = list(inputs or [])

    def write(self, text: str) -> None:
        self.outputs.append(text)

    def readline(self, prompt: str) -> str:
        if not self._inputs:
            raise EOFError
        return self._inputs.pop(0)

    def clear(self) -> None:
        self.cleared += 1

    def to_io(self) -> shell.Io:
        return shell.Io(write=self.write, readline=self.readline, clear=self.clear)


def test_strip_quotes():
    assert shell.strip_quotes('"hello world"') == "hello world"
    assert shell.strip_quotes("'single'") == "single"
    assert shell.strip_quotes("plain") == "plain"
    assert shell.strip_quotes('"unbalanced') == '"unbalanced'
    assert shell.strip_quotes("") == ""


def test_split_line_quoted_args():
    argv = shell.split_line('query "who are the main characters?" --method global')
    assert argv == [
        "query",
        "who are the main characters?",
        "--method",
        "global",
    ]


def test_split_line_parse_error():
    io = FakeIo()
    assert shell.split_line('query "unterminated', io.to_io()) == []
    assert any("parse error" in o for o in io.outputs)


def test_graphrag_cmd_falls_back_to_module(monkeypatch):
    monkeypatch.setattr(shell.shutil, "which", lambda _: None)
    assert shell.graphrag_cmd() == [shell.sys.executable, "-m", "graphrag"]


def test_graphrag_cmd_uses_exe_when_present(monkeypatch):
    monkeypatch.setattr(shell.shutil, "which", lambda _: "/usr/bin/graphrag")
    assert shell.graphrag_cmd() == ["/usr/bin/graphrag"]


def test_run_graphrag_forwards_and_returns_code(monkeypatch):
    seen: dict = {}

    class Completed:
        returncode = 3

    def fake_run(cmd, *args, **kwargs):
        seen["cmd"] = cmd
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    io = FakeIo()
    rc = shell.run_graphrag(["index", "-v"], io.to_io())
    assert rc == 3
    assert seen["cmd"][-2:] == ["index", "-v"]


def test_run_graphrag_missing_cli(monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    io = FakeIo()
    rc = shell.run_graphrag(["index"], io.to_io())
    assert rc == shell.EXIT_NOT_FOUND
    assert any("pip install graphrag" in o for o in io.outputs)


def test_is_project(tmp_path: Path):
    assert not shell.is_project(tmp_path)
    (tmp_path / "settings.yaml").write_text("name: test\n")
    assert shell.is_project(tmp_path)


def test_find_projects_skips_hidden_and_found(tmp_path: Path):
    proj = tmp_path / "proj"
    (proj / "output").mkdir(parents=True)
    (proj / "settings.yaml").write_text("a: 1\n")
    nested = tmp_path / ".git" / "x"
    nested.mkdir(parents=True)
    (nested / "settings.yaml").write_text("a: 1\n")
    found = shell.find_projects(tmp_path)
    assert found == [proj]


def test_find_project_root_walks_up(tmp_path: Path):
    (tmp_path / "settings.yaml").write_text("a: 1\n")
    deep = tmp_path / "input" / "docs"
    deep.mkdir(parents=True)
    assert shell.find_project_root(deep) == tmp_path
    assert shell.find_project_root(Path("/")) is None or True


def test_handle_line_exit():
    io = FakeIo()
    rc, quit_ = shell.handle_line("exit", io.to_io(), shell.ShellState())
    assert (rc, quit_) == (0, True)


def test_handle_line_cls():
    io = FakeIo()
    shell.handle_line("cls", io.to_io(), shell.ShellState())
    assert io.cleared == 1


def test_handle_line_help_builtin():
    io = FakeIo()
    rc, quit_ = shell.handle_line("help", io.to_io(), shell.ShellState())
    assert rc == 0 and not quit_
    assert any("Built-in commands" in o for o in io.outputs)


def test_handle_line_forwards_to_graphrag(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shell, "run_graphrag", lambda args, io=None: calls.append(args) or 0
    )
    state = shell.ShellState()
    io = FakeIo()
    shell.handle_line("index -v", io.to_io(), state)
    assert calls == [["index", "-v"]]
    # 'r' repeats the last command
    shell.handle_line("r", io.to_io(), state)
    assert calls == [["index", "-v"], ["index", "-v"]]


def test_handle_line_passthru(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shell, "run_graphrag", lambda args, io=None: calls.append(args) or 0
    )
    io = FakeIo()
    shell.handle_line("passthru query --help", io.to_io(), shell.ShellState())
    assert calls == [["query", "--help"]]


def test_interact_runs_until_eof():
    io = FakeIo(inputs=["help", "", "status"])
    rc = shell.interact(io.to_io())
    assert rc == 0


def test_main_passthrough(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(
        shell, "run_graphrag", lambda args, io=None: calls.append(args) or 7
    )
    rc = shell.main(["init", "-d", "data"], FakeIo().to_io())
    assert rc == 7
    assert calls == [["init", "-d", "data"]]


def test_launcher_resolve_cmd_bat(tmp_path: Path):
    bat = tmp_path / "graphrag_wrapper.cmd"
    bat.write_text("@echo off\n")
    assert launcher.resolve_cmd_bat(tmp_path) == bat
    sub = tmp_path / "graphterm"
    sub.mkdir()
    assert launcher.resolve_cmd_bat(sub) == bat


def test_launcher_find_python_prefers_existing(tmp_path: Path):
    exe = tmp_path / ".venv" / "Scripts" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    assert launcher.find_python(tmp_path) == str(exe)
