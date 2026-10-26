"""X API v2 records read into the same shape as the web's."""

from data_sources.socials import x_api


def test_the_lookup_key_is_the_handle_or_the_post_id():
    assert x_api.key("https://x.com/acme", "profile") == "acme"
    assert x_api.key("https://twitter.com/acme/status/1849", "post") == "1849"


def test_a_profile_and_a_post_read_like_the_webs():
    user = x_api.profile({"data": {"name": "Acme", "username": "acme", "description": "Clinics", "verified": True,
                                   "public_metrics": {"followers_count": 9, "tweet_count": 3}}}, "https://x.com/acme")
    assert (user["kind"], user["handle"], user["followers"], user["posts_count"], user["verified"]) == (
        "profile", "acme", 9, 3, True)
    record = {"data": {"text": "We opened Nakuru", "author_id": "7", "created_at": "2026-10-20T10:00:00Z",
                       "public_metrics": {"like_count": 12, "reply_count": 2, "retweet_count": 1},
                       "entities": {"hashtags": [{"tag": "clinics"}]}},
              "includes": {"users": [{"id": "7", "name": "Acme", "username": "acme"}]}}
    tweet = x_api.post(record, "https://x.com/acme/status/1")
    assert (tweet["author"], tweet["author_url"], tweet["likes"], tweet["comments_count"], tweet["hashtags"]) == (
        "Acme", "https://x.com/acme", 12, 2, ["clinics"])
