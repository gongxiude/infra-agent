# -*- coding: utf-8 -*-

"""CLI 模式测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from infra_agent.cli.interactive_shell import start_interactive_shell
from infra_agent.cli.configuration.models import CliConfig
from infra_agent.cli.mode import local as local_mode
from infra_agent.cli.mode.remote.client import RemoteClient


@patch("builtins.input", side_effect=["请修改 Jenkinsfile", "exit"])
def test_local_mode_accepts_natural_language(fake_input) -> None:
    """本地模式应支持直接输入自然语言。"""

    with patch.object(local_mode, "build_local_service") as builder:
        service = MagicMock()
        service.signal_router.from_user_chat.return_value = MagicMock(
            id="task-1",
            type="chat",
            context=MagicMock(model_dump=MagicMock(return_value={})),
        )
        async def submit_task(task):
            return None
        async def run_once():
            return {"final_output": "ok"}
        service.submit_task = submit_task
        service.run_once = run_once
        builder.return_value = service
        local_mode.run_local_mode()
    assert fake_input.call_count == 2


@patch("infra_agent.cli.mode.remote.client.request.urlopen")
def test_remote_client_submit_chat(urlopen) -> None:
    """远端客户端应调用 /chat。"""

    response = MagicMock()
    response.read.return_value = b'{"task_id":"remote-1"}'
    urlopen.return_value.__enter__.return_value = response
    client = RemoteClient(CliConfig())
    result = client.submit_chat("你好", context=MagicMock(repository_alias=None, session_id=None))
    assert result["task_id"] == "remote-1"


@patch("sys.stdin.isatty", return_value=False)
@patch("infra_agent.cli.interactive_shell.ensure_required_config")
@patch("infra_agent.cli.interactive_shell.print_global_banner")
@patch("infra_agent.cli.mode.local.run_local_mode")
def test_interactive_shell_falls_back_to_local_in_non_tty(
    run_local_mode_mock,
    print_banner_mock,
    ensure_required_config_mock,
    isatty_mock,
) -> None:
    """非交互环境应直接进入本地模式。"""

    start_interactive_shell()
    print_banner_mock.assert_called_once()
    ensure_required_config_mock.assert_called_once()
    isatty_mock.assert_called_once()
    run_local_mode_mock.assert_called_once()


@patch("sys.stdin.isatty", return_value=True)
@patch("infra_agent.cli.interactive_shell.ensure_required_config")
@patch("infra_agent.cli.interactive_shell.print_global_banner")
@patch("infra_agent.cli.interactive_shell.console")
@patch("infra_agent.cli.interactive_shell._select_mode", return_value="Exit")
def test_interactive_shell_can_exit_without_questionary_import_at_module_load(
    select_mode_mock,
    console_mock,
    print_banner_mock,
    ensure_required_config_mock,
    isatty_mock,
) -> None:
    """交互壳应支持惰性选择模式。"""

    start_interactive_shell()
    assert print_banner_mock.call_count == 2
    ensure_required_config_mock.assert_called_once()
    isatty_mock.assert_called_once()
    select_mode_mock.assert_called_once()
    console_mock.print.assert_called()
