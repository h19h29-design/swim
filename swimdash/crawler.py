from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from swimdash.config import BASE_URL, BOARD_ID, DIARY_SUBJECT, LIST_PATH
from swimdash.fetcher import HttpClient
from swimdash.models import CrawledPost, PostMeta

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlStats:
    list_pages: int = 0
    list_rows: int = 0
    filtered_diary_rows: int = 0
    fetched_detail: int = 0
    skipped_seen: int = 0
    skipped_nonfixed: int = 0
    errors: int = 0


class DcinsideCrawler:
    def __init__(self, client: HttpClient, error_log_file: Path):
        self.client = client
        self.error_log_file = error_log_file
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)

    def crawl(
        self,
        mode: str,
        seen_post_ids: set[int] | None = None,
        max_pages: int | None = None,
        recent_pages: int = 12,
        lookback_days: int = 3,
        stop_before_date: date | None = None,
        refresh_window_start: date | None = None,
        refresh_window_end: date | None = None,
    ) -> tuple[list[CrawledPost], CrawlStats]:
        seen_post_ids = seen_post_ids or set()
        stats = CrawlStats()
        results: list[CrawledPost] = []
        collected_ids: set[int] = set()
        use_refresh_window = (
            mode == "incremental"
            and refresh_window_start is not None
            and refresh_window_end is not None
        )

        if mode not in {"full", "incremental"}:
            raise ValueError(f"Unsupported mode: {mode}")

        if mode == "full":
            discovered_last = self.fetch_last_page()
            upper = discovered_last if max_pages is None else min(discovered_last, max_pages)
            pages = range(1, upper + 1)
        else:
            upper = recent_pages if max_pages is None else min(recent_pages, max_pages)
            pages = range(1, upper + 1)

        seen_streak = 0
        for page in pages:
            try:
                metas = self.fetch_list_page(page)
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                self._log_error(f"list_page_error page={page}: {exc}")
                continue

            stats.list_pages += 1
            stats.list_rows += len(metas)

            for meta in metas:
                if meta.subject != DIARY_SUBJECT:
                    continue
                stats.filtered_diary_rows += 1

                # Practical fixed-nickname rule from real HTML:
                # fixed nickname has data-uid and empty data-ip,
                # while floating/IP nick usually has data-ip value.
                if not self._is_fixed_nickname(meta):
                    stats.skipped_nonfixed += 1
                    continue

                meta_date = _meta_date(meta)
                if use_refresh_window:
                    if meta_date is None:
                        continue
                    if meta_date > refresh_window_end:
                        continue
                    if meta_date < refresh_window_start:
                        continue

                force_refresh = mode == "incremental" and _within_lookback(meta.post_datetime, lookback_days)
                if use_refresh_window and meta_date is not None:
                    force_refresh = refresh_window_start <= meta_date <= refresh_window_end

                if meta.post_id in collected_ids:
                    continue

                if meta.post_id in seen_post_ids and not force_refresh:
                    stats.skipped_seen += 1
                    seen_streak += 1
                    continue

                seen_streak = 0
                collected_ids.add(meta.post_id)

                try:
                    post = self.fetch_detail(meta)
                except Exception as exc:  # noqa: BLE001
                    stats.errors += 1
                    self._log_error(f"detail_error post_id={meta.post_id}: {exc}")
                    continue

                stats.fetched_detail += 1
                results.append(post)

            if mode == "incremental" and stop_before_date is not None:
                page_dates = [
                    _meta_date(meta)
                    for meta in metas
                    if meta.subject == DIARY_SUBJECT and self._is_fixed_nickname(meta)
                ]
                page_dates = [item for item in page_dates if item is not None]
                if page_dates and max(page_dates) < stop_before_date:
                    logger.info(
                        "Incremental crawl stopped at page=%s because latest diary row %s is older than stop_before_date=%s",
                        page,
                        max(page_dates),
                        stop_before_date,
                    )
                    break

            if mode == "incremental" and lookback_days <= 0 and page >= 2 and seen_streak >= 20:
                logger.info("Incremental crawl stopped early at page=%s due to seen streak=%s", page, seen_streak)
                break

        return results, stats

    def fetch_last_page(self) -> int:
        html = self.client.get_text(urljoin(BASE_URL, LIST_PATH), params={"id": BOARD_ID, "page": 1})
        soup = BeautifulSoup(html, "html.parser")
        page_numbers: list[int] = [1]
        for anchor in soup.select(f"a[href*='id={BOARD_ID}&page=']"):
            href = anchor.get("href", "")
            parsed = parse_qs(urlparse(href).query)
            page = parsed.get("page", [None])[0]
            if page and page.isdigit():
                page_numbers.append(int(page))
        return max(page_numbers)

    def fetch_list_page(self, page: int) -> list[PostMeta]:
        html = self.client.get_text(urljoin(BASE_URL, LIST_PATH), params={"id": BOARD_ID, "page": page})
        soup = BeautifulSoup(html, "html.parser")
        results: list[PostMeta] = []

        for row in soup.select("tr.ub-content"):
            post_no = (row.get("data-no") or "").strip()
            if not post_no.isdigit():
                continue

            title_link = row.select_one("td.gall_tit a[href*='/mini/board/view/']")
            if title_link is None:
                continue

            subject = (row.select_one("td.gall_subject") or row.select_one(".gall_subject"))
            subject_text = subject.get_text(strip=True) if subject else ""

            writer = row.select_one("td.gall_writer")
            if writer is None:
                continue

            date_cell = row.select_one("td.gall_date")
            post_datetime = (date_cell.get("title") or "").strip() if date_cell else ""

            href = title_link.get("href", "")
            full_url = urljoin(BASE_URL, href)

            results.append(
                PostMeta(
                    post_id=int(post_no),
                    url=full_url,
                    title=title_link.get_text(" ", strip=True),
                    subject=subject_text,
                    author=(writer.get("data-nick") or writer.get_text(" ", strip=True)).strip(),
                    author_uid=(writer.get("data-uid") or "").strip(),
                    author_ip=(writer.get("data-ip") or "").strip(),
                    post_datetime=post_datetime,
                )
            )

        return results

    def fetch_detail(self, meta: PostMeta) -> CrawledPost:
        html = self.client.get_text(meta.url)
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("span.title_subject") or soup.select_one(".title_subject")
        writer = soup.select_one(".gall_writer")
        date_el = soup.select_one("span.gall_date") or soup.select_one(".gall_date")
        body_el = soup.select_one("div.write_div")

        if body_el is None:
            raise RuntimeError("detail body not found")

        title = title_el.get_text(" ", strip=True) if title_el else meta.title
        author = meta.author
        if writer is not None:
            author = (writer.get("data-nick") or writer.get_text(" ", strip=True)).strip()

        post_datetime = meta.post_datetime
        if date_el is not None:
            post_datetime = (date_el.get("title") or date_el.get_text(" ", strip=True)).strip() or post_datetime

        content_text = body_el.get_text("\n", strip=True)
        content_text = _trim_content(content_text)
        image_urls = _extract_image_urls(body_el, meta.url)

        return CrawledPost(
            post_id=meta.post_id,
            url=meta.url,
            title=title,
            author=author,
            post_datetime=_normalize_datetime(post_datetime),
            content_text=content_text,
            image_urls=image_urls,
        )

    def _is_fixed_nickname(self, meta: PostMeta) -> bool:
        return bool(meta.author_uid) and not bool(meta.author_ip)

    def _log_error(self, message: str) -> None:
        self.error_log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.error_log_file.open("a", encoding="utf-8") as f:
            f.write(message + "\n")


def _trim_content(text: str) -> str:
    compact = "\n".join(line.strip() for line in text.splitlines())
    compact = "\n".join(line for line in compact.splitlines() if line)
    return compact[:6000]


def _extract_image_urls(body_el: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for img in body_el.select("img"):
        src = (
            (img.get("src") or "").strip()
            or (img.get("data-src") or "").strip()
            or (img.get("data-original") or "").strip()
            or (img.get("data-lazy-src") or "").strip()
        )
        if not src or src.startswith("data:"):
            continue
        full = urljoin(base_url, src)
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)
    return urls


def _normalize_datetime(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def _within_lookback(raw_dt: str, lookback_days: int) -> bool:
    if lookback_days <= 0:
        return False
    normalized = _normalize_datetime(raw_dt)
    if not normalized:
        return False
    try:
        post_dt = datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    cutoff_date = datetime.now().date() - timedelta(days=max(lookback_days - 1, 0))
    return post_dt.date() >= cutoff_date


def _meta_date(meta: PostMeta) -> date | None:
    normalized = _normalize_datetime(meta.post_datetime)
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        return None
