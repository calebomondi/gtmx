"""How an app's refusal reaches the founder: a connection granted too little
says to reconnect and allow every permission; anything else gives the app's
own reason, bounded."""

from backend.app.services.connections import refusal


def test_a_missing_permission_says_to_reconnect_and_allow_everything():
    said = refusal("googlesheets", "Failed to create new spreadsheet. Status: 403 - Request had insufficient "
                                   "authentication scopes.")
    assert said == ("Google Sheets is connected without every permission it needs. Reconnect it in this Lace's "
                    "settings (Apps & accounts) and tick every access box on the sign-in screen.")
    assert "without every permission" in refusal("googlesheets", '{"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}')


def test_other_refusals_give_the_apps_reason():
    assert refusal("slack", "channel_not_found") == "Slack refused it: channel_not_found"
    assert len(refusal("slack", "x" * 1000)) == len("Slack refused it: ") + 200
