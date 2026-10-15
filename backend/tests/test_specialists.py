"""Each specialist answers from their own full research: discovery saves the
research notes, and the specialist context hands each slice to its owner."""

import uuid

import psycopg
from psycopg.types.json import Jsonb

from backend.app.database.connect import AsyncSessionLocal
from backend.app.runs.discovery import build_insights, serialize_offer_snapshot
from backend.app.services import specialists
from config import settings


def test_discovery_saves_every_specialists_research_notes():
    insights = build_insights({
        "offer_findings": "Offer notes ### Sources", "market_findings": "Market notes",
        "competition_findings": "Rival notes", "icp_findings": "GTM notes",
    })
    assert insights["research"] == {"offer": "Offer notes ### Sources", "market": "Market notes",
                                    "competition": "Rival notes", "icp": "GTM notes"}


async def test_each_specialist_gets_their_own_research(user, seed_workspace):
    workspace_id = seed_workspace(user.id, "WS")
    insights = {
        "offer_snapshot": {"offer_name": "HeatherDB"}, "domain_understanding": "Short summary.",
        "specialists": [{"domain": "product", "name": "Wanjiku"}, {"domain": "gtm", "name": "Amina"}],
        "research": {"offer": "Runs on a Raspberry Pi 5.", "market": "Banks pay $20k+.",
                     "competition": "Zilliz runs Milvus.", "icp": "Start with Lagos fintechs."},
    }
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("INSERT INTO product_profiles (id, workspace_id, target_geo, insights) VALUES (%s, %s, %s, %s)",
                     (uuid.uuid4(), workspace_id, Jsonb([]), Jsonb(insights)))
    async with AsyncSessionLocal() as db:
        context = await specialists.load(db, uuid.UUID(workspace_id))
    assert "Runs on a Raspberry Pi 5." in context.research["product"]
    assert "Banks pay $20k+." in context.research["market"]
    assert "Zilliz runs Milvus." in context.research["competition"]
    assert "Start with Lagos fintechs." in context.research["gtm"]


def test_the_seller_falls_back_to_the_offer_website():
    assert specialists.seller_name({"company_name": "Shanga Labs", "website_url": "https://shangalabs.com/"}) == "Shanga Labs"
    assert specialists.seller_name({"website_url": "https://www.shangalabs.com/about"}) == "shangalabs.com"
    assert specialists.seller_name({}) == ""


def test_the_offer_snapshot_keeps_the_company_discovery_found():
    snapshot = serialize_offer_snapshot({"offer_name": "Hardware Integration", "company_name": "Shanga Labs"})
    assert snapshot["company_name"] == "Shanga Labs"
