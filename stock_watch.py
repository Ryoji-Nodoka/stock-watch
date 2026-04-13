#!/usr/bin/env python3
"""
日本の高配当株 ウォッチリスト・アラートツール

使い方:
  python stock_watch.py add 7203 --threshold 5.0 --memo "トヨタ"
  python stock_watch.py list
  python stock_watch.py check
  python stock_watch.py delete 7203
  python stock_watch.py update 7203 --threshold 8.0

cron設定例（毎営業日 9:30 に自動チェック）:
  30 9 * * 1-5 cd /path/to/stock-watch && python3 stock_watch.py check
"""

import argparse
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    import yfinance as yf
except ImportError:
    print("エラー: yfinance がインストールされていません。")
    print("  pip3 install yfinance")
    sys.exit(1)

DB_PATH = Path(__file__).parent / "watchlist.db"

# ──────────────────────────────────────────
# DB 初期化
# ──────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT    NOT NULL UNIQUE,
            name            TEXT    NOT NULL,
            sector          TEXT    DEFAULT '',
            base_price      REAL    NOT NULL,
            alert_threshold REAL    NOT NULL DEFAULT 5.0,
            memo            TEXT    DEFAULT '',
            created_at      TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


# ──────────────────────────────────────────
# yfinance ヘルパー
# ──────────────────────────────────────────

def fetch_price(code: str) -> Tuple[Optional[float], str]:
    """(現在株価, 銘柄名) を返す。取得失敗時は (None, '') を返す。"""
    ticker_symbol = f"{code}.T"
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        name = info.get("longName") or info.get("shortName") or ""
        if price is None:
            return None, name
        return float(price), name
    except Exception as e:
        return None, ""


def validate_code(code: str) -> Tuple[Optional[float], str]:
    """証券コードの存在確認。(価格, 名前) または (None, '') を返す。"""
    return fetch_price(code)


# ──────────────────────────────────────────
# macOS 通知
# ──────────────────────────────────────────

def send_notification(title: str, body: str) -> None:
    script = f'display notification "{body}" with title "{title}" sound name "Basso"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # 通知失敗はサイレントスキップ（ターミナル表示で代替）
        pass
    except FileNotFoundError:
        pass  # macOS 以外の環境


# ──────────────────────────────────────────
# コマンド実装
# ──────────────────────────────────────────

def cmd_add(args) -> None:
    code = args.code.strip().lstrip("0") or args.code.strip()
    # ゼロ埋め正規化: 4桁に揃える
    code = args.code.strip().zfill(4) if args.code.strip().isdigit() else args.code.strip()

    conn = init_db()

    # 重複チェック
    existing = conn.execute("SELECT id FROM watchlist WHERE code = ?", (code,)).fetchone()
    if existing:
        print(f"エラー: {code} はすでに登録されています。")
        conn.close()
        sys.exit(1)

    print(f"株価を取得中... ({code}.T)")
    price, name = validate_code(code)

    if price is None:
        print(f"エラー: 証券コード {code} の株価を取得できませんでした。")
        print("  コードが正しいか確認してください（例: 7203）")
        conn.close()
        sys.exit(1)

    # 銘柄名はオプション引数で上書き可能
    display_name = args.name if args.name else (name or code)

    conn.execute(
        """INSERT INTO watchlist (code, name, sector, base_price, alert_threshold, memo, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            code,
            display_name,
            args.sector or "",
            price,
            args.threshold,
            args.memo or "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()

    print(f"✓ 登録完了")
    print(f"  銘柄: {display_name} ({code})")
    print(f"  基準株価: {price:,.0f} 円")
    print(f"  アラート閾値: -{args.threshold}%")
    if args.memo:
        print(f"  メモ: {args.memo}")


def cmd_list(args) -> None:
    conn = init_db()
    rows = conn.execute(
        "SELECT * FROM watchlist ORDER BY created_at"
    ).fetchall()
    conn.close()

    if not rows:
        print("登録銘柄なし。`python stock_watch.py add <証券コード>` で追加してください。")
        return

    # ヘッダー
    print(f"\n{'─'*78}")
    print(f"  {'コード':<6} {'銘柄名':<20} {'業種':<12} {'基準株価':>8}  {'閾値':>5}  {'メモ'}")
    print(f"{'─'*78}")
    for r in rows:
        memo_short = (r["memo"] or "")[:18]
        print(
            f"  {r['code']:<6} {r['name']:<20} {(r['sector'] or ''):<12} "
            f"{r['base_price']:>8,.0f}円  -{r['alert_threshold']:>4.1f}%  {memo_short}"
        )
    print(f"{'─'*78}")
    print(f"  合計: {len(rows)} 銘柄\n")


def cmd_check(args) -> None:
    conn = init_db()
    rows = conn.execute("SELECT * FROM watchlist ORDER BY code").fetchall()
    conn.close()

    if not rows:
        print("登録銘柄なし。")
        return

    print(f"\n株価チェック中... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"{'─'*80}")
    print(f"  {'コード':<6} {'銘柄名':<20} {'基準株価':>8}  {'現在株価':>8}  {'変化率':>7}  状態")
    print(f"{'─'*80}")

    alert_count = 0

    for r in rows:
        current_price, _ = fetch_price(r["code"])

        if current_price is None:
            print(f"  {r['code']:<6} {r['name']:<20} {'—':>8}   {'取得失敗':>8}  {'—':>7}  ⚠ スキップ")
            continue

        change_pct = (current_price - r["base_price"]) / r["base_price"] * 100
        is_alert = change_pct <= -r["alert_threshold"]

        # 表示用文字列
        change_str = f"{change_pct:+.2f}%"
        if is_alert:
            status = "🔴 アラート"
            alert_count += 1
        elif change_pct < 0:
            status = "🟡 下落中"
        elif change_pct > 0:
            status = "🟢 上昇中"
        else:
            status = "⚪ 変化なし"

        print(
            f"  {r['code']:<6} {r['name']:<20} "
            f"{r['base_price']:>8,.0f}円  {current_price:>8,.0f}円  {change_str:>7}  {status}"
        )

        # macOS 通知
        if is_alert:
            notif_body = (
                f"{r['name']}({r['code']}) が {change_pct:.1f}% 下落しています"
                f"（現在: {current_price:,.0f}円）"
            )
            send_notification("株価アラート", notif_body)

    print(f"{'─'*80}")
    if alert_count > 0:
        print(f"\n  ⚠  {alert_count} 銘柄がアラート閾値を超えています！\n")
    else:
        print(f"\n  ✓ アラート対象なし\n")


def cmd_delete(args) -> None:
    code = args.code.strip().zfill(4) if args.code.strip().isdigit() else args.code.strip()
    conn = init_db()
    row = conn.execute("SELECT name FROM watchlist WHERE code = ?", (code,)).fetchone()
    if not row:
        print(f"エラー: {code} はウォッチリストに存在しません。")
        conn.close()
        sys.exit(1)

    conn.execute("DELETE FROM watchlist WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    print(f"✓ 削除しました: {row['name']} ({code})")


def cmd_update(args) -> None:
    code = args.code.strip().zfill(4) if args.code.strip().isdigit() else args.code.strip()
    conn = init_db()
    row = conn.execute("SELECT * FROM watchlist WHERE code = ?", (code,)).fetchone()
    if not row:
        print(f"エラー: {code} はウォッチリストに存在しません。")
        conn.close()
        sys.exit(1)

    updates = []
    params = []

    if args.threshold is not None:
        updates.append("alert_threshold = ?")
        params.append(args.threshold)
    if args.memo is not None:
        updates.append("memo = ?")
        params.append(args.memo)
    if args.reset_base:
        print(f"基準株価を更新中...")
        price, _ = fetch_price(code)
        if price is None:
            print(f"エラー: 株価を取得できませんでした。")
            conn.close()
            sys.exit(1)
        updates.append("base_price = ?")
        params.append(price)
        print(f"  新しい基準株価: {price:,.0f} 円")

    if not updates:
        print("更新項目がありません。--threshold / --memo / --reset-base を指定してください。")
        conn.close()
        return

    params.append(code)
    conn.execute(f"UPDATE watchlist SET {', '.join(updates)} WHERE code = ?", params)
    conn.commit()
    conn.close()
    print(f"✓ 更新しました: {row['name']} ({code})")
    if args.threshold is not None:
        print(f"  アラート閾値: -{args.threshold}%")
    if args.memo is not None:
        print(f"  メモ: {args.memo}")


# ──────────────────────────────────────────
# 初期データ登録
# ──────────────────────────────────────────

INITIAL_STOCKS = [
    ("8058", "三菱商事",           "商社",       5.0),
    ("8031", "三井物産",           "商社",       5.0),
    ("9432", "NTT",               "通信",       5.0),
    ("8316", "三井住友フィナンシャルグループ", "金融", 5.0),
    ("5020", "ENEOSホールディングス", "エネルギー", 5.0),
    ("8053", "住友商事",           "商社",       5.0),
    ("2914", "JT",                "食品・たばこ", 5.0),
    ("4502", "武田薬品工業",        "医薬品",     5.0),
]

def cmd_init(args) -> None:
    """初期データを一括登録する（初回セットアップ用）"""
    print("初期銘柄を登録します...\n")
    conn = init_db()
    registered = 0
    skipped = 0

    for code, default_name, sector, threshold in INITIAL_STOCKS:
        existing = conn.execute("SELECT id FROM watchlist WHERE code = ?", (code,)).fetchone()
        if existing:
            print(f"  スキップ: {default_name} ({code}) ← すでに登録済み")
            skipped += 1
            continue

        print(f"  取得中: {default_name} ({code}.T) ...", end=" ", flush=True)
        price, fetched_name = fetch_price(code)

        if price is None:
            print("取得失敗 → スキップ")
            skipped += 1
            continue

        name = fetched_name or default_name
        conn.execute(
            """INSERT INTO watchlist (code, name, sector, base_price, alert_threshold, memo, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, name, sector, price, threshold, "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        print(f"{price:,.0f}円 ✓")
        registered += 1

    conn.close()
    print(f"\n登録完了: {registered} 銘柄 / スキップ: {skipped} 銘柄")


# ──────────────────────────────────────────
# CLI エントリポイント
# ──────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock_watch.py",
        description="日本の高配当株 ウォッチリスト・アラートツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
コマンド例:
  python stock_watch.py init                        # 初期銘柄を一括登録
  python stock_watch.py add 7203 --threshold 5.0   # トヨタを追加
  python stock_watch.py list                        # 一覧表示
  python stock_watch.py check                       # 株価チェック＋アラート
  python stock_watch.py delete 7203                 # 削除
  python stock_watch.py update 7203 --threshold 8.0 # 閾値変更
  python stock_watch.py update 7203 --reset-base    # 基準株価をリセット

cron設定例（毎営業日 9:30 に自動チェック）:
  30 9 * * 1-5 cd /path/to/stock-watch && python3 stock_watch.py check
        """,
    )
    sub = parser.add_subparsers(dest="command", metavar="<コマンド>")
    sub.required = True

    # add
    p_add = sub.add_parser("add", help="銘柄をウォッチリストに追加")
    p_add.add_argument("code", help="証券コード（例: 7203）")
    p_add.add_argument("--name",      default="", help="銘柄名（省略時は自動取得）")
    p_add.add_argument("--sector",    default="", help="業種")
    p_add.add_argument("--threshold", type=float, default=5.0, metavar="PERCENT",
                       help="アラート発動の下落率%（デフォルト: 5.0）")
    p_add.add_argument("--memo",      default="", help="メモ")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="ウォッチリストを一覧表示")
    p_list.set_defaults(func=cmd_list)

    # check
    p_check = sub.add_parser("check", help="現在株価をチェックしてアラート判定")
    p_check.set_defaults(func=cmd_check)

    # delete
    p_del = sub.add_parser("delete", help="銘柄をウォッチリストから削除")
    p_del.add_argument("code", help="証券コード（例: 7203）")
    p_del.set_defaults(func=cmd_delete)

    # update
    p_upd = sub.add_parser("update", help="登録済み銘柄の設定を変更")
    p_upd.add_argument("code", help="証券コード（例: 7203）")
    p_upd.add_argument("--threshold",  type=float, default=None, metavar="PERCENT",
                       help="アラート閾値を変更（%）")
    p_upd.add_argument("--memo",       default=None, help="メモを変更")
    p_upd.add_argument("--reset-base", action="store_true", dest="reset_base",
                       help="基準株価を現在株価にリセット")
    p_upd.set_defaults(func=cmd_update)

    # init（初期データ一括登録）
    p_init = sub.add_parser("init", help="高配当株サンプル銘柄を一括登録")
    p_init.set_defaults(func=cmd_init)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
