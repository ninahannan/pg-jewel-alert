#!/usr/bin/env python3
"""Bot harga PG Jewel & Non-PG Gold Buyback -> Telegram.

Sumber data : https://publicgold.com.my (jadual "PG Jewel" & "Non-PG Gold Buyback")
Jadual      : dijalankan pada minit ke-16, 36 & 56 setiap jam (GitHub Actions).
Logik       :
  * Jika harga berubah berbanding harga terakhir yang dihantar -> hantar poster + mesej.
  * Sekali sehari selepas 12:16 pagi (waktu Malaysia) -> hantar UPDATE HARIAN
    walaupun harga tidak berubah.

Penggunaan:
  python bot.py              # mod biasa (dipanggil oleh GitHub Actions)
  python bot.py --preview    # jana poster + mesej sahaja, TIDAK hantar ke Telegram
  python bot.py --force      # paksa hantar walaupun tiada perubahan

Pemboleh ubah persekitaran (GitHub Secrets):
  TELEGRAM_BOT_TOKEN   token bot daripada @BotFather
  TELEGRAM_CHAT_ID     cth. @nurhasninahannan (bot mesti admin channel)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFilter, ImageFont

URL = "https://publicgold.com.my/"
MYT = timezone(timedelta(hours=8))
DAILY_AFTER = (0, 16)  # 12:16 pagi waktu Malaysia
CHANNEL_LINK = "t.me/nurhasninahannan"
WHATSAPP_LINK = "https://wa.me/601133162410"

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "data" / "state.json"
OUT_DIR = BASE / "output"
FONT_DIR = BASE / "fonts"

KEYS = ["jewel_999_sell", "jewel_999_buy", "jewel_916_sell", "jewel_916_buy",
        "buyback_999", "buyback_916"]

BULAN = ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai",
         "Ogos", "September", "Oktober", "November", "Disember"]
HARI = ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"]


# --------------------------------------------------------------------------- #
# 1. Ambil harga
# --------------------------------------------------------------------------- #
def _num(text: str) -> int:
    m = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not m:
        raise ValueError(f"Tiada nombor dalam: {text!r}")
    return int(round(float(m.group(0).replace(",", ""))))


def _table_after_title(soup: BeautifulSoup, title: str):
    # Nama class/id di laman PG dirawakkan setiap kali dimuat, jadi cari ikut teks tajuk.
    for div in soup.find_all("div"):
        if div.find("div") is None and div.get_text(" ", strip=True).lower() == title.lower():
            tbl = div.find_next("table")
            if tbl is not None:
                return tbl
    raise RuntimeError(f"Jadual '{title}' tidak dijumpai di laman web")


def _rows(table) -> dict[str, list[int]]:
    out = {}
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue
        purity = re.sub(r"\D", "", cells[0])
        out[purity] = [_num(c) for c in cells[1:]]
    return out


def fetch_prices() -> dict[str, int]:
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
    r = requests.get(URL, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    jewel = _rows(_table_after_title(soup, "PG Jewel"))
    buyback = _rows(_table_after_title(soup, "Non-PG Gold Buyback"))

    prices = {
        "jewel_999_sell": jewel["999"][0],
        "jewel_999_buy": jewel["999"][1],
        "jewel_916_sell": jewel["916"][0],
        "jewel_916_buy": jewel["916"][1],
        "buyback_999": buyback["999"][0],
        "buyback_916": buyback["916"][0],
    }
    for k, v in prices.items():
        if not 50 <= v <= 5000:
            raise RuntimeError(f"Harga {k}={v} tidak munasabah, batal")
    return prices


# --------------------------------------------------------------------------- #
# 2. State
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# 3. Teks
# --------------------------------------------------------------------------- #
def tarikh_melayu(now: datetime) -> str:
    return f"{HARI[now.weekday()]}, {now.day} {BULAN[now.month - 1]} {now.year}"


def masa_melayu(now: datetime) -> str:
    h = now.hour % 12 or 12
    if now.hour < 12:
        sesi = "pagi"
    elif now.hour < 14:
        sesi = "tengah hari"
    elif now.hour < 19:
        sesi = "petang"
    else:
        sesi = "malam"
    return f"{h}:{now.minute:02d} {sesi}"


def diff_txt(new: int, old: int | None) -> str:
    if old is None or new == old:
        return ""
    d = new - old
    return f"  {'🔺' if d > 0 else '🔻'} {'+' if d > 0 else '−'}{abs(d)}"


def build_caption(p: dict, prev: dict | None, now: datetime, daily: bool) -> str:
    prev = prev or {}
    g = lambda k: diff_txt(p[k], prev.get(k))  # noqa: E731
    title = "📅 <b>UPDATE HARIAN HARGA EMAS</b>" if daily else "🔔 <b>HARGA EMAS TELAH BERUBAH!</b>"
    return (
        f"{title}\n"
        f"💍 <b>PG JEWEL &amp; NON-PG GOLD BUYBACK</b>\n"
        f"🗓 {tarikh_melayu(now)} | ⏰ {masa_melayu(now)}\n"
        f"\n"
        f"✨ <b>PG JEWEL</b> (RM / gram)\n"
        f"<b>999 (24K)</b>\n"
        f"  • PG Jual : <b>RM {p['jewel_999_sell']:,}</b>{g('jewel_999_sell')}\n"
        f"  • PG Beli : <b>RM {p['jewel_999_buy']:,}</b>{g('jewel_999_buy')}\n"
        f"<b>916 (22K)</b>\n"
        f"  • PG Jual : <b>RM {p['jewel_916_sell']:,}</b>{g('jewel_916_sell')}\n"
        f"  • PG Beli : <b>RM {p['jewel_916_buy']:,}</b>{g('jewel_916_buy')}\n"
        f"\n"
        f"♻️ <b>NON-PG GOLD BUYBACK</b> (RM / gram)\n"
        f"  • 999 : <b>RM {p['buyback_999']:,}</b>{g('buyback_999')}\n"
        f"  • 916 : <b>RM {p['buyback_916']:,}</b>{g('buyback_916')}\n"
        f"\n"
        f"<i>* PG Jual = harga anda beli daripada PG\n"
        f"* PG Beli = harga PG beli semula daripada anda</i>\n"
        f"\n"
        f"💍 <b>Koleksi PG Jewel</b> — cincin, rantai, gelang, loket &amp; subang emas 916/999 "
        f"dengan rekaan elegan dan harga telus mengikut pasaran semasa.\n"
        f"\n"
        f"♻️ <b>Tukar emas lama kepada tunai.</b> Patah, kemek atau putus — semua diterima "
        f"dan dinilai dengan telus.\n"
        f"\n"
        f"📍 Lebih <b>30 cawangan</b> di seluruh Malaysia.\n"
        f"📞 Hubungi <b>Nina Hannan</b> (Public Gold Dealer): <b>011-3316 2410</b>\n"
        f'💬 <a href="{WHATSAPP_LINK}">WhatsApp terus — klik di sini</a>'
    )


# --------------------------------------------------------------------------- #
# 4. Poster  (tema sama seperti poster Harga Emas GAP)
# --------------------------------------------------------------------------- #
W, H = 1080, 1080  # segi empat sama: tidak dipotong dalam pratonton Telegram
BG_TOP = (106, 16, 28)
BG_BOT = (44, 5, 10)
GOLD = (242, 193, 78)
GOLD_SOFT = (232, 196, 120)
CREAM = (240, 214, 196)
WHITE = (255, 255, 255)
PANEL = (42, 4, 9)
ROW_ALT = (58, 8, 15)
PINK = (240, 140, 140)
MINT = (120, 210, 160)

DEALER_NAME = "Nina Hannan"
DEALER_ID = "PG00256918"
WHATSAPP = "011-3316 2410"


def F(size: int, kind: str = "bold") -> ImageFont.FreeTypeFont:
    name = {"bold": "DejaVuSans-Bold.ttf", "reg": "DejaVuSans.ttf"}[kind]
    return ImageFont.truetype(str(FONT_DIR / name), size)


def _vgrad(w, h, top, bottom) -> Image.Image:
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g.resize((w, h))


def _center(d: ImageDraw.ImageDraw, cx, y, text, font, fill):
    d.text((cx - d.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


def _right(d: ImageDraw.ImageDraw, rx, y, text, font, fill):
    d.text((rx - d.textlength(text, font=font), y), text, font=font, fill=fill)


def _wrap(d, text, font, maxw):
    lines, cur = [], ""
    for w in text.split(" "):
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def _promo_card(d, box, border, label, title, body):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, 20, fill=PANEL, outline=border, width=3)
    d.text((x0 + 26, y0 + 22), label, font=F(20, "bold"), fill=border)
    y = y0 + 54
    for ln in _wrap(d, title, F(30, "bold"), x1 - x0 - 52):
        d.text((x0 + 26, y), ln, font=F(30, "bold"), fill=WHITE)
        y += 40
    y += 10
    for line in body:
        for ln in _wrap(d, line.replace(" ", " ") if WHATSAPP in line else line, F(21, "reg"), x1 - x0 - 52):
            d.text((x0 + 26, y), ln, font=F(21, "reg"), fill=CREAM)
            y += 30


def render_poster(p: dict, now: datetime, daily: bool, path: Path) -> Path:
    img = _vgrad(W, H, BG_TOP, BG_BOT)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GOLD)
    d.rectangle([0, H - 10, W, H], fill=GOLD)
    L, R = 48, W - 48

    # ---- Kepala ----
    d.text((L, 40), "HARGA EMAS PG JEWEL", font=F(58, "bold"), fill=GOLD)
    # Ikon pin lokasi + maklumat cawangan
    px, py = L + 9, 126
    d.ellipse([px - 9, py - 11, px + 9, py + 7], fill=GOLD)
    d.polygon([(px - 8, py), (px + 8, py), (px, py + 15)], fill=GOLD)
    d.ellipse([px - 3.5, py - 5.5, px + 3.5, py + 1.5], fill=BG_TOP)
    fs, fb = F(23, "reg"), F(23, "bold")
    x = L + 28
    for txt, f, col in [("Lebih ", fs, CREAM), ("30 cawangan", fb, GOLD),
                        (" di seluruh Malaysia  •  Emas 999 & 916", fs, CREAM)]:
        d.text((x, 112), txt, font=f, fill=col)
        x += d.textlength(txt, font=f)
    d.text((L, 160), tarikh_melayu(now), font=F(26, "bold"), fill=WHITE)
    x = L + d.textlength(tarikh_melayu(now) + "  ", font=F(26, "bold"))
    d.text((x, 164), f"•  Dikemaskini {masa_melayu(now)}", font=F(22, "reg"), fill=CREAM)
    tag = "UPDATE HARIAN" if daily else "HARGA TERKINI"
    ft = F(20, "bold")
    tw = d.textlength(tag, font=ft)
    d.rounded_rectangle([R - tw - 36, 156, R, 194], 19, outline=GOLD, width=2)
    _right(d, R - 18, 163, tag, ft, GOLD)

    # ---- Jadual harga (1 jadual) ----
    tx0, ty0, tx1, ty1 = L, 222, R, 592
    d.rounded_rectangle([tx0, ty0, tx1, ty1], 22, fill=PANEL, outline=GOLD, width=3)
    c1 = tx0 + 190
    cw = (tx1 - c1) / 3
    cols = [(tx0, c1)] + [(c1 + i * cw, c1 + (i + 1) * cw) for i in range(3)]
    head_h = 96
    d.rounded_rectangle([tx0 + 3, ty0 + 3, tx1 - 3, ty0 + head_h], 19, fill=(78, 10, 20))
    d.rectangle([tx0 + 3, ty0 + head_h - 22, tx1 - 3, ty0 + head_h], fill=(78, 10, 20))
    d.line([(tx0 + 3, ty0 + head_h), (tx1 - 3, ty0 + head_h)], fill=GOLD, width=2)
    heads = [("KETULENAN", ""), ("PG SELL", "Harga Jual"), ("PG BUY", "Harga Beli"),
             ("NON-PG BUYBACK", "Beli Emas Luar")]
    for (a, b), (h1, h2) in zip(cols, heads):
        if h2:
            _center(d, (a + b) / 2, ty0 + 20, h1, F(25 if len(h1) < 10 else 21, "bold"), GOLD)
            _center(d, (a + b) / 2, ty0 + 58, h2 + " (RM/g)", F(17, "reg"), CREAM)
        else:
            _center(d, (a + b) / 2, ty0 + 36, h1, F(21, "bold"), GOLD)
    for a, _ in cols[1:]:
        d.line([(a, ty0 + 16), (a, ty1 - 16)], fill=(120, 60, 50), width=2)

    rows = [("999", "24K", [p["jewel_999_sell"], p["jewel_999_buy"], p["buyback_999"]]),
            ("916", "22K", [p["jewel_916_sell"], p["jewel_916_buy"], p["buyback_916"]])]
    rh = (ty1 - ty0 - head_h) / 2
    for i, (pur, k, vals) in enumerate(rows):
        ry = ty0 + head_h + i * rh
        if i:
            d.line([(tx0 + 20, ry), (tx1 - 20, ry)], fill=(110, 50, 45), width=2)
        a, b = cols[0]
        _center(d, (a + b) / 2, ry + rh / 2 - 42, pur, F(58, "bold"), GOLD)
        _center(d, (a + b) / 2, ry + rh / 2 + 24, k, F(22, "reg"), CREAM)
        for (a, b), v in zip(cols[1:], vals):
            f, fr = F(60, "bold"), F(28, "bold")
            rm, num = "RM ", f"{v:,}"
            fw = d.textlength(rm, font=fr) + d.textlength(num, font=f)
            x = (a + b) / 2 - fw / 2
            d.text((x, ry + rh / 2 - 18), rm, font=fr, fill=CREAM)
            d.text((x + d.textlength(rm, font=fr), ry + rh / 2 - 40), num, font=f, fill=WHITE)

    # ---- Kad promosi ----
    mid = W / 2
    _promo_card(d, (L, 618, mid - 10, 856), MINT, "KOLEKSI PG JEWEL", "Barang Kemas Elegan, Harga Telus",
                ["Cincin, rantai, gelang, loket & subang emas 916 & 999."])
    _promo_card(d, (mid + 10, 618, R, 856), PINK, "TUKAR EMAS LAMA KEPADA TUNAI", "Patah, Kemek atau Putus",
                ["Semua diterima & dinilai dengan telus. Hubungi Nina Hannan:", WHATSAPP])

    # ---- Kaki ----
    d.line([(L, 878), (R, 878)], fill=(120, 70, 40), width=2)
    fn, fi = F(38, "bold"), F(30, "bold")
    d.text((L, 900), DEALER_NAME, font=fn, fill=GOLD)
    d.text((L + d.textlength(DEALER_NAME + " ", font=fn), 906), f"({DEALER_ID})", font=fi, fill=GOLD)
    d.text((L, 952), "Public Gold Dealer", font=F(21, "reg"), fill=CREAM)
    _right(d, R, 902, "WhatsApp", F(21, "reg"), CREAM)
    _right(d, R, 932, WHATSAPP, F(36, "bold"), WHITE)
    _center(d, W / 2, 1020, f"Dikemaskini {now:%d/%m/%Y %I:%M %p}  •  Harga rujukan dari publicgold.com.my. "
                            "Harga boleh berubah pada bila-bila masa.", F(15, "reg"), (190, 150, 140))

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return path


# --------------------------------------------------------------------------- #
# 5. Telegram
# --------------------------------------------------------------------------- #
def chat_ids() -> list[str]:
    """Semua channel sasaran: TELEGRAM_CHAT_ID + TELEGRAM_CHAT_ID_2 (boleh juga dipisah koma)."""
    ids = []
    for var in ("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID_2"):
        for c in os.environ.get(var, "").split(","):
            c = c.strip()
            if c and c not in ids:
                ids.append(c)
    if not ids:
        raise RuntimeError("Tiada channel Telegram ditetapkan")
    return ids


def send_telegram(photo: Path, caption: str) -> list[str]:
    """Hantar ke setiap channel. Pulangkan senarai channel yang gagal."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    failed = []
    for chat in chat_ids():
        with photo.open("rb") as fh:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                              data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
                              files={"photo": fh}, timeout=60)
        if r.ok:
            print(f"  Dihantar ke {chat} ✔")
        else:
            print(f"  GAGAL ke {chat}: {r.status_code} {r.text}")
            failed.append(chat)
    return failed


# --------------------------------------------------------------------------- #
# 6. Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="jana poster sahaja, jangan hantar")
    ap.add_argument("--force", action="store_true", help="paksa hantar")
    ap.add_argument("--daily", action="store_true", help="paksa format update harian")
    args = ap.parse_args()

    now = datetime.now(MYT)
    today = now.strftime("%Y-%m-%d")
    prices = fetch_prices()
    state = load_state()
    last = state.get("last_sent_prices")

    changed = last != prices
    daily_due = (state.get("last_daily_date") != today
                 and (now.hour, now.minute) >= DAILY_AFTER)
    daily = args.daily or daily_due

    print(f"[{now:%Y-%m-%d %H:%M} MYT] harga={prices}")
    print(f"  berubah={changed} harian={daily_due}")

    if not (changed or daily or args.force or args.preview):
        print("  Tiada perubahan, tiada mesej dihantar.")
        return 0

    # Update harian banding dengan harga harian semalam; update perubahan banding dengan harga terakhir
    prev = state.get("last_daily_prices") if daily else last
    caption = build_caption(prices, prev, now, daily)
    poster = render_poster(prices, now, daily, OUT_DIR / f"poster_{now:%Y%m%d_%H%M}.png")
    print(f"  Poster: {poster}")

    if args.preview:
        (OUT_DIR / "caption_preview.txt").write_text(caption)
        print("---- KAPSYEN ----\n" + caption)
        return 0

    failed = send_telegram(poster, caption)
    if len(failed) == len(chat_ids()):
        raise RuntimeError("Gagal hantar ke semua channel")

    state["last_sent_prices"] = prices
    state["last_sent_at"] = now.isoformat(timespec="minutes")
    if daily:
        state["last_daily_date"] = today
        state["last_daily_prices"] = prices
    save_state(state)
    if failed:
        print(f"  Amaran: gagal hantar ke {', '.join(failed)} (pastikan bot admin channel)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
