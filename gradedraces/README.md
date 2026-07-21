# 公営競技重賞日程

`zenrace`内の、公営競技グレードレース日程ページです。

## 公開URL

https://nobusukeyanagi.github.io/zenrace/gradedraces/

## 対象競技

- JRA
- 地方競馬
- ボートレース
- 競輪
- オートレース

## 主なファイル

```text
gradedraces/
├─ index.html
├─ graded_races_schedule.html
├─ races.json
├─ config.json
├─ changes.json
├─ source_status.json
├─ incomplete_records.json
├─ discord_notification_state.json
├─ requirements.txt
└─ scripts/
```

- `races.json`：レース一覧データ
- `graded_races_schedule.html`：更新元となるHTML
- `index.html`：公開用HTML。自動更新時に上記HTMLから同期
- `changes.json`：直近の自動更新差分と更新対象の選択理由
- `source_status.json`：各取得先の取得状況、参照URL、警告
- `incomplete_records.json`：終了済みの未解決項目と、開催前の時刻未公開項目
- `discord_notification_state.json`：当日の重複通知を防ぐ状態ファイル

## 通常更新の考え方

`.github/workflows/graded-race-update.yml`の通常更新は、単純な「過去何日～未来何日」ではなく、情報の状態から対象を選びます。

1. 当日から14日後までの登録済みレースを確認し、番組公開後の発走時刻を取得
2. 終了済みで時刻または優勝者が空欄のレースは、最長90日間、解決するまで毎回再取得
3. 直近2日分は入力済みでも再確認し、公式側の公開遅延や訂正を反映
4. 終了済みの空欄は`incomplete_records.json`とGitHub Actionsの警告に残す

通常更新は日本時間の次の時刻に実行します。

```text
02:17 / 08:17 / 14:17 / 20:17 / 23:17
```

開催番組の公開後と、ナイター終了後の公式結果公開を同日中に拾うための時間設定です。

## 取得先の優先順位

原則として、各競技の公式サイトを直接参照します。

- ボートレース
  - BOAT RACE公式グレード日程：正式名称
  - BOAT RACE公式12R結果ページ：発走時刻・優勝者
  - BOAT RACE公式レース一覧：開催前の12R時刻
- 競輪
  - KEIRIN.JP公式グレードレース開催日程：優勝者
  - KEIRIN.JPの一般レース一覧が画面遷移依存のため、当日結果と発走時刻をOddsPark公開ページで補完
  - 翌日以降はKEIRIN.JP公式グレード日程の優勝者で再確認
- オートレース
  - AutoRace.JP公式年間グレードレース日程：優勝者
  - AutoRace.JP公式Program／RaceResult：発走時刻・個別結果
- JRA・地方競馬
  - 各公式サイトの登録済み取得処理を使用

公式サイトから取得できた既存値を、補完取得の空欄で消すことはありません。

## 四半期監査

1・4・7・10月には、登録済み期間を分割して翌年末まで再確認します。通常更新の未解決再試行とは別に、長期日程の変更や表記揺れを確認するための処理です。

## GitHub Actionsの確認

```text
Actions
→ Graded-race Update
```

実行結果のSummaryには次の件数が表示されます。

- 取得対象
- 変更件数
- 終了済み未解決件数
- 開催前の時刻未公開件数
- 競技別の取得成功・警告件数

## 手動実行

```text
Actions
→ Graded-race Update
→ Run workflow
```

- `mode: daily`：通常のスマート更新
- `base_date`：空欄なら日本時間の当日
- `mode: quarterly`：指定期間の一括再確認
- `start_date` / `end_date`：四半期監査の対象期間

GitHub PagesのSourceは`GitHub Actions`を使用します。
