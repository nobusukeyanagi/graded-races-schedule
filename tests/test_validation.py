import datetime as dt
from pathlib import Path
import sys

from bs4 import BeautifulSoup

# 本番と同じく、gradedracesを作業ディレクトリとしてscriptsを読み込む。
PROJECT_DIR = Path(__file__).resolve().parents[1] / "gradedraces"
sys.path.insert(0, str(PROJECT_DIR))

from scripts.common import Patch, merge_patches, same_name, strip_edition  # noqa: E402
from scripts.sources.autorace import grade_schedule_patches  # noqa: E402
from scripts.sources.boatrace import parse_official_result_page  # noqa: E402
from scripts.sources.keirin import (  # noqa: E402
    extract_supplemental_result_fields,
    extract_supplemental_start_time,
    schedule_patches,
)
from scripts.update_races import select_smart_target_indices  # noqa: E402


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_strip_edition() -> None:
    assert strip_edition("第35回 アサヒビールカップ") == "アサヒビールカップ"


def test_same_name() -> None:
    assert same_name("フェアリーステークス", "フェアリーS")


def test_empty_patch_does_not_delete_existing_value() -> None:
    records = [
        {
            "date": "2026-01-01",
            "sport": "jra",
            "venue": "中山",
            "grade": "GⅠ",
            "name": "テスト",
            "winner": "既存",
        }
    ]
    patched, changes = merge_patches(
        records,
        [Patch(0, {"winner": ""}, "test", "https://example.com")],
    )
    assert patched[0]["winner"] == "既存"
    assert changes == []


def test_smart_selection_retries_unresolved_instead_of_only_fixed_lookback() -> None:
    records = [
        {"date": "2026-07-18", "sport": "boat", "time": "16:35", "winner": ""},
        {"date": "2026-07-18", "sport": "nar", "time": "18:00", "winner": "入力済み"},
        {"date": "2026-05-01", "sport": "keirin", "time": "20:30", "winner": "入力済み"},
        {"date": "2026-07-30", "sport": "auto", "time": "", "winner": ""},
    ]
    indices, reasons = select_smart_target_indices(
        records,
        dt.date(2026, 7, 21),
        upcoming_days=14,
        unresolved_retry_days=90,
        recent_verification_days=2,
    )
    assert indices == [0, 3]
    assert "unresolved" in reasons[0]
    assert "upcoming" in reasons[3]


def test_boatrace_official_result_parser() -> None:
    parsed = parse_official_result_page(
        soup(
            """
            <div>締切予定時刻 10:37 11:03 11:32 12:01 12:30 12:59 13:33 14:07 14:42 15:18 15:56 16:35</div>
            <h3>優勝戦 1800m</h3>
            <table>
              <tr><th>着</th><th>枠</th><th>登録番号</th><th>ボートレーサー</th><th>レースタイム</th></tr>
              <tr><td>１</td><td>1</td><td>3845</td><td>中谷 朋子</td><td>1'51&quot;0</td></tr>
            </table>
            """
        )
    )
    assert parsed == {"time": "16:35", "winner": "中谷 朋子"}


def test_keirin_official_schedule_winner_parser() -> None:
    records = [
        {
            "date": "2026-07-20",
            "sport": "keirin",
            "venue": "高知",
            "grade": "GⅡ",
            "name": "サマーナイトフェスティバル",
            "time": "",
            "winner": "",
        }
    ]
    patches = schedule_patches(
        records,
        soup(
            """
            <table>
              <tr><td>7月</td><td>第２２回サマーナイトフェスティバル</td><td>高知(17～20)</td><td>88億4649万2400円</td><td>吉田 拓矢</td></tr>
            </table>
            """
        ),
        "https://keirin.jp/pc/graderaceschedule",
    )
    assert len(patches) == 1
    assert patches[0].fields == {"winner": "吉田 拓矢"}


def test_keirin_supplemental_start_time_parser() -> None:
    assert (
        extract_supplemental_start_time(
            soup("<div>2000m 発走時間 20:30 締切予定 20:25</div>")
        )
        == "20:30"
    )


def test_keirin_supplemental_result_parser() -> None:
    parsed = extract_supplemental_result_fields(
        soup(
            """
            <div>2000m 発走時間 20:30 締切予定 20:25</div>
            <table>
              <tr><th>着</th><th>車番</th><th>選手名</th><th>府県</th></tr>
              <tr><td>1</td><td>9</td><td>吉田 拓矢</td><td>茨城</td></tr>
            </table>
            """
        )
    )
    assert parsed == {"time": "20:30", "winner": "吉田 拓矢"}


def test_autorace_official_schedule_winner_parser() -> None:
    records = [
        {
            "date": "2026-07-20",
            "sport": "auto",
            "venue": "川口",
            "grade": "GⅠ",
            "name": "キューポラ杯",
            "time": "20:45",
            "winner": "",
        }
    ]
    patches = grade_schedule_patches(
        records,
        soup(
            """
            <table>
              <tr><td>GI</td><td>キューポラ杯(ナイター)</td><td>2026年7月16日(木)～7月20日(月・祝)</td><td>川口</td><td>青山 周平</td><td>14億6220万3300円</td></tr>
            </table>
            """
        ),
        "https://autorace.jp/calendar/graderace/",
    )
    assert len(patches) == 1
    assert patches[0].fields == {"winner": "青山 周平"}
