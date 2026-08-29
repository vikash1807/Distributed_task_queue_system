from __future__ import annotations
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """All configurations, read from environment with defaults."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra='ignore',
        populate_by_name=True
    )

    redis_addr: str = Field("localhost:6379", validation_alias="REDIS_ADDR")
    redis_pass: str = Field("", validation_alias="REDIS_PASSWORD")
    server_port: int = Field(8080, validation_alias="SERVER_PORT")
    metrics_port: int = Field(9100, validation_alias="METRICS_PORT")

    worker_count: int = Field(5, validation_alias="WORKER_COUNT")

    # Validation
    @model_validator(mode="after")
    def _validate(self) -> Config:
        if not self.redis_addr:
            raise ValueError("config: REDIS_ADDR must not be empty")
        if not self.server_port:
            raise ValueError("config: SERVER_PORT must not be empty")
        if not self.metrics_port:
            raise ValueError("config: METRICS_PORT must not be empty")
        if self.worker_count <= 0:
            raise ValueError(f"config: WORKER_COUNT must be > 0, got {self.worker_count}")
        return self


def load_config() -> Config:
    """Read configuration from enviornment, apply defaults, and validate."""
    return Config()