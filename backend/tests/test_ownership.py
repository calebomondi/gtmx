"""Tenant isolation: another user's workspace, project, competitors, accounts and
runs must be invisible -- every route answers 404 exactly as for a missing id,
and nothing is changed. User-scoped list routes answer 403 for someone else's
user id."""

from backend.tests.helpers import make_user

API = "/api/v1"


def _routes(ids: dict) -> list[tuple[str, str, dict | None]]:
    ws, pr = ids["workspace"], ids["project"]
    return [
        ("GET", f"/workspaces/{ws}", None),
        ("GET", f"/workspaces/{ws}/insights", None),
        ("PATCH", f"/workspaces/{ws}", {"name": "hijacked"}),
        ("POST", f"/workspaces/{ws}/archive", None),
        ("POST", f"/workspaces/{ws}/restore", None),
        ("DELETE", f"/workspaces/{ws}", None),
        ("GET", f"/projects/{pr}", None),
        ("PATCH", f"/projects/{pr}", {"name": "hijacked"}),
        ("POST", f"/projects/{pr}/archive", None),
        ("POST", f"/projects/{pr}/restore", None),
        ("DELETE", f"/projects/{pr}", None),
        ("GET", f"/workspaces/{ws}/competitors", None),
        ("POST", f"/workspaces/{ws}/competitors", {"website": "other.example", "deep_research": False}),
        ("PATCH", f"/workspaces/{ws}/competitors/{ids['competitor']}", {"name": "hijacked"}),
        ("DELETE", f"/workspaces/{ws}/competitors/{ids['competitor']}", None),
        ("GET", f"/workspaces/{ws}/competitors/runs", None),
        ("POST", f"/workspaces/{ws}/competitors/runs", None),
        ("GET", f"/workspaces/{ws}/competitors/runs/{ids['competitor_run']}", None),
        ("GET", f"/workspaces/{ws}/accounts", None),
        ("PATCH", f"/workspaces/{ws}/accounts/{ids['account']}", {"selected": True}),
        ("GET", f"/workspaces/{ws}/accounts/runs", None),
        ("POST", f"/workspaces/{ws}/accounts/runs", None),
        ("POST", f"/workspaces/{ws}/accounts/fit", None),
        ("GET", f"/workspaces/{ws}/accounts/runs/{ids['account_run']}", None),
    ]


def test_another_user_gets_404_on_every_resource_route(client, owned):
    client.sign_in(make_user("Intruder"))
    for method, path, body in _routes(owned):
        response = client.request(method, API + path, json=body)
        assert response.status_code == 404, f"{method} {path} -> {response.status_code} {response.text}"


def test_intruder_requests_change_nothing(client, user, owned):
    client.sign_in(make_user("Intruder"))
    for method, path, body in _routes(owned):
        client.request(method, API + path, json=body)

    client.sign_in(user)
    workspace = client.get(f"{API}/workspaces/{owned['workspace']}").json()
    assert workspace["name"] == "Owner Workspace" and workspace["archived"] is False
    assert client.get(f"{API}/projects/{owned['project']}").json()["name"] == "Owner Project"
    competitors = client.get(f"{API}/workspaces/{owned['workspace']}/competitors").json()
    assert [c["domain_key"] for c in competitors["competitors"]] == ["rival.example"]
    accounts = client.get(f"{API}/workspaces/{owned['workspace']}/accounts").json()
    assert accounts["accounts"][0]["selected"] is False


def test_owner_can_reach_every_read_route(client, owned):
    for method, path, _ in _routes(owned):
        if method == "GET":
            response = client.get(API + path)
            assert response.status_code == 200, f"GET {path} -> {response.status_code} {response.text}"


def test_user_scoped_lists_reject_another_users_id(client, user):
    client.sign_in(make_user("Intruder"))
    for path in (f"/workspaces/user/{user.id}", f"/projects/user/{user.id}"):
        assert client.get(API + path).status_code == 403


def test_cannot_link_own_workspace_to_another_users_project(client, user, owned, seed_workspace):
    intruder = make_user("Intruder")
    intruder_workspace = seed_workspace(intruder.id, "Intruder Workspace")
    client.sign_in(intruder)
    response = client.patch(f"{API}/workspaces/{intruder_workspace}", json={"project_id": owned["project"]})
    assert response.status_code == 404
