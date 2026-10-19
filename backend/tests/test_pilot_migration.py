"""Moving v1 pilot workspaces into Laces: one Lace per founder per website,
what carries over and what stays, a dry run that writes nothing, and a
second run that moves nothing twice."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg

from backend.app.database import models
from backend.app.database.connect import AsyncSessionLocal
from backend.app.services import pilot_migration
from config import settings

T0 = datetime(2026, 9, 1, tzinfo=UTC)


async def _seed(user_id: uuid.UUID) -> dict:
    """Two workspaces for the same startup site, and one with no site."""
    async with AsyncSessionLocal() as db, db.begin():
        first = models.Workspace(user_id=user_id, name="Shanga fleet")
        second = models.Workspace(user_id=user_id, name="Shanga again")
        siteless = models.Workspace(user_id=user_id, name="Idea")
        db.add_all([first, second, siteless])
        await db.flush()
        profile = models.ProductProfile(workspace_id=first.id, product_name="Shanga Labs",
                                        product_url="https://www.shangalabs.com/", confirmed=True,
                                        product_description="Fleet tracking for transporters.", target_geo=["Kenya"])
        profile.features = [models.ProductFeature(name="Fuel monitoring", description="Alerts on fuel theft.")]
        db.add_all([profile, models.ProductProfile(workspace_id=second.id, product_url="shangalabs.com",
                                                   product_description="Fleet tracking for transporters."),
                     models.ProductProfile(workspace_id=siteless.id, product_name="An idea")])
        db.add_all([
            models.Competitor(workspace_id=first.id, name="Fleetsmart", website="https://fleetsmart.test",
                              domain_key="fleetsmart.test", description="SME fleets", source="agent",
                              monitor_state={"pricing": "KES 900"}),
            models.Competitor(workspace_id=second.id, name="Fleetsmart", website="fleetsmart.test",
                              domain_key="fleetsmart.test", source="agent"),
            models.Competitor(workspace_id=second.id, name="TrackLink", website="https://tracklink.test",
                              domain_key="tracklink.test", source="user"),
        ])
        trigger = {"event": "Raised a Series B", "signal_type": "funding_round", "source": "https://news.test"}
        sun = models.Account(workspace_id=first.id, name="SunCulture", website="https://sunculture.test",
                             domain="sunculture.test", review_status="target", created_at=T0, trigger_event=trigger,
                             key_contacts=[{"name": "Amina", "title": "COO", "email": "amina@sunculture.test"}],
                             fit={"need": "Tracking", "capability": "x", "payoff": "y", "strength": "strong"})
        twiga = models.Account(workspace_id=first.id, name="Twiga", website="https://twiga.test", domain="twiga.test",
                               review_status="suggested", created_at=T0, trigger_event=trigger)
        untriggered = models.Account(workspace_id=first.id, name="Quiet Co", website="https://quiet.test",
                                     domain="quiet.test", review_status="target", created_at=T0)
        db.add_all([sun, twiga, untriggered])
        await db.flush()
        for status, direction, body, offset in (("sent", "outbound", "Hi Amina", 0), ("received", "inbound", "Tell me more", 1),
                                                ("draft", "outbound", "Follow-up draft", 2)):
            db.add(models.OutreachMessage(workspace_id=first.id, user_id=user_id, account_id=sun.id, channel="email",
                                          direction=direction, thread_id="t1", recipient_name="Amina",
                                          recipient_company="SunCulture", recipient_address="amina@sunculture.test",
                                          body=body, status=status, intent="interested" if direction == "inbound" else None,
                                          created_at=T0 + timedelta(hours=offset)))
    return {"first": first.id, "siteless": siteless.id}


async def _plan(user_id):
    async with AsyncSessionLocal() as db:
        return await pilot_migration.plan(db, user_id)


def _rows(query, *params):
    with psycopg.connect(settings.database_url) as conn:
        return conn.execute(query, params).fetchall()


def test_dry_run_reports_and_writes_nothing(client, user):
    client.portal.call(_seed, user.id)
    plan = client.portal.call(_plan, user.id)
    assert plan.laces == 1 and [w.name for w in plan.skipped] == ["Idea"]
    first = next(w for w in plan.workspaces if w.name == "Shanga fleet")
    assert (first.website, first.competitors, first.accounts, first.accounts_without_trigger, first.contacts,
            first.messages, first.facts) == ("https://www.shangalabs.com/", 1, 2, 1, 1, 2, 3)
    assert _rows("SELECT count(*) FROM laces WHERE user_id = %s", user.id) == [(0,)]


def test_workspaces_of_one_site_become_one_lace_once(client, user):
    client.portal.call(_seed, user.id)
    [lace_id] = client.portal.call(pilot_migration.apply, AsyncSessionLocal, user.id)
    # www.shangalabs.com/ and shangalabs.com are one site: one Lace.
    assert _rows("SELECT name, website, startup_name, status FROM laces WHERE user_id = %s", user.id) == [
        ("Shanga fleet", "https://www.shangalabs.com/", "Shanga Labs", "active")]

    facts = _rows("SELECT topic, claim, confidence FROM lace_facts WHERE lace_id = %s ORDER BY claim", lace_id)
    assert ("offer", "Fleet tracking for transporters.", "high") in facts and len(facts) == 3  # stated twice, kept once
    assert ("market", "It sells in Kenya.", "high") in facts
    assert _rows("SELECT name, origin, status, monitor_state IS NOT NULL FROM lace_competitors WHERE lace_id = %s"
                 " ORDER BY name", lace_id) == [("Fleetsmart", "found", "tracked", True),
                                                ("TrackLink", "founder", "tracked", False)]
    assert _rows("SELECT name, status, fit_strength FROM lace_accounts WHERE lace_id = %s ORDER BY name", lace_id) == [
        ("SunCulture", "target", "strong"), ("Twiga", "suggested", None)]
    assert _rows("SELECT name, approved_at FROM lace_contacts WHERE lace_id = %s", lace_id) == [("Amina", None)]
    messages = _rows("SELECT o.direction, o.status, o.thread_id, o.intent, a.name FROM lace_outreach o"
                     " JOIN lace_accounts a ON a.id = o.account_id WHERE o.lace_id = %s ORDER BY o.created_at", lace_id)
    assert messages == [("outbound", "sent", "t1", None, "SunCulture"),
                        ("inbound", "received", "t1", "interested", "SunCulture")]  # the draft stays behind

    # Again: nothing is moved twice.
    assert client.portal.call(pilot_migration.apply, AsyncSessionLocal, user.id) == [lace_id]
    for table in ("laces", "lace_facts", "lace_competitors", "lace_accounts", "lace_contacts", "lace_outreach"):
        column = "user_id" if table == "laces" else "lace_id"
        value = user.id if table == "laces" else lace_id
        before = {"laces": 1, "lace_facts": 3, "lace_competitors": 2, "lace_accounts": 2, "lace_contacts": 1,
                  "lace_outreach": 2}[table]
        assert _rows(f"SELECT count(*) FROM {table} WHERE {column} = %s", value) == [(before,)], table
    assert client.portal.call(_plan, user.id).laces == 0


def test_one_founder_at_a_time(client, user):
    client.portal.call(_seed, user.id)
    someone = uuid.uuid4()
    client.portal.call(_seed, someone)
    client.portal.call(pilot_migration.apply, AsyncSessionLocal, user.id)
    assert _rows("SELECT count(*) FROM laces WHERE user_id = %s", someone) == [(0,)]
