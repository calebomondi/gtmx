"""When a Lace knows enough about who buys to search for customers."""

from agents.lace.buyers import buyer_form, knows_buyers
from lace_fakes import make_fact


def test_two_facts_about_buyers_are_enough_and_offer_facts_never_are():
    offer = [make_fact(str(i), "We build with AI & Web3.", topic="offer") for i in range(5)]
    assert not knows_buyers(offer)
    one = [make_fact("c1", "Fintechs pay us.", topic="customers")]
    assert not knows_buyers(offer + one)
    assert knows_buyers(one + [make_fact("i1", "Series A fintechs in Nairobi.", topic="icp")])


def test_the_form_asks_who_pays_and_needs_only_that():
    form = buyer_form()
    assert [(f.name, f.required) for f in form.fields] == [("who_pays", True), ("past_customers", False),
                                                           ("where", False)]
    assert form.id != buyer_form().id
