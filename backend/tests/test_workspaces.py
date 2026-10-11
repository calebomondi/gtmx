"""Workspace creation from a discovery run."""

from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import workspaces as workspace_service


async def test_offer_type_is_stored_on_the_workspace(user):
    async with AsyncSessionLocal() as db:
        workspace_id = await workspace_service.create_from_discovery(
            db, user.id, {"offer_name": "acme audits", "offer_type": "service"},
        )
        workspace = await workspace_service.get_owned(db, user.id, workspace_id)
    assert workspace.offer_type == "service"
    assert workspace.name == "Acme Audits"


def test_workspace_api_returns_offer_type(client, user, seed_workspace):
    seed_workspace(user.id, "Untyped")
    [workspace] = client.get(f"/api/v1/workspaces/user/{user.id}").json()
    assert workspace["offer_type"] is None
