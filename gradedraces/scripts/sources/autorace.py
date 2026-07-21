from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from scripts.common import (
    Patch,
    RateLimitedSession,
    SourceResult,
    choose_first_place_name,
    clean_text,
    normalize,
    same_name,
    soup_from,
    strip_edition,
    table_rows,
)

NAME = "オートレース"
GRADE_URL = "https://autorace.jp/calendar/graderace/"
VENUE_SLUGS = {
    "川口": "kawaguchi",
    "伊勢崎": "isesaki",
    "浜松": "hamamatsu",
    "飯塚": "iizuka",
    "山陽": "sanyo",
}

DATE_RANGE_RE = re.compile(
    r"(?P<start_year>\d{4})年(?P<start_month>\d{1,2})月(?P<start_day>\d{1,2})日.*?"
    r"[～~-](?:(?P<end_year>\d{4})年)?(?:(?P<end_month>\d{1,2})月)?(?P<end_day>\d{1,2})日"
)
SALES_RE = re.compile(r"[\d,]+億|[\d,]+万|円")


def _url(kind: str, venue: str, date: str, race_no: int) -> str:
    slug = VENUE_SLUGS[venue]
    return f"https://autorace.jp/race_info/{kind}/{slug}/{date}_{race_no:02d}"


def _looks_like_person_name(value: str) -> bool:
    text = clean_text(value)
    if not 2 <= len(text) <= 20 or re.search(r"\d", text) or SALES_RE.search(text):
        return False
    if any(token in text for token in ("優勝者", "レース", "カップ", "賞", "記念", "選手権", "グランプリ")):
        return False
    return bool(re.search(r"[一-龯ぁ-んァ-ヶ]", text))


def _parse_end_date(value: str) -> str:
    match = DATE_RANGE_RE.search(clean_text(value))
    if not match:
        return ""
    start_year = int(match.group("start_year"))
    start_month = int(match.group("start_month"))
    end_year = int(match.group("end_year") or start_year)
    end_month = int(match.group("end_month") or start_month)
    end_day = int(match.group("end_day"))
    try:
        return dt.date(end_year, end_month, end_day).isoformat()
    except ValueError:
        return ""


def parse_grade_schedule_entries(soup: BeautifulSoup) -> list[dict[str, str]]:
    """AutoRace.JP年間グレード日程から最終日と優勝者を取得する。"""
    entries: list[dict[str, str]] = []
    for cells in table_rows(soup):
        joined = " | ".join(cells)
        end_date = _parse_end_date(joined)
        if not end_date:
            continue
        venue_index = next((i for i, cell in enumerate(cells) if clean_text(cell) in VENUE_SLUGS), -1)
        if venue_index < 0:
            continue

        # 日付セルより前にある、グレード以外の最後の文字列をレース名とする。
        date_index = next((i for i, cell in enumerate(cells) if _parse_end_date(cell)), venue_index)
        title = ""
        for cell in reversed(cells[:date_index]):
            value = clean_text(cell)
            if not value:
                continue
            if re.fullmatch(r"(?:特)?G(?:I|II|III|Ⅰ|Ⅱ|Ⅲ)|SG", normalize(value), re.I):
                continue
            title = strip_edition(value)
            break

        winner = ""
        for cell in cells[venue_index + 1 :]:
            if _looks_like_person_name(cell):
                winner = clean_text(cell)
                break
        entries.append(
            {
                "title": title,
                "venue": clean_text(cells[venue_index]),
                "end_date": end_date,
                "winner": winner,
            }
        )
    return entries


def grade_schedule_patches(records: list[dict[str, Any]], soup: BeautifulSoup, source_url: str) -> list[Patch]:
    entries = parse_grade_schedule_entries(soup)
    patches: list[Patch] = []
    for index, record in enumerate(records):
        if record.get("sport") != "auto":
            continue
        for entry in entries:
            if entry["end_date"] != str(record.get("date", "")):
                continue
            if normalize(entry["venue"]) != normalize(record.get("venue")):
                continue
            if entry["title"] and not same_name(str(record.get("name", "")), entry["title"]):
                continue
            if entry["winner"]:
                patches.append(
                    Patch(index, {"winner": entry["winner"]}, NAME, source_url, "AutoRace.JP公式年間日程の優勝者")
                )
            break
    return patches


def collect(records: list[dict[str, Any]], session: RateLimitedSession, logger: logging.Logger) -> SourceResult:
    targets = [(index, record) for index, record in enumerate(records) if record.get("sport") == "auto"]
    if not targets:
        return SourceResult(NAME, True, [], [], [])
    patches: list[Patch] = []
    fetched: list[str] = []
    warnings: list[str] = []
    try:
        grade_response = session.get(GRADE_URL)
        fetched.append(grade_response.url)
        grade_soup = soup_from(grade_response)
        grade_text = grade_soup.get_text(" ", strip=True)
        if "グレード" not in grade_text or len(grade_text) < 500:
            raise RuntimeError("オートレース年間グレード日程の内容を確認できません")
        patches.extend(grade_schedule_patches(records, grade_soup, grade_response.url))

        for index, record in targets:
            venue = str(record.get("venue", ""))
            if venue not in VENUE_SLUGS:
                warnings.append(f"未対応の開催場: {venue}")
                continue
            compact_date = str(record["date"])
            found = False
            # 終了後はResult、開催前はProgram。12Rから9Rまで順に確認する。
            for kind in ("RaceResult", "Program"):
                for race_no in range(12, 8, -1):
                    url = _url(kind, venue, compact_date, race_no)
                    try:
                        response = session.get(url)
                        fetched.append(response.url)
                        soup = soup_from(response)
                        text = clean_text(soup.get_text(" ", strip=True))
                        if len(text) < 250 or "ページが見つかりません" in text:
                            continue
                        rows = list(table_rows(soup))
                        if not rows and "発走" not in text:
                            continue
                        fields: dict[str, str] = {}
                        time_match = re.search(r"発走(?:予定)?\s*([0-2]?\d:[0-5]\d)", text)
                        if time_match:
                            hour, minute = time_match.group(1).split(":")
                            fields["time"] = f"{int(hour):02d}:{minute}"
                        if kind == "RaceResult":
                            winner = choose_first_place_name(rows)
                            if winner:
                                fields["winner"] = winner
                        if fields:
                            patches.append(Patch(index, fields, NAME, response.url, f"AutoRace.JP公式{kind} {race_no}R"))
                            found = True
                            break
                    except Exception as exc:
                        warnings.append(f"{record['date']} {venue} {kind} {race_no}R: {exc}")
                if found:
                    break
            # 年間日程の優勝者だけ取得できた場合も正常。個別ページ不明は警告として可視化する。
            if not found:
                warnings.append(f"{record['date']} {venue}: 優勝戦ページを特定できませんでした")
        return SourceResult(NAME, True, patches, list(dict.fromkeys(fetched)), warnings)
    except Exception as exc:
        logger.exception("オートレースの取得に失敗しました")
        return SourceResult(NAME, False, patches, fetched, warnings, str(exc))
