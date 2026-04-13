"""
高配当株ウォッチリスト Webアプリ
起動: python3 app.py
"""

import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

try:
    import yfinance as yf
except ImportError:
    print("エラー: pip3 install yfinance")
    sys.exit(1)

app = Flask(__name__)
DB_PATH = Path(__file__).parent / "watchlist.db"

# ── 銘柄マスター（名前・業種・タイプ・年間配当） ─────────────────────
STOCK_MASTER = {
    "1605": {"name": "INPEX",                          "sector": "エネルギー",   "type": "cyclical",  "dividend": 56.0},
    "1925": {"name": "大和ハウス工業",                  "sector": "建設",         "type": "cyclical",  "dividend": 130.0},
    "2502": {"name": "アサヒグループホールディングス",   "sector": "食品・飲料",   "type": "defensive", "dividend": 60.0},
    "2503": {"name": "キリンホールディングス",           "sector": "食品・飲料",   "type": "defensive", "dividend": 67.0},
    "2914": {"name": "日本たばこ産業（JT）",             "sector": "食品・たばこ", "type": "defensive", "dividend": 188.0},
    "4063": {"name": "信越化学工業",                    "sector": "化学",         "type": "cyclical",  "dividend": 50.0},
    "4452": {"name": "花王",                            "sector": "生活用品",     "type": "defensive", "dividend": 150.0},
    "4502": {"name": "武田薬品工業",                    "sector": "医薬品",       "type": "defensive", "dividend": 188.0},
    "4503": {"name": "アステラス製薬",                  "sector": "医薬品",       "type": "defensive", "dividend": 60.0},
    "5019": {"name": "出光興産",                        "sector": "エネルギー",   "type": "cyclical",  "dividend": 120.0},
    "5020": {"name": "ENEOSホールディングス",            "sector": "エネルギー",   "type": "cyclical",  "dividend": 22.0},
    "5108": {"name": "ブリヂストン",                    "sector": "自動車部品",   "type": "cyclical",  "dividend": 220.0},
    "6301": {"name": "小松製作所（コマツ）",             "sector": "機械",         "type": "cyclical",  "dividend": 80.0},
    "6501": {"name": "日立製作所",                      "sector": "電気機器",     "type": "cyclical",  "dividend": 60.0},
    "6503": {"name": "三菱電機",                        "sector": "電気機器",     "type": "cyclical",  "dividend": 40.0},
    "6758": {"name": "ソニーグループ",                  "sector": "電気機器",     "type": "cyclical",  "dividend": 85.0},
    "6902": {"name": "デンソー",                        "sector": "自動車部品",   "type": "cyclical",  "dividend": 60.0},
    "7203": {"name": "トヨタ自動車",                    "sector": "自動車",       "type": "cyclical",  "dividend": 60.0},
    "7267": {"name": "本田技研工業（ホンダ）",           "sector": "自動車",       "type": "cyclical",  "dividend": 68.0},
    "7751": {"name": "キヤノン",                        "sector": "精密機器",     "type": "cyclical",  "dividend": 100.0},
    "8001": {"name": "伊藤忠商事",                      "sector": "商社",         "type": "cyclical",  "dividend": 110.0},
    "8002": {"name": "丸紅",                            "sector": "商社",         "type": "cyclical",  "dividend": 78.0},
    "8015": {"name": "豊田通商",                        "sector": "商社",         "type": "cyclical",  "dividend": 110.0},
    "8031": {"name": "三井物産",                        "sector": "商社",         "type": "cyclical",  "dividend": 115.0},
    "8053": {"name": "住友商事",                        "sector": "商社",         "type": "cyclical",  "dividend": 105.0},
    "8058": {"name": "三菱商事",                        "sector": "商社",         "type": "cyclical",  "dividend": 100.0},
    "8306": {"name": "三菱UFJフィナンシャルグループ",    "sector": "金融",         "type": "cyclical",  "dividend": 41.0},
    "8316": {"name": "三井住友フィナンシャルグループ",   "sector": "金融",         "type": "cyclical",  "dividend": 330.0},
    "8411": {"name": "みずほフィナンシャルグループ",     "sector": "金融",         "type": "cyclical",  "dividend": 115.0},
    "8591": {"name": "オリックス",                      "sector": "金融",         "type": "cyclical",  "dividend": 94.0},
    "8802": {"name": "三菱地所",                        "sector": "不動産",       "type": "cyclical",  "dividend": 34.0},
    "9020": {"name": "東日本旅客鉄道（JR東日本）",       "sector": "運輸",         "type": "defensive", "dividend": 40.0},
    "9432": {"name": "NTT（日本電信電話）",              "sector": "通信",         "type": "defensive", "dividend": 5.1},
    "9433": {"name": "KDDI",                            "sector": "通信",         "type": "defensive", "dividend": 145.0},
    "9501": {"name": "東京電力ホールディングス",          "sector": "電力",         "type": "defensive", "dividend": 0.0},
    "9503": {"name": "関西電力",                        "sector": "電力",         "type": "defensive", "dividend": 60.0},
    "9531": {"name": "東京ガス",                        "sector": "ガス",         "type": "defensive", "dividend": 70.0},
    "9984": {"name": "ソフトバンクグループ",             "sector": "通信",         "type": "cyclical",  "dividend": 88.0},
}

SECTOR_JP = {
    "Basic Materials": "素材", "Communication Services": "通信",
    "Consumer Cyclical": "一般消費財", "Consumer Defensive": "生活必需品",
    "Energy": "エネルギー", "Financial Services": "金融",
    "Healthcare": "ヘルスケア", "Industrials": "産業・機械",
    "Real Estate": "不動産", "Technology": "テクノロジー", "Utilities": "公益事業",
}
SECTOR_TYPE = {
    "Communication Services": "defensive", "Consumer Defensive": "defensive",
    "Healthcare": "defensive", "Utilities": "defensive",
    "Basic Materials": "cyclical", "Consumer Cyclical": "cyclical",
    "Energy": "cyclical", "Financial Services": "cyclical",
    "Industrials": "cyclical", "Real Estate": "cyclical", "Technology": "cyclical",
}

def get_master(code: str) -> dict:
    return STOCK_MASTER.get(code.zfill(4), {})


# ── DB ──────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            code               TEXT    NOT NULL UNIQUE,
            name               TEXT    NOT NULL,
            sector             TEXT    DEFAULT '',
            stock_type         TEXT    DEFAULT 'unknown',
            base_price         REAL    NOT NULL,
            dividend_per_share REAL    DEFAULT 0,
            alert_threshold    REAL    NOT NULL DEFAULT 5.0,
            memo               TEXT    DEFAULT '',
            created_at         TEXT    NOT NULL
        )
    """)

    # マイグレーション：既存DBに新カラムを追加
    for col, definition in [
        ("stock_type",         "TEXT DEFAULT 'unknown'"),
        ("dividend_per_share", "REAL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE watchlist ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError:
            pass  # すでに存在

    conn.commit()
    return conn


# ── 株価取得 ─────────────────────────────────────────────────────────

def fetch_jp_name(code: str) -> str:
    """Yahoo Finance Japan API から日本語銘柄名を取得"""
    try:
        import requests as req
        r = req.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": f"{code}.T", "lang": "ja-JP", "region": "JP",
                    "quotesCount": 1, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        quotes = r.json().get("quotes", [])
        if quotes:
            return quotes[0].get("longname") or quotes[0].get("shortname") or ""
    except Exception:
        pass
    return ""


def fetch_prices_batch(codes: list) -> dict:
    """複数コードを一括取得。{code: price} を返す。"""
    if not codes:
        return {}
    tickers = " ".join(f"{c}.T" for c in codes)
    try:
        data = yf.download(tickers, period="2d", progress=False, auto_adjust=True)
        closes = data["Close"]
        # 最新の終値を取得
        latest = closes.ffill().iloc[-1]
        result = {}
        for c in codes:
            key = f"{c}.T"
            try:
                v = float(latest[key])
                result[c] = v if v > 0 else None
            except Exception:
                result[c] = None
        return result
    except Exception:
        return {c: None for c in codes}


def fetch_price(code: str):
    """単体取得（add時の検証用）。(price, name, currency) を返す。"""
    try:
        ticker = yf.Ticker(f"{code}.T")
        fast  = ticker.fast_info
        price = fast.last_price
        info  = ticker.info
        name  = info.get("longName") or info.get("shortName") or ""
        return (float(price) if price else None), name, "JPY"
    except Exception:
        return None, None, None


# ── 利回りティア ─────────────────────────────────────────────────────

def yield_tier(y):
    if y is None: return "none"
    if y >= 5.0:  return "gold"
    if y >= 4.5:  return "green"
    if y >= 4.0:  return "blue"
    return "gray"


# ── エンリッチ ────────────────────────────────────────────────────────

def build_stock_dict(row, price):
    """DB行 + 取得済み価格 → dict（APIレスポンス用）"""

    div = float(row["dividend_per_share"] or 0)
    if price and price > 0 and div > 0:
        div_yield = div / price * 100
    else:
        div_yield = None

    if price and price > 0:
        change_pct = (price - row["base_price"]) / row["base_price"] * 100
        if change_pct < 0:
            status = "down"
        elif change_pct > 0:
            status = "up"
        else:
            status = "flat"
    else:
        change_pct = None
        status = "unknown"

    return {
        "id":                  row["id"],
        "code":                row["code"],
        "name":                row["name"],
        "sector":              row["sector"] or "",
        "stock_type":          row["stock_type"] or "unknown",
        "base_price":          row["base_price"],
        "dividend_per_share":  div,
        "alert_threshold":     row["alert_threshold"],
        "memo":                row["memo"] or "",
        "created_at":          row["created_at"],
        "current_price":       round(price, 1) if price else None,
        "change_pct":          round(change_pct, 2) if change_pct is not None else None,
        "status":              status,
        "dividend_yield":      round(div_yield, 2) if div_yield is not None else None,
        "yield_tier":          yield_tier(div_yield),
        "updated_at":          datetime.now().strftime("%H:%M:%S"),
    }


# ── API ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/lookup/<code>")
def api_lookup(code):
    """証券コードから銘柄情報を自動補完"""
    code = code.strip().zfill(4)
    master = get_master(code)

    if master:
        return jsonify({
            "found":    True,
            "name":     master["name"],
            "sector":   master["sector"],
            "type":     master["type"],
            "dividend": master["dividend"],
            "source":   "master",
        })

    # マスターにない場合：日本語名 + yfinance で補完
    try:
        ticker    = yf.Ticker(f"{code}.T")
        info      = ticker.info
        price     = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return jsonify({"found": False, "error": "銘柄が見つかりませんでした"})

        en_sector = info.get("sector", "")
        dividend  = float(info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0)

        # 日本語名を取得（Yahoo Finance Japan API 優先）
        jp_name = fetch_jp_name(code)
        name    = jp_name or info.get("longName") or info.get("shortName") or code

        return jsonify({
            "found":    True,
            "name":     name,
            "sector":   SECTOR_JP.get(en_sector, en_sector),
            "type":     SECTOR_TYPE.get(en_sector, "unknown"),
            "dividend": round(dividend, 1),
            "source":   "yfinance",
        })
    except Exception:
        return jsonify({"found": False, "error": "取得に失敗しました"})


@app.route("/api/stocks")
def api_stocks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM watchlist ORDER BY created_at").fetchall()
    conn.close()

    if not rows:
        return jsonify([])

    # 全銘柄を一括バッチ取得（高速）
    codes  = [r["code"] for r in rows]
    prices = fetch_prices_batch(codes)

    results = []
    for row in rows:
        price = prices.get(row["code"])
        results.append(build_stock_dict(row, price))

    return jsonify(results)


@app.route("/api/stocks/<code>")
def api_stock_single(code):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM watchlist WHERE code = ?", (code.upper(),)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    prices = fetch_prices_batch([code.upper()])
    price  = prices.get(code.upper())
    return jsonify(build_stock_dict(row, price))


@app.route("/api/stocks", methods=["POST"])
def api_add():
    data = request.json or {}
    raw  = data.get("code", "").strip()
    code = raw.zfill(4) if raw.isdigit() else raw.upper()

    if not code:
        return jsonify({"error": "証券コードを入力してください"}), 400

    conn = get_conn()
    if conn.execute("SELECT id FROM watchlist WHERE code = ?", (code,)).fetchone():
        conn.close()
        return jsonify({"error": f"{code} はすでに登録されています"}), 400

    price, en_name, _ = fetch_price(code)
    if price is None:
        conn.close()
        return jsonify({"error": f"証券コード {code} の株価を取得できませんでした"}), 400

    master = get_master(code)
    jp_name = fetch_jp_name(code) if not master else ""
    display_name = (data.get("name") or "").strip() or master.get("name") or jp_name or en_name or code

    conn.execute(
        """INSERT INTO watchlist
           (code, name, sector, stock_type, base_price, dividend_per_share, alert_threshold, memo, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            code,
            display_name,
            data.get("sector", "").strip(),
            data.get("stock_type", "unknown"),
            price,
            float(data.get("dividend_per_share") or 0),
            float(data.get("alert_threshold", 5.0)),
            data.get("memo", "").strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "code": code, "name": display_name, "base_price": price}), 201


@app.route("/api/stocks/<code>", methods=["PUT"])
def api_update(code):
    data = request.json or {}
    conn = get_conn()
    row  = conn.execute("SELECT * FROM watchlist WHERE code = ?", (code.upper(),)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    updates, params = [], []

    if "alert_threshold" in data:
        updates.append("alert_threshold = ?"); params.append(float(data["alert_threshold"]))
    if "dividend_per_share" in data:
        updates.append("dividend_per_share = ?"); params.append(float(data["dividend_per_share"] or 0))
    if "stock_type" in data:
        updates.append("stock_type = ?"); params.append(data["stock_type"])
    if "memo" in data:
        updates.append("memo = ?"); params.append(data["memo"])
    if "name" in data and data["name"].strip():
        updates.append("name = ?"); params.append(data["name"].strip())
    if data.get("reset_base"):
        p, _, _ = fetch_price(code.upper())
        if p:
            updates.append("base_price = ?"); params.append(p)

    if updates:
        params.append(code.upper())
        conn.execute(f"UPDATE watchlist SET {', '.join(updates)} WHERE code = ?", params)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/stocks/<code>", methods=["DELETE"])
def api_delete(code):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE code = ?", (code.upper(),))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/notify", methods=["POST"])
def api_notify():
    data   = request.json or {}
    title  = data.get("title", "株価アラート")
    body   = data.get("body", "")
    script = f'display notification "{body}" with title "{title}" sound name "Basso"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception:
        pass
    return jsonify({"ok": True})


# ── 初期データ ────────────────────────────────────────────────────────

INITIAL_STOCKS = [
    # (code, name, sector, stock_type, dividend_per_share, threshold)
    ("8058", "三菱商事",                     "商社",         "cyclical",  100.0, 5.0),
    ("8031", "三井物産",                     "商社",         "cyclical",  115.0, 5.0),
    ("9432", "NTT（日本電信電話）",           "通信",         "defensive",   5.1, 5.0),
    ("8316", "三井住友フィナンシャルグループ", "金融",         "cyclical",  330.0, 5.0),
    ("5020", "ENEOSホールディングス",         "エネルギー",   "cyclical",   22.0, 5.0),
    ("8053", "住友商事",                     "商社",         "cyclical",  105.0, 5.0),
    ("2914", "日本たばこ産業（JT）",          "食品・たばこ", "defensive", 188.0, 5.0),
    ("4502", "武田薬品工業",                 "医薬品",       "defensive", 188.0, 5.0),
]


@app.route("/api/init", methods=["POST"])
def api_init():
    conn = get_conn()
    registered, skipped = 0, 0
    results = []

    for code, name, sector, stype, div, threshold in INITIAL_STOCKS:
        if conn.execute("SELECT id FROM watchlist WHERE code = ?", (code,)).fetchone():
            skipped += 1
            results.append({"code": code, "status": "skipped"})
            continue

        price, _, _ = fetch_price(code)
        if price is None:
            results.append({"code": code, "status": "failed"})
            continue

        conn.execute(
            """INSERT INTO watchlist
               (code,name,sector,stock_type,base_price,dividend_per_share,alert_threshold,memo,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (code, name, sector, stype, price, div, threshold, "",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        registered += 1
        results.append({"code": code, "name": name, "status": "ok", "price": price})

    conn.close()
    return jsonify({"registered": registered, "skipped": skipped, "results": results})


def migrate_names():
    """起動時にDBの銘柄名を日本語に更新（STOCK_MASTER優先、なければYahoo Finance Japan）"""
    conn = get_conn()
    rows = conn.execute("SELECT code, name FROM watchlist").fetchall()
    updated = 0
    for row in rows:
        master = get_master(row["code"])
        if master:
            new_name = master["name"]
            if new_name and new_name != row["name"]:
                conn.execute("UPDATE watchlist SET name=?, sector=?, stock_type=? WHERE code=?",
                             (master["name"], master["sector"], master["type"], row["code"]))
                updated += 1
        else:
            # マスターにない銘柄は Yahoo Finance Japan から日本語名を取得
            jp = fetch_jp_name(row["code"])
            if jp and jp != row["name"]:
                conn.execute("UPDATE watchlist SET name=? WHERE code=?", (jp, row["code"]))
                updated += 1
    if updated:
        conn.commit()
        print(f"  銘柄名を日本語に更新: {updated}件")
    conn.close()


import os

migrate_names()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    print("=" * 50)
    print(f"  高配当株ウォッチリスト 起動中...")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, port=port, host="0.0.0.0", threaded=True)
