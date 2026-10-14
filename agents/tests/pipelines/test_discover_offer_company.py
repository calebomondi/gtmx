"""The offer's company name is read off the page summary, JSON or markdown."""

import pytest

from agents.pipelines.discover.discover_offer import company_from_understanding


@pytest.mark.parametrize("text, expected", [
    ('{"company_name": "Shanga Labs", "offer_name": "Hardware Integration"}', "Shanga Labs"),
    ("- **company_name**: Shanga Labs\n- **offer_name**: Hardware Integration", "Shanga Labs"),
    ("- company_name: \"Aphorion\"\n- offer_name: HeatherDB", "Aphorion"),
    ('{"company_name": null, "offer_name": "X"}', None),
    ("- **company_name**: null\n- **offer_name**: X", None),
    ("- **offer_name**: X", None),
    (None, None),
])
def test_company_name_is_read_off_the_page_summary(text, expected):
    assert company_from_understanding(text) == expected
