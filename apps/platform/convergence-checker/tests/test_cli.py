from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from convergence_checker import cli as cli_module
from convergence_checker.cli import cli


class _BootCallRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, dry_run: bool) -> None:
        self.calls.append({"dry_run": dry_run})


@pytest.fixture
def boot_recorder(monkeypatch: pytest.MonkeyPatch) -> _BootCallRecorder:
    recorder = _BootCallRecorder()
    monkeypatch.setattr(cli_module, "boot_and_run", recorder)
    return recorder


class TestCli:
    def test_no_flag_invokes_boot_with_dry_run_false(self, boot_recorder: _BootCallRecorder) -> None:
        result = CliRunner().invoke(cli, [])
        assert result.exit_code == 0, result.output
        assert boot_recorder.calls == [{"dry_run": False}]

    def test_dry_run_flag_invokes_boot_with_dry_run_true(self, boot_recorder: _BootCallRecorder) -> None:
        result = CliRunner().invoke(cli, ["--dry-run"])
        assert result.exit_code == 0, result.output
        assert boot_recorder.calls == [{"dry_run": True}]
