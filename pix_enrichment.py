"""Associação conservadora entre usuários do Checklist Fácil e chaves PIX."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


class PixDataMissingError(ValueError):
    """A ação SharePoint do agente não enviou os dados para enriquecer o Excel."""


_PIX_PLACEHOLDERS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "nao informado",
    "nao possui",
    "sem chave",
    "null",
    "none",
    "0",
}
_IDENTITY_FIELDS = ("email", "emailAddress", "username", "userName", "login", "name")
_UUID_PIX = re.compile(
    r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?"
    r"[0-9a-f]{4}-?[0-9a-f]{12}$",
    re.IGNORECASE,
)


def normalize_identity(value: object) -> str:
    """Normaliza caixa, acentos e espaços sem apagar pontuação significativa."""

    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text).casefold().strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    if "@" in text:
        return re.sub(r"\s+", "", text)
    return " ".join(text.split())


def _normalize_pix(value: object) -> tuple[str, str] | None:
    """Retorna a chave canônica e a forma original para exibição no Excel."""

    original = "" if value is None else str(value).strip()
    placeholder = unicodedata.normalize("NFKD", original.casefold())
    placeholder = placeholder.encode("ascii", "ignore").decode()
    placeholder = " ".join(placeholder.split())
    if placeholder in _PIX_PLACEHOLDERS:
        return None

    # CPF, CNPJ e telefone podem chegar com ou sem pontuação no SharePoint.
    if re.fullmatch(r"[0-9() .+/-]+", original):
        digits = re.sub(r"\D", "", original)
        return (f"digits:{digits}", original) if digits else None

    # Chaves aleatórias UUID são insensíveis a caixa e hífens de formatação.
    compact = original.replace("-", "")
    if _UUID_PIX.fullmatch(original) or _UUID_PIX.fullmatch(compact):
        return (f"uuid:{compact.casefold()}", original)

    # E-mails são insensíveis a caixa; outras chaves são preservadas exatamente.
    if "@" in original:
        return (f"email:{original.casefold()}", original)
    return (f"text:{original}", original)


@dataclass
class ChecklistUserAliases:
    """Aliases separados por perfil para bloquear nomes e logins ambíguos."""

    profiles_by_display: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    profile_owners_by_alias: dict[str, set[str]] = field(default_factory=dict)


def checklist_user_aliases(users: list[dict[str, Any]]) -> ChecklistUserAliases:
    """Indexa perfis do Checklist sem fundir contas que compartilham um nome."""

    result = ChecklistUserAliases()
    for user in users:
        if not isinstance(user, dict):
            continue
        display_name = normalize_identity(user.get("name"))
        if not display_name:
            continue

        aliases = {
            identity
            for field_name in _IDENTITY_FIELDS
            if (identity := normalize_identity(user.get(field_name)))
        }
        aliases.add(display_name)
        user_id = user.get("userId", user.get("id"))
        profile_id = f"id:{user_id}" if user_id is not None else "aliases:" + "|".join(sorted(aliases))

        profile = result.profiles_by_display.setdefault(display_name, {}).setdefault(
            profile_id, set()
        )
        profile.update(aliases)
        for alias in aliases:
            result.profile_owners_by_alias.setdefault(alias, set()).add(profile_id)
    return result


def build_pix_index(
    records: list[dict[str, str]],
) -> dict[str, dict[str | None, str | None]]:
    """Indexa chaves e mantém conflitos/valores vazios para falhar de forma segura."""

    index: dict[str, dict[str | None, str | None]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = normalize_identity(record.get("usuario"))
        if not identity:
            continue
        normalized = _normalize_pix(record.get("pix"))
        canonical, original = normalized if normalized else (None, None)
        index.setdefault(identity, {}).setdefault(canonical, original)
    return index


def build_display_name_index(records: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Indexa nomes completos do SharePoint pela identidade Usuário."""

    index: dict[str, dict[str, str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = normalize_identity(record.get("usuario"))
        display_name = "" if record.get("nome") is None else str(record["nome"]).strip()
        normalized_name = normalize_identity(display_name)
        if identity and normalized_name:
            index.setdefault(identity, {}).setdefault(normalized_name, display_name)
    return index


def find_unambiguous_pix(
    display_name: object,
    aliases: ChecklistUserAliases,
    index: dict[str, dict[str | None, str | None]],
) -> str | None:
    """Retorna PIX somente quando perfil, alias e valor têm correspondência única."""

    name_key = normalize_identity(display_name)
    profiles = aliases.profiles_by_display.get(name_key, {})
    # Sem ID de usuário na linha do checklist, nomes repetidos não podem ser
    # distinguidos com segurança, mesmo que um dos perfis tenha e-mail cadastrado.
    if len(profiles) != 1:
        return None

    profile_id, identity_keys = next(iter(profiles.items()))
    matched: dict[str, str] = {}
    for identity in sorted(identity_keys):
        if aliases.profile_owners_by_alias.get(identity) != {profile_id}:
            continue
        values = index.get(identity)
        if not values:
            continue
        # Chave em branco ou várias chaves para o mesmo usuário bloqueiam a
        # associação; aliases alternativos não devem esconder esse conflito.
        if len(values) != 1 or None in values:
            return None
        canonical, original = next(iter(values.items()))
        if canonical is None or original is None:
            return None
        matched[canonical] = original

    if len(matched) != 1:
        return None
    return next(iter(matched.values()))


def find_unambiguous_display_name(
    display_name: object,
    aliases: ChecklistUserAliases,
    index: dict[str, dict[str, str]],
) -> str | None:
    """Retorna nome do SharePoint apenas se a identidade e o nome forem únicos."""

    name_key = normalize_identity(display_name)
    profiles = aliases.profiles_by_display.get(name_key, {})
    if len(profiles) != 1:
        return None

    profile_id, identity_keys = next(iter(profiles.items()))
    matched: dict[str, str] = {}
    for identity in sorted(identity_keys):
        if aliases.profile_owners_by_alias.get(identity) != {profile_id}:
            continue
        matched.update(index.get(identity, {}))

    return next(iter(matched.values())) if len(matched) == 1 else None
