import json
import os
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        print("DISCORD_WEBHOOK_URLが設定されていません。")
        return 1

    changes_path = Path("changes.json")

    if not changes_path.exists():
        print("changes.jsonがないため、通知しません。")
        return 0

    changes = json.loads(changes_path.read_text(encoding="utf-8"))

    if not changes:
        print("変更がないため、通知しません。")
        return 0

    lines = ["**公営競技重賞日程を更新しました**", ""]

    for change in changes[:10]:
        date = change.get("date", "")
        venue = change.get("venue", "")
        name = change.get("name", "")
        detail = change.get("detail", change.get("message", ""))

        title = " ".join(value for value in [date, venue, name] if value)
        lines.append(f"**{title}**")

        if detail:
            lines.append(str(detail))

        lines.append("")

    if len(changes) > 10:
        lines.append(f"ほか {len(changes) - 10} 件の変更があります。")

    message = "\n".join(lines)

    payload = json.dumps(
        {
            "content": message,
            "username": "公営競技重賞日程",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 204):
            raise RuntimeError(
                f"Discord通知に失敗しました: HTTP {response.status}"
            )

    print(f"Discordへ{len(changes)}件の変更を通知しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())