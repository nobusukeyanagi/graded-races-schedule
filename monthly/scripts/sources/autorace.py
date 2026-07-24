from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from monthly.scripts.common import OfficialSession, SourceResult, clean_text

SPORT = "auto"
VENUES = {
    "川口": "kawaguchi",
    "伊勢崎": "isesaki",
    "浜松": "hamamatsu",
    "飯塚": "iizuka",
    "山陽": "sanyo",
}
SLUG_TO_VENUE = {slug: venue for venue, slug in VENUES.items()}
TIME_RE = re.compile(r"(?:発走(?:予定)?|締切(?:予定)?)\s*[:：]?\s*([0-2]?\d:[0-5]\d)")
VENUE_TITLE_RE = re.compile(r"(川口|伊勢崎|浜松|飯塚|山陽)\s*(?:オートレース|オート)")
RACE_TOKENS = ("1R", "第1レース", "発走", "出走表")
NOT_FOUND_TOKENS = ("ページが見つかりません", "404 Not Found")


def _session_from_text(context_text: str, first_time: str) -> str:
    """開催名などページ上部の文脈と1R時刻から時間帯を判定する。"""
    if "オーバーミッドナイト" in context_text or "ミッドナイト" in context_text:
        return "midnight"
    if "ナイター" in context_text or "アフター5" in context_text:
        return "night"
    if "アーリー" in context_text:
        return "morning"
    if first_time:
        hour = int(first_time.split(":", 1)[0])
        if hour <= 10:
            return "morning"
        if hour >= 14:
            return "night"
    return ""


def _identity_candidates(soup: BeautifulSoup) -> list[str]:
    """ナビ・フッターを除外し、ページ固有の開催場名が載る箇所だけを返す。"""
    candidates: list[str] = []
    if soup.title:
        candidates.append(soup.title.get_text(" ", strip=True))

    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            candidates.append(str(tag.get("content")))

    main = soup.find("main")
    heading_root = main or soup.body or soup
    for heading in heading_root.find_all(("h1", "h2"), limit=4):
        candidates.append(heading.get_text(" ", strip=True))

    return [clean_text(value) for value in candidates if clean_text(value)]


def _canonical_venue(soup: BeautifulSoup) -> str:
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if not canonical or not canonical.get("href"):
        return ""
    path_parts = [part for part in urlparse(str(canonical.get("href"))).path.split("/") if part]
    for part in path_parts:
        if part in SLUG_TO_VENUE:
            return SLUG_TO_VENUE[part]
    return ""


def _page_venue(soup: BeautifulSoup) -> str:
    """title・OG title・ページ上部見出しから、実際に表示された開催場を特定する。"""
    for candidate in _identity_candidates(soup):
        match = VENUE_TITLE_RE.search(candidate)
        if match:
            return match.group(1)

    # title等に開催場がないページだけ、canonical URLを補助情報として利用する。
    return _canonical_venue(soup)


def _event_context(soup: BeautifulSoup) -> str:
    """時間帯判定に使う開催名周辺だけを抽出し、フッターの宣伝文言を混入させない。"""
    candidates = _identity_candidates(soup)
    main = soup.find("main")
    if main:
        for selector in (".race-title", ".event-title", ".meeting-title", ".race-name"):
            for element in main.select(selector)[:2]:
                candidates.append(clean_text(element.get_text(" ", strip=True)))
    return clean_text(" ".join(value for value in candidates if value))


def _is_race_page(soup: BeautifulSoup, text: str) -> bool:
    """開催表本文にレース番号・発走時刻がある場合だけ出走表として扱う。"""
    if any(token in text for token in NOT_FOUND_TOKENS):
        return False
    main = soup.find("main") or soup.body or soup
    main_text = clean_text(main.get_text(" ", strip=True))
    has_race_marker = any(token in main_text for token in RACE_TOKENS)
    has_start_time = bool(TIME_RE.search(main_text))
    return has_race_marker and has_start_time


def collect(target: date, session: OfficialSession) -> SourceResult:
    entries: list[dict[str, Any]] = []
    fetched: list[str] = []
    warnings: list[str] = []
    reachable_pages = 0
    race_pages = 0

    for expected_venue, slug in VENUES.items():
        url = f"https://autorace.jp/race_info/Program/{slug}/{target.isoformat()}_01"
        try:
            response = session.get(url)
            reachable_pages += 1
            fetched.append(response.url)
            soup = BeautifulSoup(response.text, "lxml")
            text = clean_text(soup.get_text(" ", strip=True))
            if not _is_race_page(soup, text):
                continue

            race_pages += 1
            actual_venue = _page_venue(soup)
            if not actual_venue:
                warnings.append(f"{expected_venue}: ページ上部から開催場を識別できなかったため除外しました。")
                continue
            if actual_venue != expected_venue:
                warnings.append(
                    f"{expected_venue}: 取得ページは{actual_venue}の出走表だったため、非開催場として除外しました。"
                )
                continue

            times = TIME_RE.findall(text)
            first_time = times[0] if times else ""
            item: dict[str, Any] = {"sport": SPORT, "venue": expected_venue, "grade": "普通"}
            session_name = _session_from_text(_event_context(soup), first_time)
            if session_name:
                item["session"] = session_name
            entries.append(item)
        except Exception as exc:
            warnings.append(f"{expected_venue}: {exc}")

    if reachable_pages == 0:
        return SourceResult(
            SPORT,
            False,
            fetched_urls=fetched,
            warnings=warnings,
            error="AutoRace.JPの当日出走表へ接続できませんでした",
        )

    # レース内容は取得できたのに開催場を1件も確定できない場合は、HTML構造変更として失敗扱いにする。
    # update_schedule.py側が既存データを保全するため、誤った0件更新も防げる。
    if race_pages > 0 and not entries:
        return SourceResult(
            SPORT,
            False,
            fetched_urls=fetched,
            warnings=warnings,
            error="AutoRace.JPのページから開催場を確定できませんでした",
        )

    return SourceResult(SPORT, True, entries=entries, fetched_urls=fetched, warnings=warnings)
