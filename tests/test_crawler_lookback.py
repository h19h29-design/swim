from datetime import datetime, timedelta
from pathlib import Path

from swimdash.crawler import DcinsideCrawler, _within_lookback
from swimdash.models import CrawledPost, PostMeta


class DummyClient:
    pass


class FakeCrawler(DcinsideCrawler):
    def __init__(self, metas):
        super().__init__(client=DummyClient(), error_log_file=Path("logs/test_crawler_lookback.log"))
        self._metas = metas

    def fetch_list_page(self, page: int):  # noqa: ARG002
        return self._metas

    def fetch_detail(self, meta: PostMeta):
        return CrawledPost(
            post_id=meta.post_id,
            url=meta.url,
            title=meta.title,
            author=meta.author,
            post_datetime=meta.post_datetime,
            content_text="시간: 40분\n거리: 800m",
            image_urls=[],
        )


class PagedFakeCrawler(DcinsideCrawler):
    def __init__(self, pages):
        super().__init__(client=DummyClient(), error_log_file=Path("logs/test_crawler_lookback.log"))
        self._pages = pages

    def fetch_list_page(self, page: int):
        return self._pages.get(page, [])

    def fetch_detail(self, meta: PostMeta):
        return CrawledPost(
            post_id=meta.post_id,
            url=meta.url,
            title=meta.title,
            author=meta.author,
            post_datetime=meta.post_datetime,
            content_text="1500 / 42:30",
            image_urls=[],
        )


def _meta(post_id: int, dt: datetime) -> PostMeta:
    return PostMeta(
        post_id=post_id,
        url=f"https://example.com/{post_id}",
        title=f"post-{post_id}",
        subject="일기",
        author="tester",
        author_uid="uid",
        author_ip="",
        post_datetime=dt.strftime("%Y-%m-%d %H:%M:%S"),
    )


def test_incremental_refetches_seen_posts_within_lookback():
    now = datetime.now()
    recent = _meta(1, now - timedelta(days=1))
    old = _meta(2, now - timedelta(days=7))
    crawler = FakeCrawler([recent, old])

    posts, stats = crawler.crawl(
        mode="incremental",
        seen_post_ids={1, 2},
        recent_pages=1,
        lookback_days=3,
    )

    assert [p.post_id for p in posts] == [1]
    assert stats.fetched_detail == 1
    assert stats.skipped_seen == 1


def test_within_lookback_uses_date_window_inclusive():
    now = datetime.now().replace(hour=23, minute=59, second=0, microsecond=0)
    inside = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    outside = (now - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")

    assert _within_lookback(inside, 3) is True
    assert _within_lookback(outside, 3) is False


def test_incremental_stops_after_oldest_recent_window_page():
    now = datetime.now()
    pages = {
        1: [_meta(1, now - timedelta(days=1))],
        2: [_meta(2, now - timedelta(days=5))],
        3: [_meta(3, now - timedelta(days=1))],
    }
    crawler = PagedFakeCrawler(pages)

    posts, stats = crawler.crawl(
        mode="incremental",
        seen_post_ids=set(),
        recent_pages=3,
        lookback_days=3,
        stop_before_date=(now - timedelta(days=2)).date(),
    )

    assert [post.post_id for post in posts] == [1, 2]
    assert stats.list_pages == 2
    assert stats.fetched_detail == 2
