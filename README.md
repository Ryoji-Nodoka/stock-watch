# 日本高配当株 ウォッチリスト・アラートツール

日本株の候補銘柄を登録しておき、株価が指定した下落率に達したら
macOS のネイティブ通知で知らせてくれる CLI ツールです。

## セットアップ

```bash
# 依存ライブラリのインストール
pip3 install -r requirements.txt

# 高配当株サンプル銘柄を一括登録（初回のみ）
python3 stock_watch.py init
```

## コマンド一覧

### 銘柄を追加
```bash
python3 stock_watch.py add <証券コード> [オプション]

# 例
python3 stock_watch.py add 7203                          # 基準株価を自動取得・閾値5%
python3 stock_watch.py add 7203 --threshold 8.0          # 閾値を8%に設定
python3 stock_watch.py add 7203 --memo "優待あり"        # メモ付き
python3 stock_watch.py add 7203 --sector "自動車" --threshold 5.0 --memo "トヨタ"
```

### 一覧表示
```bash
python3 stock_watch.py list
```

### 株価チェック（アラート判定）
```bash
python3 stock_watch.py check
```
- 全銘柄の現在株価を yfinance で取得
- 基準株価からの下落率がアラート閾値を超えた銘柄に macOS 通知を送信
- ターミナルに結果一覧を表示

### 銘柄を削除
```bash
python3 stock_watch.py delete 7203
```

### 設定を更新
```bash
python3 stock_watch.py update 7203 --threshold 10.0      # 閾値変更
python3 stock_watch.py update 7203 --memo "新メモ"       # メモ変更
python3 stock_watch.py update 7203 --reset-base          # 基準株価を現在株価にリセット
```

## 自動実行（cron 設定）

毎営業日 9:30 に自動チェックする例:

```bash
# crontab を開く
crontab -e

# 以下を追加（パスは環境に合わせて変更）
30 9 * * 1-5 cd /Users/<ユーザー名>/Claude/stock-watch && python3 stock_watch.py check
```

ログをファイルに残したい場合:
```
30 9 * * 1-5 cd /path/to/stock-watch && python3 stock_watch.py check >> check.log 2>&1
```

## 出力例

```
株価チェック中... (2026-04-13 09:30:01)
────────────────────────────────────────────────────────────────────────────────
  コード  銘柄名                 基準株価    現在株価    変化率   状態
────────────────────────────────────────────────────────────────────────────────
  8058   三菱商事              3,200円    2,990円    -6.56%  🔴 アラート
  8031   三井物産              2,850円    2,880円    +1.05%  🟢 上昇中
  9432   NTT                    155円      152円    -1.94%  🟡 下落中
────────────────────────────────────────────────────────────────────────────────

  ⚠  1 銘柄がアラート閾値を超えています！
```

## データ構造

SQLite ファイル `watchlist.db` に保存されます。

| カラム          | 型      | 説明                         |
|----------------|---------|------------------------------|
| id             | INTEGER | 自動採番                     |
| code           | TEXT    | 証券コード（例: 7203）       |
| name           | TEXT    | 銘柄名                       |
| sector         | TEXT    | 業種                         |
| base_price     | REAL    | 登録時の基準株価             |
| alert_threshold| REAL    | アラート発動の下落率（%）    |
| memo           | TEXT    | メモ                         |
| created_at     | TEXT    | 登録日時                     |

## 初期登録銘柄（`init` コマンド）

| 証券コード | 銘柄名                     | 業種         |
|-----------|---------------------------|--------------|
| 8058      | 三菱商事                   | 商社         |
| 8031      | 三井物産                   | 商社         |
| 9432      | NTT                       | 通信         |
| 8316      | 三井住友フィナンシャルグループ | 金融       |
| 5020      | ENEOSホールディングス       | エネルギー   |
| 8053      | 住友商事                   | 商社         |
| 2914      | JT                        | 食品・たばこ |
| 4502      | 武田薬品工業               | 医薬品       |

## 注意事項

- yfinance の株価は **遅延データ**（15〜20分遅れ）です
- 市場が閉まっている時間帯は最終終値が返されます
- macOS 通知は `osascript` を使用するため、macOS 専用です
