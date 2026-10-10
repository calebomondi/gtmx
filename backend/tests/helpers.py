"""Test data builders shared by backend tests."""

import uuid

from backend.app.api.deps import AuthUser


def make_user(name: str) -> AuthUser:
    return AuthUser(id=uuid.uuid4(), email=f"{name.lower()}@example.com", name=name, avatar_url=None)
