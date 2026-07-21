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
    best_record_match,
    choose_first_place_name,
    clean_text,
    extract_times,
    now_jst,
    parse_grade_and_name,
    same_name,
    soup_from,
    strip_edition,
    table_rows,
)

NAME = "ボートレース"
SCHEDULE_URLS = {
    "SG": "https://www.boatrace.jp/owpc/pc/race/gradesch?hcd=01",
    "G1G2": "https://www.boatrace.jp/owpc/pc/race/gradesch?hcd=02",
    "G3": "https://www.boatrace.jp/owpc/pc/race/gradesch?hcd=03",
}
RACE_INDEX_URL = "https://www.boatrace.jp/owpc/pc/race/raceindex"
RACE_RESULT_URL = "https://www.boatrace.jp/owpc/pc/race/raceresult"
VENUE_CODES = {
    "桐生": "01", "戸田": "02", "江戸川": "03", "平和島": "04", "多摩川": "05", "浜名湖": "06",
    "蒲郡": "07", "常滑": "08", "津": "09", "三国": "10", "びわこ": "11", "住之江": "12",
    "尼崎": "13", "鳴門": "14", "丸亀": "15", "児島": "16", "宮島": "17", "徳山": "18",
    "下関": "19", "若松": "20", "芦屋": "21", "福岡": "22", "唐津": "23", "大村": "24",
}


def _parse_range(value: str, base_year: int) -> str:
    match = re.search(r"(\d{1,2})/(\d{1,2})\s*[-～]\s*(?:(\d{1,2})/)?(\d{1,2})", value)
    if not match:
        return ""
    start_month = int(match.group(1))
    end_month = int(match.group(3) or start_month)
    end_day = int(match.group(4))
    year = base_year + (1 if start_month == 12 and end_month == 1 else 0)
    return dt.date(year, end_month, end_day).isoformat()


def _schedule_patches(records: list[dict[str, Any]], session: RateLimitedSession) -> tuple[list[Patch], list[str], list[str]]:
    """年間日程は正式名称の補正に使用し、結果は個別公式結果ページを優先する。"""
    patches: list[Patch] = []
    fetched: list[str] = []
    warnings: list[str] = []
    years = sorted({int(str(record["date"])[:4]) for record in records if record.get("sport") == "boat"})
    for label, url in SCHEDULE_URLS.items():
        response = session.get(url)
        fetched.append(response.url)
        soup = soup_from(response)
        rows = list(table_rows(soup))
        if not rows:
            warnings.append(f"{label}: 表を取得できませんでした")
            continue
        for cells in rows:
            joined = " | ".join(cells)
            if not re.search(r"\d{1,2}/\d{1,2}\s*[-～]", joined):
                continue
            for year in years:
                end_date = _parse_range(joined, year)
                if not end_date:
                    continue
                venue = next((cell for cell in cells if cell in VENUE_CODES), "")
                if not venue:
                    continue
                candidates = [cell for cell in cells if cell and cell != venue and not re.search(r"\d{1,2}/\d{1,2}", cell)]
                title = ""
                for cell in candidates:
                    _, parsed_name = parse_grade_and_name(cell)
                    if parsed_name and len(parsed_name) >= 3 and not any(token in parsed_name for token in ("開催日程", "優勝者", "リンク")):
                        title = strip_edition(parsed_name)
                        break
                index = best_record_match(records, sport="boat", date=end_date, venue=venue, name=title)
                if index is None:
                    continue
                existing_name = str(records[index].get("name", ""))
                generic_names = {"", "企業杯", "オールレディース", "マスターズリーグ"}
                if title and title not in {"企業杯", "オールレディース", "マスターズリーグ"}:
                    if existing_name in generic_names or same_name(existing_name, title):
                        patches.append(Patch(index, {"name": title}, NAME, response.url, f"BOAT RACE {label}公式日程"))
    return patches, fetched, warnings


def parse_official_result_page(soup: BeautifulSoup) -> dict[str, str]:
    """BOAT RACE公式12R結果ページから締切予定時刻と1着選手を取得する。"""
    text = clean_text(soup.get_text(" ", strip=True))
    fields: dict[str, str] = {}

    # 「締切予定時刻」の後ろには1R～12Rが並ぶため、最後の時刻が12R。
    time_match = re.search(r"締切予定時刻(.{0,500}?)(?:優勝戦|選抜戦|特別選抜|出走表|オッズ)", text)
    if not time_match:
        time_match = re.search(r"締切予定時刻(.{0,500})", text)
    if time_match:
        times = extract_times(time_match.group(1))
        if times:
            fields["time"] = times[-1]

    winner = choose_first_place_name(table_rows(soup))
    if winner:
        fields["winner"] = winner
    return fields


def _official_result(record: dict[str, Any], session: RateLimitedSession) -> tuple[dict[str, str], str]:
    code = VENUE_CODES.get(str(record.get("venue", "")))
    if not code:
        return {}, ""
    params = {
        "jcd": code,
        "hd": str(record["date"]).replace("-", ""),
        "rno": "12",
    }
    response = session.get(RACE_RESULT_URL, params=params)
    soup = soup_from(response)
    return parse_official_result_page(soup), response.url


def _final_time(record: dict[str, Any], session: RateLimitedSession) -> tuple[str, str]:
    code = VENUE_CODES.get(str(record.get("venue", "")))
    if not code:
        return "", ""
    params = {"jcd": code, "hd": str(record["date"]).replace("-", "")}
    response = session.get(RACE_INDEX_URL, params=params)
    soup = soup_from(response)
    # 原則12R優勝戦。DOM行から最後の時刻を採用する。
    for row in soup.select("tr,li,div"):
        text = clean_text(row.get_text(" ", strip=True))
        if not re.search(r"(^|\D)12R(\D|$)", text):
            continue
        times = extract_times(text)
        if times:
            return times[-1], response.url
    text = soup.get_text(" ", strip=True)
    match = re.search(r"12R.{0,500}", text)
    if match:
        times = extract_times(match.group(0))
        if times:
            return times[-1], response.url
    return "", response.url


def collect(records: list[dict[str, Any]], session: RateLimitedSession, logger: logging.Logger) -> SourceResult:
    targets = [(index, record) for index, record in enumerate(records) if record.get("sport") == "boat"]
    if not targets:
        return SourceResult(NAME, True, [], [], [])
    patches: list[Patch] = []
    fetched: list[str] = []
    warnings: list[str] = []
    today = now_jst().date()
    try:
        schedule_patches, schedule_urls, schedule_warnings = _schedule_patches(records, session)
        patches.extend(schedule_patches)
        fetched.extend(schedule_urls)
        warnings.extend(schedule_warnings)

        for index, record in targets:
            result_fields: dict[str, str] = {}
            try:
                race_date = dt.date.fromisoformat(str(record["date"]))
                if race_date <= today:
                    result_fields, result_url = _official_result(record, session)
                    if result_url:
                        fetched.append(result_url)
                    if result_fields:
                        patches.append(Patch(index, result_fields, NAME, result_url, "BOAT RACE公式12R結果"))
            except Exception as exc:
                warnings.append(f"{record['date']} {record.get('venue','')}: 公式結果取得を見送り ({exc})")

            # 結果ページで時刻が取れない開催前・公開前だけ、公式レース一覧を補完利用する。
            if "time" not in result_fields:
                try:
                    time_value, url = _final_time(record, session)
                    if url:
                        fetched.append(url)
                    if time_value:
                        patches.append(Patch(index, {"time": time_value}, NAME, url, "BOAT RACE公式12R締切予定時刻"))
                except Exception as exc:
                    warnings.append(f"{record['date']} {record.get('venue','')}: 時刻取得を見送り ({exc})")
        return SourceResult(NAME, True, patches, list(dict.fromkeys(fetched)), warnings)
    except Exception as exc:
        logger.exception("ボートレースの取得に失敗しました")
        return SourceResult(NAME, False, patches, fetched, warnings, str(exc))
