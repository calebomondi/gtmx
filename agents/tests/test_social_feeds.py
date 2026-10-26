"""A public X account's posts and a TikTok account's videos and comments, read
from Bright Data's documented record shapes into one form."""

from data_sources.socials import tiktok, x


def test_x_posts_read_newest_first_without_reposts(monkeypatch):
    rows = [{"url": "https://x.com/a/status/1", "description": "Old", "date_posted": "2026-10-01", "views": "1,200",
             "likes": 40, "replies": 0, "reposts": 2},
            {"url": "https://x.com/a/status/2", "description": "New", "date_posted": "2026-10-20", "views": 300,
             "likes": 0, "replies": 5, "reposts": 0},
            {"url": "https://x.com/b/status/3", "description": "Theirs", "is_repost": True, "date_posted": "2026-10-21"}]
    monkeypatch.setattr(x, "fetch_records", lambda *a: rows)
    posts = x.recent_posts("a", None, 10)
    assert [p["text"] for p in posts] == ["New", "Old"]
    assert posts[1] == {"url": "https://x.com/a/status/1", "text": "Old", "date": "2026-10-01", "views": 1200,
                        "likes": 40, "replies": None, "reposts": 2}


def test_tiktok_videos_come_from_the_profile_with_their_captions(monkeypatch):
    profile = {"top_videos": [{"video_id": "7", "video_url": "https://tiktok.com/@a/video/7", "create_date": "2026-10-02",
                               "playcount": 900, "diggcount": 30, "commentcount": 4, "share_count": 1}],
               "top_posts_data": [{"post_id": "7", "description": "Soil sensors in the rain"}]}
    monkeypatch.setattr(tiktok, "fetch_record", lambda *a: profile)
    assert tiktok.recent_videos("a", None, 10) == [{"url": "https://tiktok.com/@a/video/7",
                                                    "text": "Soil sensors in the rain", "date": "2026-10-02",
                                                    "views": 900, "likes": 30, "comments": 4, "shares": 1}]


def test_tiktok_comments_keep_only_ones_with_text(monkeypatch):
    rows = [{"commenter_user_name": "farmer_joe", "comment_text": "Price?", "date_created": "2026-10-03",
             "num_likes": 2}, {"commenter_user_name": "x", "comment_text": ""}]
    monkeypatch.setattr(tiktok, "fetch_records", lambda *a: rows)
    assert tiktok.video_comments("v", None, 10) == [{"author": "farmer_joe", "text": "Price?", "date": "2026-10-03",
                                                     "likes": 2}]
