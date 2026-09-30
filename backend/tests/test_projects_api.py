"""Phase-1 API tests: projects CRUD + ordering, workspace project membership,
and the archive/restore flows.

The venv has no pytest — run directly:

    .venv/bin/python backend/tests/test_projects_api.py

Uses an isolated temp SQLite database (never touches blog.db).
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid

# Make `backend.app.*` importable when run from the repo root tree.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from backend.app.api.v1.endpoints import projects, workspaces  # noqa: E402
from backend.app.database import models  # noqa: E402
from backend.app.database.connect import Base, get_db  # noqa: E402
from backend.app.naming import title_case  # noqa: E402

API_ROOT = "http://test/api/v1"
# NOTE: in this isolated app the routers are mounted at /projects and
# /workspaces (the real app adds the /api/v1 prefix). A base_url that itself
# carries a path (e.g. .../api/v1) breaks httpx resolution, so calls below use
# the mounted prefixes directly.


def _check_title_case() -> None:
    cases = {
        "acme corp": "Acme Corp",
        "GTMX analyst": "Gtmx Analyst",
        "api tool": "API Tool",
        "b2b saas crm": "B2B SaaS CRM",
        "  spaced out  name ": "Spaced Out Name",
        "": "",
        None: "",
    }
    for raw, expected in cases.items():
        actual = title_case(raw)
        assert actual == expected, f"title_case({raw!r}) = {actual!r}, expected {expected!r}"
    print("  title_case: ok")


def main() -> int:
    _check_title_case()

    tmp = tempfile.mkdtemp(prefix="gtmx-api-test-")
    db_path = os.path.join(tmp, "test.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def _init() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as db:
            user = models.User(id=uuid.uuid4(), name="Test User", email="test@example.com")
            db.add(user)
            await db.commit()
            user_id = user.id
        ws1 = await _seed_workspace(SessionLocal, user_id, name="Analytics Hub")
        ws2 = await _seed_workspace(SessionLocal, user_id, name="My App")
        return user_id, ws1, ws2

    user_id, ws1, ws2 = asyncio.run(_init())

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app = FastAPI()
    app.include_router(projects.router, prefix="/projects")
    app.include_router(workspaces.router, prefix="/workspaces")
    app.dependency_overrides[get_db] = override_get_db

    failures: list[str] = []

    def check(label: str, condition: bool, extra: str = "") -> None:
        if condition:
            print(f"  ok: {label}")
        else:
            failures.append(f"{label} {extra}".strip())
            print(f"  FAIL: {label} {extra}".strip())

    with TestClient(app, base_url="http://test") as client:
        # -- Project creation: title-case + uniqueness -----------------------
        r = client.post(f"/projects/user/{user_id}", json={"name": "acme corp"})
        check("create project returns 201", r.status_code == 201, f"(got {r.status_code})")
        project = r.json()
        project_id = project["id"]
        check("create project normalizes name", project["name"] == "Acme Corp")
        check("create project defaults to Other", project["priority"] is False)
        check("new project has 0 workspaces", project["workspace_count"] == 0)

        r = client.post(f"/projects/user/{user_id}", json={"name": "ACME CORP"})
        check(
            "duplicate project (case-insensitive) is 409",
            r.status_code == 409,
            f"(got {r.status_code}: {r.text})",
        )

        r = client.post(f"/projects/user/{user_id}", json={"name": "  "})
        check(
            "blank project name is 422",
            r.status_code == 422,
            f"(got {r.status_code})",
        )

        r = client.post(f"/projects/user/{user_id}", json={"name": "beta ltd"})
        check("second project created", r.status_code == 201)
        project2 = r.json()
        project2_id = project2["id"]

        # -- Listing ---------------------------------------------------------
        r = client.get(f"/projects/user/{user_id}")
        check("list live projects", r.status_code == 200 and len(r.json()) == 2)
        check(
            "live list includes both projects",
            {p["id"] for p in r.json()} == {project_id, project2_id},
        )

        # -- Append position (regression: a max position of 0 is falsy, so the
        #    second create used to land on a duplicate position 0) -----------
        r = client.post(f"/projects/user/{user_id}", json={"name": "gamma inc"})
        check("third project created", r.status_code == 201)
        project3 = r.json()
        positions = sorted(p["position"] for p in projects_list(client, user_id))
        check(
            "sequential creates get distinct ascending positions",
            positions == [0, 1, 2],
            f"(got {positions})",
        )
        check(
            "first project keeps position 0",
            project["position"] == 0,
            f"(got {project['position']})",
        )
        r = client.delete(f"/projects/{project3['id']}")
        check(
            "scratch project removed",
            r.status_code == 204,
            f"(got {r.status_code})",
        )

        # -- Workspace membership -------------------------------------------
        r = client.patch(
            f"/workspaces/{ws1}",
            json={"project_id": str(project_id)},
        )
        check(
            "workspace joins project",
            r.status_code == 200 and r.json().get("project_id") == str(project_id),
            f"(got {r.status_code})",
        )
        r = client.patch(
            f"/workspaces/{ws2}",
            json={"project_id": str(project_id)},
        )
        check("second workspace joins project", r.status_code == 200)

        r = client.patch(
            f"/workspaces/{ws1}",
            json={"project_id": str(uuid.uuid4())},
        )
        check(
            "linking to a foreign/unknown project is 404",
            r.status_code == 404,
            f"(got {r.status_code})",
        )
        # Confirm the failed link did not clobber the existing membership.
        r = client.get(f"/workspaces/user/{user_id}")
        ws_rows = {w["id"]: w for w in r.json()}
        check("failed link keeps prior project", ws_rows[str(ws1)]["project_id"] == project_id)

        r = client.patch(
            f"/workspaces/{ws1}",
            json={"name": "my great app"},
        )
        check(
            "rename title-cases workspace",
            r.status_code == 200 and r.json()["name"] == "My Great App",
        )

        r = client.get(f"/projects/{project_id}")
        detail = r.json()
        check("project detail is 200", r.status_code == 200)
        check(
            "detail has 2 member workspaces",
            detail.get("workspace_count") == 2,
            f"(got {detail.get('workspace_count')})",
        )
        member_ids = {w["id"] for w in detail.get("workspaces", [])}
        check("detail lists both workspaces", member_ids == {str(ws1), str(ws2)})
        check(
            "archived workspace count is 0",
            detail.get("archived_workspace_count") == 0,
        )

        # -- Bucket ordering (drag-to-order) --------------------------------
        r = client.put(
            f"/projects/user/{user_id}/order",
            json={"priority": [project2_id], "other": [project_id]},
        )
        check("order endpoint accepts two buckets", r.status_code == 204)

        r = client.get(f"/projects/user/{user_id}")
        ordered = r.json()
        check("priority project listed first", ordered[0]["id"] == project2_id)
        check("priority flag flipped", ordered[0]["priority"] is True)
        check("other project keeps flag false", ordered[1]["priority"] is False)

        # -- Workspace archive / restore ------------------------------------
        r = client.post(f"/workspaces/{ws1}/archive")
        check("archive workspace", r.status_code == 200 and r.json()["archived"] is True)

        r = client.get(f"/workspaces/user/{user_id}")
        live_ids = {w["id"] for w in r.json()}
        check(
            "archived workspace leaves the live list",
            str(ws1) not in live_ids and str(ws2) in live_ids,
        )

        r = client.get(f"/workspaces/user/{user_id}?archived=true")
        archived_ids = {w["id"] for w in r.json()}
        check(
            "archived workspace appears with ?archived=true",
            str(ws1) in archived_ids and str(ws2) not in archived_ids,
        )

        r = client.post(f"/workspaces/{ws1}/restore")
        check("restore workspace", r.status_code == 200 and r.json()["archived"] is False)

        # -- Project archive auto-archives members --------------------------
        r = client.post(f"/projects/{project_id}/archive")
        archived_proj = r.json()
        check("archive project", archived_proj["archived"] is True)
        check(
            "project archive auto-archives all workspaces",
            archived_proj.get("archived_workspace_count") == 2,
        )
        check(
            "detail workspace flags are archived",
            all(w["archived"] for w in archived_proj.get("workspaces", [])),
        )

        r = client.get(f"/projects/user/{user_id}")
        check(
            "archived project hidden from live projects",
            all(p["id"] != project_id for p in r.json()),
        )
        r = client.get(f"/projects/user/{user_id}?archived=true")
        check(
            "archived project listed via ?archived=true",
            any(p["id"] == project_id for p in r.json()),
        )
        r = client.get(f"/workspaces/user/{user_id}")
        check(
            "auto-archived workspaces leave live list",
            all(w["id"] not in {str(ws1), str(ws2)} for w in r.json()),
        )

        # -- Project restore brings the whole group back --------------------
        r = client.post(f"/projects/{project_id}/restore")
        restored = r.json()
        check("restore project", restored["archived"] is False)
        check(
            "restore brings all workspaces back",
            restored.get("workspace_count") == 2
            and all(not w["archived"] for w in restored.get("workspaces", [])),
        )
        r = client.get(f"/workspaces/user/{user_id}")
        check(
            "workspaces live again after project restore",
            {w["id"] for w in r.json()} == {str(ws1), str(ws2)},
        )

        # -- Delete requires a fully empty project --------------------------
        r = client.delete(f"/projects/{project_id}")
        check(
            "delete non-empty project is 409",
            r.status_code == 409,
            f"(got {r.status_code}: {r.text})",
        )
        # Unlink both workspaces (a valid emptying path), then delete.
        for ws in (ws1, ws2):
            r = client.patch(f"/workspaces/{ws}", json={"project_id": None})
            check(f"unlink workspace {ws}", r.status_code == 200)
        r = client.delete(f"/projects/{project_id}")
        check("delete emptied project is 204", r.status_code == 204)

        r = client.get(f"/projects/{project_id}")
        check(
            "deleted project is 404",
            r.status_code == 404,
            f"(got {r.status_code})",
        )

        # Re-using the name after deletion is allowed.
        r = client.post(f"/projects/user/{user_id}", json={"name": "acme corp"})
        check(
            "name reusable after project deletion",
            r.status_code == 201,
            f"(got {r.status_code})",
        )

        # -- Rename conflicts ----------------------------------------------
        r = client.patch(
            f"/projects/{project2_id}",
            json={"name": "acme corp"},
        )
        check(
            "renaming onto an existing name is 409",
            r.status_code == 409,
            f"(got {r.status_code})",
        )

    # Cleanup
    async def _dispose() -> None:
        await engine.dispose()
    asyncio.run(_dispose())

    if failures:
        print(f"\n{len(failures)} failure(s)")
        for item in failures:
            print(" -", item)
        return 1
    print("\nAll projects/archive API checks passed.")
    return 0


async def _seed_workspace(
    SessionLocal,
    user_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    async with SessionLocal() as db:
        workspace = models.Workspace(user_id=user_id, name=name)
        db.add(workspace)
        await db.commit()
        return workspace.id


def projects_list(client: TestClient, user_id: uuid.UUID) -> list[dict]:
    """Live projects for a user, straight from the API (no store state)."""
    r = client.get(f"/projects/user/{user_id}")
    assert r.status_code == 200, r.text
    return r.json()


if __name__ == "__main__":
    raise SystemExit(main())