"""Screening and profiling candidate competitors: one firm on two domains is
one company, and a capped hunt (a first look) profiles only its strongest few
candidates and keeps at most the number asked for."""

from agents.pipelines.competitors import get_competitors as gc
from agents.schemas.competition import CandidateFinding, CompetitorHuntBundle


def _bundle(*firms: tuple[str, str], label: str = "AI SDR tools") -> CompetitorHuntBundle:
    return CompetitorHuntBundle(archetype_label=label,
                                candidates=[CandidateFinding(name=n, website=w) for n, w in firms])


def _screen(*bundles: CompetitorHuntBundle, cap: int | None = None) -> list[dict]:
    state = {"competitor_hunt_bundles": list(bundles), "own_website": "https://thalace.com",
             "max_competitors": cap}
    return gc.screen_candidates(state)["competitor_survivors"]


def test_one_firm_on_two_domains_is_one_company():
    survivors = _screen(_bundle(("AiSDR", "https://aisdr.com"), ("AiSDR", "https://aisdr.io"),
                                ("Reply.io", "https://reply.io"), ("Thalace", "https://thalace.com")))
    assert [(s["name"], s["website"]) for s in survivors] == [("AiSDR", "https://aisdr.com"),
                                                              ("Reply.io", "https://reply.io")]
    assert survivors[0]["mentions"] == 2


def test_a_capped_hunt_keeps_the_firms_found_most_first():
    first = _bundle(*[(f"Firm{i}", f"https://firm{i}.test") for i in range(10)])
    second = _bundle(("Firm7", "https://firm7.test"), ("Firm9", "https://www.firm9.test"), label="Agencies")
    survivors = _screen(first, second, cap=3)
    assert [s["name"] for s in survivors][:2] == ["Firm7", "Firm9"]
    assert len(survivors) == 3 + gc.SPARE_CANDIDATES
    # Uncapped, the order found is kept and the usual cap applies.
    assert [s["name"] for s in _screen(first, second)][:2] == ["Firm0", "Firm1"]


def test_a_capped_hunt_keeps_at_most_the_number_asked_for(monkeypatch):
    profiled: list[str] = []

    def profile_one(survivor, offer):
        profiled.append(survivor["name"])
        if survivor["name"] == "Firm1":
            return None, "not_a_competitor"
        return gc.CompetitorProfile(name=survivor["name"], website=survivor["website"]), None
    monkeypatch.setattr(gc, "_profile_one", profile_one)
    survivors = [{"name": f"Firm{i}", "website": f"https://firm{i}.test"} for i in range(5)]

    kept = gc.profile_competitors({"competitor_survivors": survivors, "max_competitors": 3})["competitor_profiles"]
    assert [p.name for p in kept] == ["Firm0", "Firm2", "Firm3"]
    assert sorted(profiled) == [f"Firm{i}" for i in range(5)]
