# -*- coding: utf-8 -*-

"""运行时配置。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from infra_agent.config.paths import data_dir, project_root

# 启动时加载 .env.local 和 .env（.env 优先级更高，后加载覆盖前者）
_root = project_root()
load_dotenv(_root / ".env.local", override=False)
load_dotenv(_root / ".env", override=True)


class GitSettings(BaseModel):
    """Git 工作区配置。"""

    remote_repositories: dict[str, str] = Field(default_factory=dict)
    workspace_root: Path = Path(".workspaces")
    workspace_directories: list[Path] = Field(default_factory=lambda: [Path(".workspaces")])
    default_branch: str = "main"


class RuntimeSettings(BaseModel):
    """运行时配置。"""

    model: str = "gpt-5.4"
    worker_name: str = "infra-agent-worker"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    session_database_path: Path = Field(default_factory=lambda: data_dir() / "agent_sessions.sqlite3")


class AppSettings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_prefix="INFRA_AGENT_",
        extra="ignore",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
    )

    app_name: str = "infra-agent"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    git: GitSettings = Field(default_factory=GitSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从环境变量加载配置。"""

        settings = cls()
        # 兼容 OPENAI_API_KEY 和 INFRA_AGENT_OPENAI_API_KEY
        if not settings.openai_api_key:
            settings.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        # 兼容 OPENAI_BASE_URL
        if not settings.openai_base_url:
            settings.openai_base_url = os.getenv("OPENAI_BASE_URL", "")
        repositories = _load_json("AGENT_GIT_REMOTE_REPOSITORIES")
        workspace_root = os.getenv("AGENT_GIT_WORKSPACE_ROOT", "").strip()
        workspace_directories = _load_json("AGENT_GIT_WORKSPACE_DIRECTORIES")
        if isinstance(repositories, dict):
            settings.git.remote_repositories = {
                str(key): str(value) for key, value in repositories.items()
            }
        if workspace_root:
            settings.git.workspace_root = Path(workspace_root)
        if isinstance(workspace_directories, list) and workspace_directories:
            settings.git.workspace_directories = [Path(str(item)) for item in workspace_directories]
        elif not settings.git.workspace_directories:
            settings.git.workspace_directories = [settings.git.workspace_root]
        return settings


def _load_json(name: str) -> dict | list | None:
    """读取 JSON 环境变量。"""

    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return json.loads(raw)


def get_settings() -> AppSettings:
    """返回应用配置。"""

    return AppSettings.from_env()
