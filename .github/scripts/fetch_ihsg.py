#!/usr/bin/env python3
"""Ambil IHSG dari Yahoo Finance, tulis ihsg.json untuk grafik di portofolio.

Dijalankan oleh .github/workflows/ihsg.yml. Hasilnya di-push ke branch
`ihsg-data`, bukan ke `main`, supaya riwayat commit portofolio tetap bersih
sementara datanya bisa diperbarui sesering yang diizinkan GitHub.

Kalau datanya tidak masuk akal, skrip sengaja gagal (exit 1) supaya angka
aneh tidak pernah sampai ke halaman.
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

SYMBOL = "%5EJKSE"  # ^JKSE = IHSG
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/" + SYMBOL
UA = "Mozilla/5.0 (compatible; andiulia-portfolio/1.0)"
WIB = timezone(timedelta(hours=7))


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def result(url):
    data = get(url)
    try:
        return data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        raise SystemExit("bentuk respons Yahoo tidak seperti yang diharapkan: " + url)


def main():
    # 1. penutupan bulanan, tiga tahun terakhir
    monthly_res = result(BASE + "?range=3y&interval=1mo")
    stamps = monthly_res.get("timestamp") or []
    closes = monthly_res["indicators"]["quote"][0].get("close") or []

    now_wib = datetime.now(WIB)
    this_month = now_wib.strftime("%Y-%m")

    monthly = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        ym = datetime.fromtimestamp(ts + 7 * 3600, timezone.utc).strftime("%Y-%m")
        # bulan berjalan belum selesai, jangan disejajarkan dengan bulan penuh
        if ym >= this_month:
            continue
        monthly.append({"ym": ym, "v": round(float(close), 2)})

    if len(monthly) < 20:
        raise SystemExit("titik bulanan terlalu sedikit (%d), data tidak dipakai" % len(monthly))

    # 2. harga terkini + penutupan sebelumnya, untuk baris utama
    day_res = result(BASE + "?range=1d&interval=1m")
    meta = day_res["meta"]
    price = meta.get("regularMarketPrice")
    prev = meta.get("previousClose") or meta.get("chartPreviousClose")
    stamp = meta.get("regularMarketTime")

    if not price or price <= 0:
        raise SystemExit("harga terakhir tidak masuk akal: %r" % (price,))

    quote = {
        "price": round(float(price), 2),
        "prevClose": round(float(prev), 2) if prev else None,
        "time": datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp else None,
    }

    out = {
        "generated": now_wib.isoformat(timespec="seconds"),
        "source": "IDX via Yahoo Finance",
        "symbol": "^JKSE",
        "quote": quote,
        "monthly": monthly,
    }

    with open("ihsg.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(
        "ok: %d bulan (%s s/d %s), harga %s, sebelumnya %s"
        % (len(monthly), monthly[0]["ym"], monthly[-1]["ym"], quote["price"], quote["prevClose"])
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - kegagalan apa pun harus terlihat di log Actions
        print("gagal: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        raise SystemExit(1)
