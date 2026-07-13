from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CHANGES_PATH = Path("changes.json")
MAX_ITEMS = 10
DISCORD_MAX_LENGTH = 1900


def extract_changes(payload: Any) -> list[dict[str, Any]]:
    """changes.json の複数形式に対応して変更一覧を取り出す。"""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        raise ValueError("changes.json の最上位は配列またはオブジェクトである必要があります。")

    # この自動更新プログラムの標準形式を優先
    for key in ("changes", "items", "updates", "diffs"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    # added / updated / removed のように分類されている形式にも対応
    merged: list[dict[str, Any]] = []
    for category in ("added", "updated", "removed"):
        value = payload.get(category)
        if not isinstance(value, list):
            continue

        for item in value:
            if not isinstance(item, dict):
                continue
            copied = dict(item)
            copied.setdefault("category", category)
            merged.append(copied)

    return merged


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def format_change(change: dict[str, Any]) -> str:
    """変更1件をDiscord表示用に整形する。"""
    race = change.get("race")
    if not isinstance(race, dict):
        race = {}

    date = first_text(change.get("date"), race.get("date"))
    venue = first_text(change.get("venue"), race.get("venue"))
    name = first_text(change.get("name"), race.get("name"))

    title_parts = [part for part in (date, venue, name) if part]
    title = " ".join(title_parts) or "日程情報"

    field = first_text(
        change.get("field"),
        change.get("key"),
        change.get("property"),
    )
    before = first_text(
        change.get("before"),
        change.get("old"),
        change.get("previous"),
        change.get("from"),
    )
    after = first_text(
        change.get("after"),
        change.get("new"),
        change.get("current"),
        change.get("to"),
    )
    message = first_text(
        change.get("detail"),
        change.get("message"),
        change.get("description"),
    )

    lines = [f"**{title}**"]

    if message:
        lines.append(message)
    elif field or before or after:
        label_map = {
            "time": "発走時刻",
            "winner": "優勝者",
            "name": "レース名",
            "venue": "開催場",
            "grade": "グレード",
            "status": "開催状況",
        }
        label = label_map.get(field, field or "変更")
        before_text = before or "空欄"
        after_text = after or "空欄"
        lines.append(f"{label}：{before_text} → {after_text}")
    else:
        # 不明な形式でもJSON全体を出さず、主要項目だけ表示
        category = first_text(change.get("category"), change.get("type"))
        if category:
            lines.append(f"変更種別：{category}")

    source_url = first_text(
        change.get("source_url"),
        change.get("url"),
        change.get("source"),
    )
    if source_url.startswith(("https://", "http://")):
        lines.append(f"<{source_url}>")

    return "\n".join(lines)


def build_message(changes: list[dict[str, Any]]) -> str:
    lines = ["**公営競技重賞日程を更新しました**", ""]

    for change in changes[:MAX_ITEMS]:
        lines.append(format_change(change))
        lines.append("")

    if len(changes) > MAX_ITEMS:
        lines.append(f"ほか {len(changes) - MAX_ITEMS} 件の変更があります。")

    message = "\n".join(lines).strip()

    if len(message) > DISCORD_MAX_LENGTH:
        message = message[: DISCORD_MAX_LENGTH - 20].rstrip() + "\n…以下省略"

    return message


def send_to_discord(webhook_url: str, message: str) -> None:
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
                raise RuntimeError(f"Discord通知に失敗しました: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord通知に失敗しました: HTTP {exc.code} {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Discordへ接続できませんでした: {exc.reason}") from exc


def main() -> int:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL が設定されていません。", file=sys.stderr)
        return 1

    if not CHANGES_PATH.exists():
        print("changes.json がないため、Discord通知を行いません。")
        return 0

    try:
        payload = json.loads(CHANGES_PATH.read_text(encoding="utf-8"))
        changes = extract_changes(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"changes.json の読み込みに失敗しました: {exc}", file=sys.stderr)
        return 1

    if not changes:
        print("変更がないため、Discord通知を行いません。")
        return 0

    message = build_message(changes)

    try:
        send_to_discord(webhook_url, message)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Discordへ {len(changes)} 件の変更を通知しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
