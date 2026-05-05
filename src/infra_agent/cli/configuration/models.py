# -*- coding: utf-8 -*-

"""CLI 配置模型。"""

from pydantic import BaseModel, Field


class RemoteConfig(BaseModel):
    """远端配置。"""

    base_url: str = "http://127.0.0.1:8000"


class CliConfig(BaseModel):
    """CLI 配置。"""

    remote: RemoteConfig = Field(default_factory=RemoteConfig)
