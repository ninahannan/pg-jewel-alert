# Bot Harga PG Jewel & Non-PG Gold Buyback → Telegram

Ambil harga **PG Jewel** (999/916, PG Jual & PG Beli) dan **Non-PG Gold Buyback**
(999/916) dari https://publicgold.com.my, jana poster, dan hantar ke channel
Telegram https://t.me/nurhasninahannan dan https://t.me/ninahannanjewelry.

## Jadual
| Bila | Tindakan |
|---|---|
| Minit ke-16, 36, 56 setiap jam | Semak harga. Hantar poster **hanya jika harga berubah** (kapsyen Telegram tunjuk beza harga 🔺/🔻). |
| Sekali sehari selepas 12:16 pagi (MYT) | Hantar **UPDATE HARIAN** walaupun harga tak berubah (banding dengan harga harian semalam). |

Harga terakhir disimpan di `data/state.json` (di-commit automatik oleh workflow).

## Setup (sekali sahaja)
1. Guna bot Telegram yang sama seperti `gap-alert`. Bot mesti **admin di kedua-dua channel** (izin *Post Messages*).
   Channel kedua (`@ninahannanjewelry`) ditetapkan terus dalam workflow (`TELEGRAM_CHAT_ID_2`).
   Token: @BotFather → `/mybots` → pilih bot → **API Token**. Jangan tekan *Revoke*.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   - `BOT_TOKEN` = token bot
   - `CHANNEL_ID` = `@nurhasninahannan` (atau nombor `-100...` seperti dalam `gap-alert`)
3. Uji: **Actions → Harga PG Jewel & Buyback → Run workflow** → mode `force`.

## Uji secara lokal
```bash
pip install -r requirements.txt
python bot.py --preview   # jana poster ke output/ + papar kapsyen, tidak hantar
```

Nota: GitHub Actions kadang-kadang lewat beberapa minit pada waktu sibuk.
