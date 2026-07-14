from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

START = date(2026, 1, 1)
END = date(2026, 6, 30)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="2026年1月〜6月の発走時刻に空欄がないことを検証します。"
    )
    parser.add_argument("--races", default="races.json")
    parser.add_argument("--output", default="h1_2026_time_verification.json")
    args = parser.parse_args()

    payload: list[dict[str, Any]] = json.loads(Path(args.races).read_text(encoding="utf-8"))
    missing = []
    for record in payload:
        try:
            value = parse_date(str(record.get("date", "")))
        except ValueError:
            continue
        if START <= value <= END and not str(record.get("time", "")).strip():
            missing.append({
                "date": record.get("date", ""),
                "sport": record.get("sport", ""),
                "venue": record.get("venue", ""),
                "grade": record.get("grade", ""),
                "name": record.get("name", ""),
            })

    result = {
        "range": {"start": START.isoformat(), "end": END.isoformat()},
        "complete": not missing,
        "missing_count": len(missing),
        "missing": missing,
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if missing:
        print(f"2026年1月〜6月の発走時刻に {len(missing)} 件の空欄が残っています。")
        return 1
    print("2026年1月〜6月の発走時刻は全件入力済みです。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
