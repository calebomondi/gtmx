"""Competitor endpoint rules beyond ownership."""

API = "/api/v1"


def test_competitor_cannot_lose_its_name_or_website(client, owned):
    path = f"{API}/workspaces/{owned['workspace']}/competitors/{owned['competitor']}"
    for field in ("name", "website"):
        response = client.patch(path, json={field: None})
        assert response.status_code == 422, (field, response.text)
