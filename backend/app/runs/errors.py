"""Turn run failures into messages a user can act on. Raw exception text is
logged, never shown."""

from agents.llm.main import LlmProvidersExhaustedError, classify_llm_error


def user_facing_error(err: BaseException) -> str:
    """Turn a provider failure into something the user can act on.

    The raw exception is an "All LLM providers failed for <step>" RuntimeError,
    which says nothing useful in the UI. Name the step, name the likely cause,
    and say whether retrying is worth it — the run is resumable from the
    workspace, not lost.
    """
    if isinstance(err, LlmProvidersExhaustedError):
        if err.last_err is None:
            return (
                f"Stopped while running '{err.log_label}'. The AI provider is rate "
                "limiting requests across the whole run. This is a provider-side "
                "limit, not a problem with your input — wait a minute and start "
                "the workspace again. Nothing already saved is lost."
            )
        # Same classifier the retry ladder uses, so the message can't contradict
        # how we actually reacted to the error.
        kind = classify_llm_error(err.last_err)
        if kind == "rate_limit":
            reason = (
                "The AI provider is rate limiting requests right now. This is a "
                "provider-side limit, not a problem with your input — it usually "
                "clears within a minute."
            )
        elif kind == "context_overflow":
            return (
                f"Stopped while running '{err.log_label}'. The accumulated "
                "research grew past what the AI model can read in one request. "
                "This is a limit on our side, not your input — nothing already "
                "saved is lost, but the interview needs to be re-run with a "
                "shorter starting point to get past it."
            )
        elif kind == "auth":
            reason = (
                "The AI provider rejected the API key. Check DASHSCOPE_API_KEY in "
                "your .env and that the model is enabled for your account."
            )
        elif kind == "billing":
            reason = (
                "The AI provider reports the account is out of credit; the "
                "account's quota needs to be raised."
            )
        else:
            reason = "The AI provider rejected the request."

        return (
            f"Stopped while running '{err.log_label}'. {reason} "
            "Wait a moment and start the workspace again — nothing already "
            "saved is lost."
        )
    if isinstance(err, TimeoutError):
        return (
            "This run took longer than the time limit and was stopped. Nothing "
            "already saved is lost -- please start it again."
        )
    # Anything else is a bug or an outage: the detail goes to the logs, never
    # to the user (it can carry internals).
    return "Something went wrong on our side and the run stopped. Please try again."
