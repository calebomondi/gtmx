"""Tenant isolation: every route under another user's Lace answers as if it
did not exist, and changes nothing. Walks the Lace router's own routes, so a
new route that forgets the ownership dependency fails here."""

import re
import uuid

from backend.app.api.v1.endpoints.lace_members import router as members_router
from backend.app.api.v1.endpoints.laces import router as laces_router
from backend.tests.helpers import make_user
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture

_PARAM = re.compile(r"\{(\w+)\}")


def _lace_routes(lace_id: str) -> list[tuple[str, str]]:
    """(method, path) of every route under /laces/{lace_id}, with its other
    path parameters filled with random ids."""
    out = []
    for route in [*laces_router.routes, *members_router.routes]:
        if not route.path.startswith("/{lace_id}"):
            continue
        filled = _PARAM.sub(lambda m: lace_id if m[1] == "lace_id" else str(uuid.uuid4()), route.path)
        out += [(method, f"/laces{filled}") for method in route.methods - {"HEAD", "OPTIONS"}]
    return out


def test_another_users_lace_is_invisible_on_every_route(client, user, lace):  # noqa: F811
    routes = _lace_routes(lace)
    assert len(routes) > 30  # the walk found the Lace's routes
    before = client.get(f"{API}/laces/{lace}").json()
    client.sign_in(make_user("Intruder"))
    for method, path in routes:
        response = client.request(method, API + path, json={})
        if method == "GET":
            assert response.status_code == 404, f"{method} {path} -> {response.status_code}"
        else:
            assert response.status_code in (404, 422), f"{method} {path} -> {response.status_code} {response.text}"
    client.sign_in(user)
    assert client.get(f"{API}/laces/{lace}").json() == before
