"""Mzalendo's Bill Tracker: each bill's stage is the track's current segment,
and bills are matched across sources by name and year."""

import httpx
import pytest

from data_sources.legislation.mzalendo import BillStatus, MzalendoError, bill_key, bill_stages, parse_tracker


def _row(href, name, year, stage, label="First Reading"):
    segs = "".join(f'<span class="bt-seg bt-seg--s{i}{" is-current" if title == stage else ""}" title="{title}"></span>'
                   for i, title in enumerate(["First Reading", "Second Reading", "Committee of the Whole House",
                                              "Third Reading", "Presidential Assent"], 1))
    return (f'<div class="bt-row"><a class="bt-row__link" href="{href}">'
            f'<span class="bt-row__name">{name} <span class="bt-row__year">{year}</span> '
            f'<span class="bt-row__number" title="x">National Assembly Bill No. 65 of {year}</span></span>'
            f'<span class="bt-track" title="{stage}">{segs}</span><span class="bt-row__stage">{label}</span></a>'
            f'<button class="bt-row__preview">Read</button></div>')


PAGE = (_row("/legislative-trends/bills/na/852/", "The Tax Laws (Amendment) Bill, 2026", 2026, "Third Reading")
        + _row("/legislative-trends/bills/na/700/", "The Value Added Tax (Amendment) Bill, 2026", 2026,
               "Presidential Assent", label="Bill assented by the Presi…")
        + _row("/legislative-trends/bills/na/1/", "A bill with no stage marked", 2026, "none"))


def test_stages_come_from_the_current_segment():
    assert parse_tracker(PAGE, "National Assembly") == [
        BillStatus(title="The Tax Laws (Amendment) Bill, 2026", year=2026, house="National Assembly",
                   stage="third_reading", url="https://mzalendo.com/legislative-trends/bills/na/852/"),
        BillStatus(title="The Value Added Tax (Amendment) Bill, 2026", year=2026, house="National Assembly",
                   stage="assented", url="https://mzalendo.com/legislative-trends/bills/na/700/"),
    ]


@pytest.mark.parametrize("a, b", [
    (("The Artificial Intelligence Bill, 2026", None), ("The Artificial Intelligence Bill 2026", 2026)),
    (("The Value Added Tax (Amendment) Bill, 2026", None), ("The Value Added Tax (amendment) Bill", 2026)),
    (("The Statutory Instruments (Amendment) Bill, 2024", None),
     ("Senate Bill No. 10 Of 2024 - The Statutory Instruments (Amendment) Bill, 2024", 2024)),
])
def test_the_same_bill_has_the_same_key(a, b):
    assert bill_key(*a) == bill_key(*b)


def test_bills_of_other_years_differ():
    assert bill_key("The Finance Bill, 2026") != bill_key("The Finance Bill, 2025")


def test_each_house_is_read_until_a_page_lists_none():
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append((request.url.params.get("house"), request.url.params.get("page")))
        return httpx.Response(200, text=PAGE if request.url.params.get("page") in (None, "2") else "<p>End</p>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        bills = bill_stages(["National Assembly", "Senate"], client=client)
    assert asked == [("na", None), ("na", "2"), ("na", "3"), ("senate", None), ("senate", "2"), ("senate", "3")]
    assert len(bills) == 8 and {b.house for b in bills} == {"National Assembly", "Senate"}


def test_an_empty_first_page_means_the_layout_changed():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<p>New look</p>"))) as client:
        with pytest.raises(MzalendoError, match="layout"):
            bill_stages(["Senate"], client=client)


def test_an_unreachable_tracker_is_a_mzalendo_error():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(502))) as client:
        with pytest.raises(MzalendoError, match="page 1"):
            bill_stages(["National Assembly"], client=client)


@pytest.mark.live
def test_the_live_tracker_still_parses():
    bills = bill_stages(["Senate"])
    assert len(bills) >= 10 and all(b.url.startswith("https://mzalendo.com/") for b in bills)
