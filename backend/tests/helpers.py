"""Test data builders shared by backend tests."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from backend.app.api.deps import AuthUser


def make_user(name: str, *, is_admin: bool = False) -> AuthUser:
    return AuthUser(
        id=uuid.uuid4(), email=f"{name.lower()}@example.com", name=name, avatar_url=None, is_admin=is_admin,
    )


class FakeSupabase:
    """Just enough of supabase.auth.admin for the admin services: list, get
    and update users (app_metadata and ban_duration)."""

    def __init__(self, users):
        self.users = {str(u.id): u for u in users}
        self.auth = SimpleNamespace(admin=self)

    async def list_users(self, page, per_page):
        items = list(self.users.values())
        return items[(page - 1) * per_page: page * per_page]

    async def get_user_by_id(self, uid):
        if uid not in self.users:
            raise LookupError(f"no user {uid}")
        return SimpleNamespace(user=self.users[uid])

    async def update_user_by_id(self, uid, attributes):
        user = self.users[uid]
        if "app_metadata" in attributes:
            user.app_metadata = attributes["app_metadata"]
        if "ban_duration" in attributes:
            user.banned_until = None if attributes["ban_duration"] == "none" else datetime(2999, 1, 1, tzinfo=UTC)


def supabase_user(uid, email, app_metadata=None):
    return SimpleNamespace(id=str(uid), email=email, app_metadata=app_metadata or {}, user_metadata={},
                           created_at=None, last_sign_in_at=None, banned_until=None)
