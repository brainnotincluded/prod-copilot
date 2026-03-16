"""Lightweight role-based authorization via X-User-Role header.

Design for an internal tool behind a reverse proxy / API gateway:
- The gateway authenticates the user (SSO, LDAP, etc.)
- The gateway sets X-User-Role header based on the user's group
- The backend trusts this header and enforces permissions

Three roles (hierarchical):
  viewer  — read-only: browse endpoints, view maps, search, view stats
  editor  — viewer + upload specs, run queries/chat
  admin   — editor + delete specs, approve/reject confirmations

If no header is provided, defaults to "editor" (dev mode).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)


class Role(str, enum.Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


# Hierarchical weight: higher = more permissions
_ROLE_WEIGHT = {Role.VIEWER: 0, Role.EDITOR: 1, Role.ADMIN: 2}


@dataclass(frozen=True)
class CurrentUser:
    """Represents the current request's user context."""
    role: Role


def get_current_user(request: Request) -> CurrentUser:
    """Extract user role from X-User-Role header.

    If header is missing or invalid, defaults to editor (internal tool,
    no login required for dev/demo). In production the API gateway
    always sets this header.
    """
    raw = request.headers.get("X-User-Role", "editor").lower().strip()
    try:
        role = Role(raw)
    except ValueError:
        role = Role.EDITOR
    return CurrentUser(role=role)


def require_role(min_role: Role) -> Callable:
    """FastAPI dependency: reject if the user's role is below min_role.

    Usage::

        @router.post("/upload")
        async def upload(user: CurrentUser = Depends(require_role(Role.EDITOR))):
            ...
    """
    min_weight = _ROLE_WEIGHT[min_role]

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if _ROLE_WEIGHT[user.role] < min_weight:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role '{min_role.value}' or higher. Current: '{user.role.value}'.",
            )
        return user

    return _check
