"""Making target accounts reachable: people via v1's contact search, the
organisation's own pages by strict URL and name match, and an honest verdict."""

import pytest

from agents.lace.contacts import complete_contacts, contact_status, org_page
from agents.schemas.accounts import AccountRecord, ContactRecord, TriggerEvent
from config import get_settings

CFG = get_settings()


def _record(**kw) -> AccountRecord:
    trigger = TriggerEvent(event="Grew headcount 58.8%", signal_type="hiring_post", source="https://news.test")
    return AccountRecord(name="Enzi E-Mobility", website="https://enzimotors.com", trigger_event=trigger, **kw)


@pytest.mark.parametrize("platform, url, title, ok", [
    ("facebook", "https://www.facebook.com/enzimotors", "Enzi E-Mobility | Nairobi", True),
    ("facebook", "https://www.facebook.com/sharer/sharer.php?u=x", "Enzi E-Mobility", False),
    ("facebook", "https://www.facebook.com/someoneelse", "Bodaboda Riders Kenya", False),
    ("instagram", "https://www.instagram.com/p/C123/", "Enzi E-Mobility on Instagram", False),
    ("instagram", "https://www.instagram.com/enzi.ke/?hl=en", "Enzi E-Mobility (@enzi.ke)", True),
    ("x", "https://x.com/EnziMotors", "Enzi E-Mobility (@EnziMotors) / X", True),
    ("linkedin", "https://www.linkedin.com/company/enzi-e-mobility/", "Enzi E-Mobility | LinkedIn", True),
    ("linkedin", "https://www.linkedin.com/in/jane-doe", "Jane Doe - Enzi E-Mobility", False),
    ("tiktok", "https://www.tiktok.com/@enzimotors", "Enzi E-Mobility (@enzimotors) | TikTok", True),
])
def test_org_page_needs_the_profile_shape_and_the_name(platform, url, title, ok):
    page = org_page(_record(), platform, CFG, search=lambda q, cfg: [{"url": url, "title": title}])
    assert (page == url.split("?")[0]) if ok else page is None


@pytest.mark.parametrize("contacts, socials, expected", [
    ([ContactRecord(name="Jane Doe", title="COO", email="jane@enzimotors.com")], {}, "person"),
    ([ContactRecord(email="hello@enzimotors.com")], {}, "organisation"),
    ([], {"x": "https://x.com/EnziMotors"}, "organisation"),
    ([ContactRecord(name="Jane Doe")], {}, "none"),
])
def test_contact_status(contacts, socials, expected):
    assert contact_status(_record(key_contacts=contacts, socials=socials)) == expected


def test_complete_fills_people_and_missing_pages_on_a_copy():
    record = _record(socials={"linkedin": "https://www.linkedin.com/company/enzi-e-mobility/"})
    searched = []

    def complete(acc, titles, cfg, limit):
        assert titles == ["COO"]
        acc.key_contacts = [ContactRecord(name="Jane Doe", title="COO", email="jane@enzimotors.com")]

    def search(query, cfg):
        searched.append(query)
        if "facebook.com" in query:
            return [{"url": "https://www.facebook.com/enzimotors", "title": "Enzi E-Mobility"}]
        return []

    done = complete_contacts(record, ["COO"], CFG, complete=complete, search=search)
    assert contact_status(done) == "person"
    assert done.socials == {"linkedin": "https://www.linkedin.com/company/enzi-e-mobility/",
                            "facebook": "https://www.facebook.com/enzimotors"}
    assert not any("linkedin" in q for q in searched)  # a page already on file is not searched for
    assert record.key_contacts == [] and "facebook" not in record.socials  # the input is untouched


def test_a_failed_people_search_still_finds_pages():
    def complete(acc, titles, cfg, limit):
        raise ConnectionError("exa down")

    done = complete_contacts(_record(), [], CFG, complete=complete,
                             search=lambda q, cfg: [{"url": "https://x.com/EnziMotors", "title": "Enzi E-Mobility"}]
                             if "x.com" in q else [])
    assert done.socials == {"x": "https://x.com/EnziMotors"} and contact_status(done) == "organisation"


def test_org_page_prefers_the_accounts_country():
    queries = []

    def search(query, cfg):
        queries.append(query)
        if "Kenya" in query:
            return [{"url": "https://ke.linkedin.com/company/enzimotors", "title": "Enzi E-Mobility | LinkedIn"}]
        return [{"url": "https://au.linkedin.com/company/enzi-australia", "title": "Enzi E-Mobility Australia"}]

    page = org_page(_record(geo="Kenya"), "linkedin", CFG, search=search)
    assert page == "https://ke.linkedin.com/company/enzimotors" and len(queries) == 1


@pytest.mark.parametrize("url, geo, ok", [
    ("https://vn.linkedin.com/company/reflex-technologies-vietnam", "Kenya", False),
    ("https://ke.linkedin.com/company/reflex-technologies", "Kenya", True),
    ("https://www.linkedin.com/company/reflex-technologies", "Kenya", True),
    ("https://vn.linkedin.com/company/reflex", "East Africa", True),  # a region: nothing to compare
])
def test_a_page_localised_to_another_country_is_not_the_account(url, geo, ok):
    record = _record(geo=geo).model_copy(update={"name": "Reflex Technologies"})
    page = org_page(record, "linkedin", CFG, search=lambda q, cfg: [{"url": url, "title": "Reflex Technologies"}])
    assert (page == url) if ok else page is None
