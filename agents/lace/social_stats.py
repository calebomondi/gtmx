"""How a founder's recent posts did, summed up in code so the model quotes
the numbers: totals and averages of what each platform counts, and the posts
that did best."""

# Posts named as the best, and what "best" is ranked by when a count is there.
TOP = 3
_RANKED_BY = ("views", "likes")
_COUNTS = ("views", "likes", "comments", "replies", "reposts", "shares")


def summarise_posts(posts: list[dict]) -> dict:
    """{posts, totals, averages, best: [{url, text, ...}]}; counts a platform
    doesn't give are left out."""
    counts = [c for c in _COUNTS if any(p.get(c) is not None for p in posts)]
    totals = {c: sum(p.get(c) or 0 for p in posts) for c in counts}
    averages = {c: round(totals[c] / len(posts), 1) for c in counts} if posts else {}
    rank = next((c for c in _RANKED_BY if c in counts), None)
    best = sorted(posts, key=lambda p: p.get(rank) or 0, reverse=True)[:TOP] if rank else posts[:TOP]
    return {"posts": len(posts), "totals": totals, "averages": averages, "ranked_by": rank,
            "best": [{k: p.get(k) for k in ("url", "text", "date", *counts)} for p in best]}
