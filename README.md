
if provider == "openai":
        m = model or OPENAI_COMP_MODELS[0]
        logger.info("Using OpenAI (%s)", m)
        return ChatOpenAI(
            model=m,
            base_url="https://openrouter.ai/api/v1",
            api_key=cfg.openai_api_key
        )