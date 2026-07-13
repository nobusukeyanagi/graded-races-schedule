from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


RACES_PATH = Path("races.json")
JST = ZoneInfo("Asia/Tokyo")
DISCORD_MAX_LENGTH = 1900

SPORT_NAMES = {
    "jra": "JRA",
    "nar": "地方競馬",
    "boat": "ボートレース",
    "keirin": "競輪",
    "auto": "オートレース",
}

SPORT_ORDER = {
    "jra": 0,
    "nar": 1,
    "boat": 2,
    "keirin": 3,
    "auto": 4,
}


def get_target_date() -> str:
    """手動実行時はNOTIFY_DATE、通常実行時は日本時間の当日を使う。"""
    specified = os.environ.get("NOTIFY_DATE", "").strip()

    if specified:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", specified):
            raise ValueError("NOTIFY_DATEはYYYY-MM-DD形式で指定してください。")
        return specified

    return datetime.now(JST).strftime("%Y-%m-%d")


def get_site_url() -> str:
    """
    SITE_URLが設定されていればそれを使用。
    未設定ならGITHUB_REPOSITORYからGitHub PagesのURLを組み立てる。
    """
    configured = os.environ.get("SITE_URL", "").strip()

    if configured:
        if configured.endswith("index.html"):
            return configured
        return configured.rstrip("/") + "/index.html"

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if "/" not in repository:
        raise ValueError(
            "SITE_URLが未設定で、GITHUB_REPOSITORYからも公開URLを判定できません。"
        )

    owner, repo_name = repository.split("/", 1)

    if repo_name.lower() == f"{owner.lower()}.github.io":
        return f"https://{owner}.github.io/index.html"

    return f"https://{owner}.github.io/{repo_name}/index.html"


def load_races() -> list[dict[str, Any]]:
    if not RACES_PATH.exists():
        raise FileNotFoundError("races.jsonが見つかりません。")

    payload = json.loads(RACES_PATH.read_text(encoding="utf-8"))

    if not isinstance(payload, list):
        raise ValueError("races.jsonの最上位は配列である必要があります。")

    return [race for race in payload if isinstance(race, dict)]


def time_value(value: str) -> int:
    if re.fullmatch(r"\d{2}:\d{2}", value):
        hour, minute = map(int, value.split(":"))
        return hour * 60 + minute

    # 時刻未定は時刻確定済みレースの後ろ
    return 24 * 60 + 1


def format_race(race: dict[str, Any]) -> str:
    time_text = str(race.get("time", "")).strip() or "時刻未定"
    sport = SPORT_NAMES.get(
        str(race.get("sport", "")).strip(),
        str(race.get("sport", "")).strip(),
    )
    venue = str(race.get("venue", "")).strip()
    grade = str(race.get("grade", "")).strip()
    name = str(race.get("name", "")).strip()

    values = [time_text, sport, venue, grade, name]
    return " ".join(value for value in values if value)


def build_messages(
    target_date: str,
    site_url: str,
    races: list[dict[str, Any]],
) -> list[str]:
    todays_races = [
        race
        for race in races
        if str(race.get("date", "")).strip() == target_date
    ]

    todays_races.sort(
        key=lambda race: (
            time_value(str(race.get("time", "")).strip()),
            SPORT_ORDER.get(str(race.get("sport", "")).strip(), 99),
            str(race.get("venue", "")).strip(),
            str(race.get("name", "")).strip(),
        )
    )

    linked_title = f"[🏁本日のグレードレース](<{site_url}>)"

    if not todays_races:
        return [
            f"{linked_title}\n"
            "グレードレースはありません"
        ]

    race_lines = [format_race(race) for race in todays_races]

    # Discordの1投稿2000文字制限を超えないよう、必要なら分割する。
    messages: list[str] = []
    current_lines = [linked_title]

    for line in race_lines:
        candidate = "\n".join(current_lines + [line])

        if len(candidate) <= DISCORD_MAX_LENGTH:
            current_lines.append(line)
            continue

        messages.append("\n".join(current_lines))
        current_lines = [
            f"[🏁本日のグレードレース（続き）](<{site_url}>)",
            line,
        ]

    if current_lines:
        messages.append("\n".join(current_lines))

    return messages


def send_message(webhook_url: str, message: str) -> None:
    payload = json.dumps(
        {
            "content": message,
            "username": "公営競技重賞日程",
            "allowed_mentions": {"parse": []},
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "graded-races-schedule/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 204):
                raise RuntimeError(
                    f"Discord通知に失敗しました: HTTP {response.status}"
                )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord通知に失敗しました: HTTP {exc.code} {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Discordへ接続できませんでした: {exc.reason}"
        ) from exc


def main() -> int:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        print("DISCORD_WEBHOOK_URLが設定されていません。", file=sys.stderr)
        return 1

    try:
        target_date = get_target_date()
        site_url = get_site_url()
        races = load_races()
        messages = build_messages(target_date, site_url, races)

        for message in messages:
            send_message(webhook_url, message)

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        RuntimeError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    count = sum(
        1
        for race in races
        if str(race.get("date", "")).strip() == target_date
    )

    print(
        f"{target_date}のグレードレース{count}件を"
        f"Discordへ通知しました。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
