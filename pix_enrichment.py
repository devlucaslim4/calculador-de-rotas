"""Correspondência conservadora entre usuários do checklist e dados PIX recebidos."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


class PixDataMissingError(ValueError):
    """A ação SharePoint do agente não enviou os dados para enriquecer o Excel."""


def normalize_identity(value: object) -> str:
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9@._+-]+", "", text.casefold())


def checklist_user_aliases(users: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Cria aliases exatos (email/login/nome) por nome de exibição do Checklist."""
    aliases: dict[str, set[str]] = {}
    identity_fields = ("email", "emailAddress", "username", "userName", "login", "name")
    for user in users:
        if not isinstance(user, dict):
            continue
        display_name = normalize_identity(user.get("name"))
        if not display_name:
            continue
        values = aliases.setdefault(display_name, set())
        for field in identity_fields:
            identity = normalize_identity(user.get(field))
            if identity:
                values.add(identity)
    return aliases


def build_pix_index(records: list[dict[str, str]]) -> dict[str, set[str]]:
    """Índice de usuário, preservando conflitos para não associar PIX incorreto."""
    index: dict[str, set[str]] = {}
    for record in records:
        identity = normalize_identity(record.get("usuario"))
        pix = str(record.get("pix", "")).strip()
        if identity and pix:
            index.setdefault(identity, set()).add(pix)
    return index


def find_unambiguous_pix(
    display_name: object,
    aliases: dict[str, set[str]],
    index: dict[str, set[str]],
) -> str | None:
    name_key = normalize_identity(display_name)
    identity_keys = aliases.get(name_key, {name_key} if name_key else set())
    matches = {
        next(iter(index[key]))
        for key in identity_keys
        if key in index and len(index[key]) == 1
    }
    return next(iter(matches)) if len(matches) == 1 else None
