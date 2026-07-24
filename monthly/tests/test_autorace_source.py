from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from monthly.scripts.sources import autorace


class FakeSession:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    def get(self, url: str, **kwargs):
        if url not in self.responses:
            raise AssertionError(f"unexpected URL: {url}")
        return SimpleNamespace(text=self.responses[url], url=url)


def all_venue_responses(html: str, target: date) -> dict[str, str]:
    return {
        f"https://autorace.jp/race_info/Program/{slug}/{target.isoformat()}_01": html
        for slug in autorace.VENUES.values()
    }


class AutoRaceSourceTests(unittest.TestCase):
    def test_fallback_page_is_not_counted_as_all_five_venues(self) -> None:
        target = date(2026, 7, 24)
        # 非開催場URLでも飯塚ページが返るケースを再現。
        # ナビには全5場名があるため、本文全体の部分一致では誤判定する。
        html = """
        <html>
          <head>
            <title>出走表 | 飯塚オート | レース情報 | AutoRace.JP</title>
            <meta property="og:title" content="出走表 | 飯塚オート">
          </head>
          <body>
            <nav>川口 伊勢崎 浜松 飯塚 山陽</nav>
            <main>
              <h1>飯塚オート 出走表</h1>
              <h2>令和8年度飯塚市営 普通開催 7/24～</h2>
              <div>1R 発走 15:24</div>
              <div>2R 発走 15:49</div>
            </main>
            <footer>ミッドナイト特設</footer>
          </body>
        </html>
        """
        result = autorace.collect(target, FakeSession(all_venue_responses(html, target)))

        self.assertTrue(result.ok)
        self.assertEqual(
            result.entries,
            [{"sport": "auto", "venue": "飯塚", "grade": "普通", "session": "night"}],
        )
        self.assertEqual(len(result.warnings), 4)
        self.assertTrue(all("飯塚の出走表" in warning for warning in result.warnings))

    def test_footer_midnight_text_does_not_override_first_race_time(self) -> None:
        target = date(2026, 7, 24)
        responses: dict[str, str] = {}
        for venue, slug in autorace.VENUES.items():
            url = f"https://autorace.jp/race_info/Program/{slug}/{target.isoformat()}_01"
            if venue == "飯塚":
                responses[url] = """
                <html><head><title>飯塚オート 出走表</title></head><body>
                  <main><h1>飯塚オート</h1><h2>普通開催</h2><div>1R 発走:15:24</div></main>
                  <footer>ミッドナイト特設</footer>
                </body></html>
                """
            else:
                responses[url] = "<html><body>本日の開催情報はありません。</body></html>"

        result = autorace.collect(target, FakeSession(responses))
        self.assertTrue(result.ok)
        self.assertEqual(result.entries[0]["session"], "night")

    def test_unidentifiable_race_page_fails_safely(self) -> None:
        target = date(2026, 7, 24)
        html = """
        <html><head><title>出走表 | AutoRace.JP</title></head><body>
          <nav>川口 伊勢崎 浜松 飯塚 山陽</nav>
          <main><h1>本日の出走表</h1><div>1R 発走 15:24</div></main>
        </body></html>
        """
        result = autorace.collect(target, FakeSession(all_venue_responses(html, target)))

        self.assertFalse(result.ok)
        self.assertEqual(result.entries, [])
        self.assertIn("開催場を確定できませんでした", result.error)


if __name__ == "__main__":
    unittest.main()
