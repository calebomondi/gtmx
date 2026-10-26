"""The Slack actions a Lace can propose, run on the founder's approval
(lace_app_actions): a message to a channel, from the founder's account.
Composio tool verified against the live catalog (2026-10-24)."""

from backend.app.services import connections as connection_service
from backend.app.services.lace_app_actions import Outcome, RunContext, call, runs


@runs("slack", "post_message")
async def post_message(ctx: RunContext, arguments: dict) -> Outcome:
    done = await call(ctx, "SLACK_SEND_MESSAGE", {"channel": arguments["channel"], "markdown_text": arguments["text"],
                                                  "as_user": True})
    channel = connection_service.response_field(done["data"], "channel") or arguments["channel"]
    return Outcome(f"Posted in #{arguments['channel']}.", f"https://slack.com/app_redirect?channel={channel}",
                   done["log_id"])
