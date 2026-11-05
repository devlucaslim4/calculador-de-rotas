"""Configuração da API por variáveis de ambiente e secrets locais."""

from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from checklist_api import DEFAULT_CATEGORY_ID, DEFAULT_TIMEZONE


ITEM_ENV_NAMES = {
    "odometer_start_item_id": "CHECKLIST_ITEM_ODOMETER_START_ID",
    "odometer_end_item_id": "CHECKLIST_ITEM_ODOMETER_END_ID",
    "reason_item_id": "CHECKLIST_ITEM_REASON_ID",
    "cost_center_item_id": "CHECKLIST_ITEM_COST_CENTER_ID",
    "gps_start_item_id": "CHECKLIST_ITEM_GPS_START_ID",
    "gps_end_item_id": "CHECKLIST_ITEM_GPS_END_ID",
}


def _integer(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _local_streamlit_settings() -> dict[str, object]:
    """Reaproveita secrets locais sem depender do runtime do Streamlit."""

    path = Path(".streamlit/secrets.toml")
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    section = data.get("checklist_facil", {})
    return dict(section) if isinstance(section, dict) else {}


@dataclass(frozen=True)
class ApiSettings:
    inbound_api_key: str
    file_signing_secret: str
    checklist_api_token: str
    category_id: int = DEFAULT_CATEGORY_ID
    timezone_name: str = DEFAULT_TIMEZONE
    item_mapping: dict[str, int] | None = None
    public_api_base_url: str = ""
    file_ttl_seconds: int = 900
    max_generated_file_mb: int = 25
    temp_directory: Path = Path(tempfile.gettempdir()) / "calculador_rotas_api"

    @classmethod
    def from_environment(cls) -> "ApiSettings":
        local = _local_streamlit_settings()
        local_items = local.get("items", {})
        if not isinstance(local_items, dict):
            local_items = {}

        mapping: dict[str, int] = {}
        for field, env_name in ITEM_ENV_NAMES.items():
            mapping[field] = _integer(
                os.getenv(env_name, local_items.get(field, 0)),
                0,
            )

        timezone_name = os.getenv(
            "CHECKLIST_FACIL_TIMEZONE",
            str(local.get("timezone", DEFAULT_TIMEZONE)),
        ).strip()
        try:
            ZoneInfo(timezone_name)
        except Exception:
            timezone_name = DEFAULT_TIMEZONE

        ttl = max(60, min(_integer(os.getenv("FILE_TTL_SECONDS"), 900), 86_400))
        max_file_mb = max(1, min(_integer(os.getenv("MAX_GENERATED_FILE_MB"), 25), 100))
        temp_value = os.getenv("API_TEMP_DIRECTORY", "").strip()
        temp_directory = (
            Path(temp_value).expanduser()
            if temp_value
            else Path(tempfile.gettempdir()) / "calculador_rotas_api"
        )
        return cls(
            inbound_api_key=os.getenv("ROUTES_API_KEY", "").strip(),
            file_signing_secret=os.getenv("FILE_SIGNING_SECRET", "").strip(),
            checklist_api_token=os.getenv(
                "CHECKLIST_FACIL_API_TOKEN",
                str(local.get("api_token", "")),
            ).strip(),
            category_id=_integer(
                os.getenv("CHECKLIST_FACIL_CATEGORY_ID", local.get("category_id")),
                DEFAULT_CATEGORY_ID,
            ),
            timezone_name=timezone_name,
            item_mapping=mapping,
            public_api_base_url=os.getenv("PUBLIC_API_BASE_URL", "").strip().rstrip("/"),
            file_ttl_seconds=ttl,
            max_generated_file_mb=max_file_mb,
            temp_directory=temp_directory,
        )

    @property
    def ready(self) -> bool:
        return bool(
            self.inbound_api_key
            and self.file_signing_secret
            and self.checklist_api_token
            and self.public_api_base_url
        )

    @property
    def missing_settings(self) -> list[str]:
        missing = []
        if not self.inbound_api_key:
            missing.append("ROUTES_API_KEY")
        if not self.file_signing_secret:
            missing.append("FILE_SIGNING_SECRET")
        if not self.checklist_api_token:
            missing.append("CHECKLIST_FACIL_API_TOKEN")
        if not self.public_api_base_url:
            missing.append("PUBLIC_API_BASE_URL")
        return missing

