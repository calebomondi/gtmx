"""Only clients a source actually names survive."""

from agents.pipelines.accounts import competitor_clients as cc
from agents.schemas.accounts import CompetitorClient, CompetitorClients

DOCS = [{"url": "https://rival.example/stories/swift", "title": "Swift Haulage",
         "text": "Swift Haulage cut fuel costs 12% with Rival's platform."}]


def _client(name, url="https://rival.example/stories/swift", relationship="case_study"):
    return CompetitorClient(name=name, relationship=relationship, evidence="...", source_url=url)


def test_only_backed_named_clients_are_kept(monkeypatch):
    monkeypatch.setattr(cc, "_docs", lambda name, website: DOCS)
    returned = CompetitorClients(clients=[
        _client("Swift Haulage"),
        _client("Ghost Logistics"),                          # its cited page never names it
        _client("Rival"),                                    # the competitor itself
        _client("Itkenya Universal", url="", relationship="profile"),  # on the profile list
        _client("Made Up Co", url="", relationship="profile"),          # not on the profile list
        _client("Swift Haulage"),                            # duplicate
    ])
    monkeypatch.setattr(cc, "invoke_structured_with_fallback", lambda *a, **k: returned)
    kept = cc.find("Rival", "https://rival.example", ["Itkenya Universal", "Banks"])
    assert [c.name for c in kept] == ["Swift Haulage", "Itkenya Universal"]
    assert kept[1].source_url == "https://rival.example"


def test_nothing_to_read_means_no_model_call(monkeypatch):
    monkeypatch.setattr(cc, "_docs", lambda name, website: [])
    monkeypatch.setattr(cc, "invoke_structured_with_fallback", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert cc.find("Rival", "https://rival.example", []) == []
