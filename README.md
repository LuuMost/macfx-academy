# 📈 Mac FX Academy — Website & Web App

A complete membership web app for Mac FX Academy: landing page, member
registration & login, **R500/month subscription**, a members-only signals
feed, and a **trading bot store**.

## ▶️ Run it (2 minutes)

```bash
cd macfx-site
pip install -r requirements.txt
python3 app.py
```

Open **http://localhost:5000** in your browser.

Then try the full member journey:
1. **Join now** → create an account
2. Checkout is in **🧪 DEMO MODE** — click *Pay R500 (demo)* (no real money)
3. Your dashboard shows **Membership: ACTIVE** → open the Signals feed
4. Visit **Trading Bots** → *Buy now* → demo-pay → bot appears in your dashboard

## 🛠 Admin HQ — you control everything

**The first account ever registered automatically becomes the site admin.**
So: register your own account first, before telling anyone else!

Admins see a **🛠 Admin** link in the menu (`/admin`), with 4 tabs:

| Tab | What you control |
|---|---|
| 📊 **Overview** | Members count, active subs, **monthly recurring revenue**, bots sold, total bot revenue, newest members & latest payments |
| 👥 **Members** | Every login registered. Actions: **activate/pause a subscription manually** (perfect for EFT/cash payments via WhatsApp), make/remove admin, delete a member |
| 📡 **Post Signals** | Post BUY/SELL signals (pair, entry, SL, TP, reasoning) — they appear instantly in the members-only feed |
| 🤖 **Bot Store** | Add new bots (name, price in R, features) or remove them — the public store updates immediately |

To make someone else an admin later: Members tab → **⬆ Make admin**.

## 💳 Taking REAL payments (Paystack)

Payments in South Africa run through [Paystack](https://paystack.com/za)
(ZAR, cards/EFT, recurring subscriptions).

1. Create a free Paystack account → complete business verification
2. Get your **API keys** (Dashboard → Settings → API Keys & Webhooks)
3. Create a **Plan** (Dashboard → Plans) of R500/month → copy its **plan code**
4. Set the environment variables before starting the app:

```bash
export PAYSTACK_PUBLIC_KEY="pk_live_..."
export PAYSTACK_SECRET_KEY="sk_live_..."
export PAYSTACK_PLAN_CODE="PLN_..."
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
python3 app.py
```

When `PAYSTACK_PUBLIC_KEY` is present, checkout automatically switches from
demo mode to the real Paystack popup. Renewals & confirmations arrive via
webhook — in your Paystack dashboard set the webhook URL to:

```
https://YOUR-DOMAIN/paystack/webhook
```

> ⚠️ Never paste secret keys in code or screenshots — environment variables only.

## 🌐 Going live on the internet

This app needs a Python host (not plain static hosting). Free/cheap options:

| Host | Notes |
|---|---|
| **Render** | Free tier, easiest — connect a GitHub repo, start command `python3 app.py` |
| **Railway** | Free trial, very simple Python deploys |
| **A small VPS** (Hetzner ~R90/mo) | Full control; behind HTTPS via Caddy/Nginx |

Requirements for real payments: **HTTPS domain** (hosts above give a free
`*.onrender.com`-style subdomain to start; a custom domain like
`macfxacademy.co.za` is ~R100/yr). Set the same env vars in the host's
settings panel.

## 📁 Project structure

```
app.py              → the whole backend (routes, auth, payments, database)
templates/          → pages (landing, login, register, dashboard, signals, store, checkout)
static/css/site.css → the dark & gold theme
static/js/main.js   → menu + animations
macfx.db            → SQLite database (auto-created; users, subs, purchases)
```

## 🗂 Editing content

| What | Where |
|---|---|
| Bots (name, price, features) | `PRODUCTS` list in `app.py` |
| Sample signals | `SIGNALS` list in `app.py` |
| Subscription price | `PLAN_AMOUNT` in `app.py` (cents) |
| Land your real `.ex5` bot files | deliver via email after purchase, or ask me to add file downloads |

## 🔒 Production to-do list (before real customers)

- [ ] Set a strong `SECRET_KEY` env var (sessions are signed with it)
- [ ] Deploy with HTTPS (required by Paystack live + browsers)
- [ ] Email verification & "forgot password" flow (I can add)
- [ ] Admin page to post signals without touching code (I can add)
- [ ] Switch SQLite → Postgres when traffic grows
- [ ] Legal: privacy policy (PoPIA — you store personal details), terms of
      service, and confirm your FSCA/compliance position for signals & bots
     (educational disclaimers are already in the footer)

---

Built with Flask + SQLite + Paystack. *Trade smart. Build freedom.* 📈
