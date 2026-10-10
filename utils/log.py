import logging

from config import settings

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

# The agent's own logger is "gtmx.nodes", a child of the "gtmx" package. Setting
# the level on "GTMX" (a different, unrelated name) never matched it, so every
# agent diagnostic — which model each call used, how large each assembled context
# actually was — was silently dropped. Those are exactly the numbers needed to
# diagnose a run that dies on a provider-side limit, so the level is set on the
# real parent and can be overridden with GTMX_LOG_LEVEL (see config.Settings.log_level).
logging.getLogger("gtmx").setLevel(settings.log_level.upper())
logger = logging.getLogger("gtmx.nodes")