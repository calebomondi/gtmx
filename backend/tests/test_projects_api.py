"""Projects CRUD + ordering, workspace project membership, and the
archive/restore flows, through the real API router on the Postgres test DB."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.app.naming import title_case


def test_title_case() -> None:
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


def test_projects_and_archive_flows(client: TestClient, user, seed_workspace) -> None:
    user_id = user.id
    ws1 = seed_workspace(user_id, "Analytics Hub")
    ws2 = seed_workspace(user_id, "My App")

    failures: list[str] = []

    def check(label: str, condition: bool, extra: str = "") -> None:
        if not condition:
            failures.append(f"{label} {extra}".strip())

    # -- Project creation: title-case + uniqueness -----------------------
    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "acme corp"})
    check("create project returns 201", r.status_code == 201, f"(got {r.status_code})")
    project = r.json()
    project_id = project["id"]
    check("create project normalizes name", project["name"] == "Acme Corp")
    check("create project defaults to Other", project["priority"] is False)
    check("new project has 0 workspaces", project["workspace_count"] == 0)

    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "ACME CORP"})
    check(
        "duplicate project (case-insensitive) is 409",
        r.status_code == 409,
        f"(got {r.status_code}: {r.text})",
    )

    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "  "})
    check(
        "blank project name is 422",
        r.status_code == 422,
        f"(got {r.status_code})",
    )

    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "beta ltd"})
    check("second project created", r.status_code == 201)
    project2 = r.json()
    project2_id = project2["id"]

    # -- Listing ---------------------------------------------------------
    r = client.get(f"/api/v1/projects/user/{user_id}")
    check("list live projects", r.status_code == 200 and len(r.json()) == 2)
    check(
        "live list includes both projects",
        {p["id"] for p in r.json()} == {project_id, project2_id},
    )

    # -- Append position (regression: a max position of 0 is falsy, so the
    #    second create used to land on a duplicate position 0) -----------
    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "gamma inc"})
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
    r = client.delete(f"/api/v1/projects/{project3['id']}")
    check(
        "scratch project removed",
        r.status_code == 204,
        f"(got {r.status_code})",
    )

    # -- Workspace membership -------------------------------------------
    r = client.patch(
        f"/api/v1/workspaces/{ws1}",
        json={"project_id": str(project_id)},
    )
    check(
        "workspace joins project",
        r.status_code == 200 and r.json().get("project_id") == str(project_id),
        f"(got {r.status_code})",
    )
    r = client.patch(
        f"/api/v1/workspaces/{ws2}",
        json={"project_id": str(project_id)},
    )
    check("second workspace joins project", r.status_code == 200)

    r = client.patch(
        f"/api/v1/workspaces/{ws1}",
        json={"project_id": str(uuid.uuid4())},
    )
    check(
        "linking to a foreign/unknown project is 404",
        r.status_code == 404,
        f"(got {r.status_code})",
    )
    # Confirm the failed link did not clobber the existing membership.
    r = client.get(f"/api/v1/workspaces/user/{user_id}")
    ws_rows = {w["id"]: w for w in r.json()}
    check("failed link keeps prior project", ws_rows[str(ws1)]["project_id"] == project_id)

    r = client.patch(
        f"/api/v1/workspaces/{ws1}",
        json={"name": "my great app"},
    )
    check(
        "rename title-cases workspace",
        r.status_code == 200 and r.json()["name"] == "My Great App",
    )

    r = client.get(f"/api/v1/projects/{project_id}")
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
        f"/api/v1/projects/user/{user_id}/order",
        json={"priority": [project2_id], "other": [project_id]},
    )
    check("order endpoint accepts two buckets", r.status_code == 204)

    r = client.get(f"/api/v1/projects/user/{user_id}")
    ordered = r.json()
    check("priority project listed first", ordered[0]["id"] == project2_id)
    check("priority flag flipped", ordered[0]["priority"] is True)
    check("other project keeps flag false", ordered[1]["priority"] is False)

    # -- Workspace archive / restore ------------------------------------
    r = client.post(f"/api/v1/workspaces/{ws1}/archive")
    check("archive workspace", r.status_code == 200 and r.json()["archived"] is True)

    r = client.get(f"/api/v1/workspaces/user/{user_id}")
    live_ids = {w["id"] for w in r.json()}
    check(
        "archived workspace leaves the live list",
        str(ws1) not in live_ids and str(ws2) in live_ids,
    )

    r = client.get(f"/api/v1/workspaces/user/{user_id}?archived=true")
    archived_ids = {w["id"] for w in r.json()}
    check(
        "archived workspace appears with ?archived=true",
        str(ws1) in archived_ids and str(ws2) not in archived_ids,
    )

    r = client.post(f"/api/v1/workspaces/{ws1}/restore")
    check("restore workspace", r.status_code == 200 and r.json()["archived"] is False)

    # -- Project archive auto-archives members --------------------------
    r = client.post(f"/api/v1/projects/{project_id}/archive")
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

    r = client.get(f"/api/v1/projects/user/{user_id}")
    check(
        "archived project hidden from live projects",
        all(p["id"] != project_id for p in r.json()),
    )
    r = client.get(f"/api/v1/projects/user/{user_id}?archived=true")
    check(
        "archived project listed via ?archived=true",
        any(p["id"] == project_id for p in r.json()),
    )
    r = client.get(f"/api/v1/workspaces/user/{user_id}")
    check(
        "auto-archived workspaces leave live list",
        all(w["id"] not in {str(ws1), str(ws2)} for w in r.json()),
    )

    # -- Project restore brings the whole group back --------------------
    r = client.post(f"/api/v1/projects/{project_id}/restore")
    restored = r.json()
    check("restore project", restored["archived"] is False)
    check(
        "restore brings all workspaces back",
        restored.get("workspace_count") == 2
        and all(not w["archived"] for w in restored.get("workspaces", [])),
    )
    r = client.get(f"/api/v1/workspaces/user/{user_id}")
    check(
        "workspaces live again after project restore",
        {w["id"] for w in r.json()} == {str(ws1), str(ws2)},
    )

    # -- Delete requires a fully empty project --------------------------
    r = client.delete(f"/api/v1/projects/{project_id}")
    check(
        "delete non-empty project is 409",
        r.status_code == 409,
        f"(got {r.status_code}: {r.text})",
    )
    # Unlink both workspaces (a valid emptying path), then delete.
    for ws in (ws1, ws2):
        r = client.patch(f"/api/v1/workspaces/{ws}", json={"project_id": None})
        check(f"unlink workspace {ws}", r.status_code == 200)
    r = client.delete(f"/api/v1/projects/{project_id}")
    check("delete emptied project is 204", r.status_code == 204)

    r = client.get(f"/api/v1/projects/{project_id}")
    check(
        "deleted project is 404",
        r.status_code == 404,
        f"(got {r.status_code})",
    )

    # Re-using the name after deletion is allowed.
    r = client.post(f"/api/v1/projects/user/{user_id}", json={"name": "acme corp"})
    check(
        "name reusable after project deletion",
        r.status_code == 201,
        f"(got {r.status_code})",
    )

    # -- Rename conflicts ----------------------------------------------
    r = client.patch(
        f"/api/v1/projects/{project2_id}",
        json={"name": "acme corp"},
    )
    check(
        "renaming onto an existing name is 409",
        r.status_code == 409,
        f"(got {r.status_code})",
    )

    assert not failures, "\n".join(failures)


def projects_list(client: TestClient, user_id: uuid.UUID) -> list[dict]:
    """Live projects for a user, straight from the API (no store state)."""
    r = client.get(f"/api/v1/projects/user/{user_id}")
    assert r.status_code == 200, r.text
    return r.json()
