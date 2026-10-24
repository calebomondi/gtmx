"""One Lace per startup: a second Lace for the same website domain is
refused, and its would-be maker can ask to join the first instead."""

from backend.tests.helpers import make_user
from backend.tests.test_lace_invites import WANJIRU, people  # noqa: F401 -- fixture
from backend.tests.test_lace_jobs import lace  # noqa: F401 -- fixture
from backend.tests.test_laces_api import API, lace_runtime  # noqa: F401 -- fixture


def test_a_second_lace_for_the_same_startup_is_refused(client, lace):  # noqa: F811
    client.sign_in(make_user("Copycat"))
    for website in ("acme.test", "https://www.ACME.test/about", "http://acme.test:8080"):
        refused = client.post(f"{API}/laces", json={"name": "Mine", "website": website})
        assert refused.status_code == 409 and "acme.test already has a Lace" in refused.json()["detail"], website
    assert client.get(f"{API}/laces/claimed", params={"website": "www.acme.test"}).json() == {
        "domain": "acme.test", "taken": True}
    assert client.get(f"{API}/laces/claimed", params={"website": "other.test"}).json()["taken"] is False


def test_asking_to_join_reaches_its_people(client, user, lace, people):  # noqa: F811
    client.sign_in(WANJIRU)
    assert client.post(f"{API}/laces/requests", json={"website": "https://acme.test"}).status_code == 204
    assert client.post(f"{API}/laces/requests", json={"website": "acme.test"}).status_code == 409  # asked already
    assert client.get(f"{API}/laces/{lace}").status_code == 404  # not in yet
    assert client.post(f"{API}/laces/requests", json={"website": "nolace.test"}).status_code == 404

    client.sign_in(user)
    [feed_item] = [a for a in client.get(f"{API}/laces/{lace}/activity").json() if a["kind"] == "access_requested"]
    assert feed_item["title"] == "Wanjiru asked to join"
    team = {p["email"]: p["status"] for p in client.get(f"{API}/laces/{lace}/members").json()}
    assert team[WANJIRU.email] == "requested"
    assert client.post(f"{API}/laces/{lace}/members/{WANJIRU.id}/approve").status_code == 204

    client.sign_in(WANJIRU)
    assert client.get(f"{API}/laces/{lace}").json()["role"] == "member"
