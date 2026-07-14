from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

START = date(2026, 1, 1)
END = date(2026, 6, 30)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("races.json の最上位は配列である必要があります")
    return payload


def in_h1(record: dict[str, Any]) -> bool:
    try:
        value = parse_date(str(record.get("date", "")))
    except ValueError:
        return False
    return START <= value <= END


def is_missing(record: dict[str, Any]) -> bool:
    return in_h1(record) and not str(record.get("time", "")).strip()


def record_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(record.get("date", "")),
        str(record.get("sport", "")),
        str(record.get("venue", "")),
        str(record.get("name", "")),
    )


def missing_records(path: Path) -> list[dict[str, Any]]:
    return [record for record in load_records(path) if is_missing(record)]


def dateranges(start: date, end: date, width: int):
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=width - 1))
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def run_update(chunk_start: date, chunk_end: date) -> dict[str, Any]:
    center = chunk_start + (chunk_end - chunk_start) // 2
    before = (center - chunk_start).days
    after = (chunk_end - center).days
    command = [
        sys.executable,
        "-m",
        "scripts.update_races",
        "--date",
        center.isoformat(),
        "--before",
        str(before),
        "--after",
        str(after),
        "--fail-if-all-sources-fail",
    ]
    print(f"[time-backfill] {chunk_start} - {chunk_end}", flush=True)
    completed = subprocess.run(command, check=False)
    return {
        "start": chunk_start.isoformat(),
        "end": chunk_end.isoformat(),
        "returncode": completed.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="2026年1月〜6月の登録レースを公式取得処理で再照合し、発走時刻を補完します。"
    )
    parser.add_argument("--races", default="races.json")
    parser.add_argument("--batch-days", type=int, default=7)
    parser.add_argument("--retry-passes", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--report", default="h1_2026_time_backfill_report.json")
    args = parser.parse_args()

    if not 1 <= args.batch_days <= 14:
        raise ValueError("batch-days は1〜14で指定してください")
    if not 0 <= args.retry_passes <= 5:
        raise ValueError("retry-passes は0〜5で指定してください")
    if args.delay < 0:
        raise ValueError("delay は0以上で指定してください")

    races_path = Path(args.races)
    report_path = Path(args.report)
    before_records = load_records(races_path)
    before_by_key = {record_key(r): dict(r) for r in before_records if in_h1(r)}
    initial_missing = [r for r in before_records if is_missing(r)]
    runs: list[dict[str, Any]] = []

    # 第1段階: 半年を小さな期間に分割し、全対象を公式サイトで再照合する。
    for chunk_start, chunk_end in dateranges(START, END, args.batch_days):
        current_missing_dates = {
            parse_date(str(r["date"])) for r in missing_records(races_path)
        }
        if not any(chunk_start <= value <= chunk_end for value in current_missing_dates):
            continue
        runs.append(run_update(chunk_start, chunk_end))
        if args.delay:
            time.sleep(args.delay)

    # 第2段階: 残った空欄の日だけを日単位で再試行する。
    for pass_no in range(1, args.retry_passes + 1):
        remaining_dates = sorted({
            parse_date(str(r["date"])) for r in missing_records(races_path)
        })
        if not remaining_dates:
            break
        print(
            f"[time-backfill] retry pass {pass_no}: {len(remaining_dates)} dates",
            flush=True,
        )
        for value in remaining_dates:
            result = run_update(value, value)
            result["retry_pass"] = pass_no
            runs.append(result)
            if args.delay:
                time.sleep(args.delay)

    # 地方競馬のH/M区分など、同時に公式表記へ正規化する。
    normalize = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.normalize_grades",
            str(races_path),
            "--start",
            START.isoformat(),
        ],
        check=False,
    )

    after_records = load_records(races_path)
    final_missing = [r for r in after_records if is_missing(r)]
    filled: list[dict[str, Any]] = []
    for record in after_records:
        if not in_h1(record) or not str(record.get("time", "")).strip():
            continue
        key = record_key(record)
        prior = before_by_key.get(key)
        if prior is not None and not str(prior.get("time", "")).strip():
            filled.append({
                "date": record.get("date", ""),
                "sport": record.get("sport", ""),
                "venue": record.get("venue", ""),
                "name": record.get("name", ""),
                "time": record.get("time", ""),
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": {"start": START.isoformat(), "end": END.isoformat()},
        "initial_missing_count": len(initial_missing),
        "filled_count": len(filled),
        "remaining_missing_count": len(final_missing),
        "remaining_by_sport": dict(Counter(str(r.get("sport", "")) for r in final_missing)),
        "normalize_returncode": normalize.returncode,
        "runs": runs,
        "filled": filled,
        "remaining": [
            {
                "date": r.get("date", ""),
                "sport": r.get("sport", ""),
                "venue": r.get("venue", ""),
                "grade": r.get("grade", ""),
                "name": r.get("name", ""),
            }
            for r in final_missing
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"[time-backfill] initial={len(initial_missing)} "
        f"filled={len(filled)} remaining={len(final_missing)}",
        flush=True,
    )
    if normalize.returncode != 0:
        return 1
    if runs and all(int(run["returncode"]) != 0 for run in runs):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
