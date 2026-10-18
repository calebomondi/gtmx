import pytest

from config import get_settings
from lace_fakes import MemoryStore


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def settings():
    return get_settings().model_copy(update={"firecrawl_api_key": "fc-test", "exa_api_key": "exa-test"})
