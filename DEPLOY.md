# 🚀 Deploy Mac FX Academy — step by step

> Everything is prepared. You only need ~15 minutes and two free accounts:
> GitHub (✅ you have: LuuMost) and Render (we'll create it).

---

## Step 1 — Put the code on GitHub (5 min)

1. Get **`macfx-academy.zip`** from the workspace and **extract** it on your laptop
2. Go to **github.com** → log in → top-right **"+" → New repository**
3. Name: **`macfx-academy`** → Public → **Create repository**
   (leave all "initialize" checkboxes **unticked**)
4. On the new repo page, click the **"uploading an existing file"** link
5. Drag **all the extracted files & folders** into that page
   (`app.py`, `requirements.txt`, `render.yaml`, `templates/`, `static/`, `README.md`, `DEPLOY.md`, `.gitignore`)
6. Click **Commit changes** ✅

## Step 2 — Deploy on Render (5 min)

1. Go to **[render.com](https://render.com)** → **Get Started** → **Sign up with GitHub**
   (authorize when asked — this lets Render read your repos)
2. In the Render dashboard: **New + → Blueprint**
3. Choose your **`macfx-academy`** repo → **Connect**
4. Render reads the `render.yaml` and fills everything in automatically:
   free web service · Python · correct build & start commands · a generated `SECRET_KEY` 🔑
5. Click **Apply / Deploy Blueprint** → wait ~2–3 minutes for the build ☕
6. When it shows **Live**, open your URL:

### ✅ https://macfx-academy.onrender.com

## Step 3 — Claim your admin crown 👑 (1 min)

**Register YOURSELF first!** The first account becomes the admin.
Register → you land on your Admin HQ → the site is officially open for business.

---

### 💳 Real payments, later
In Render: your service → **Environment → Add Environment Variable** → add
`PAYSTACK_PUBLIC_KEY`, `PAYSTACK_SECRET_KEY`, `PAYSTACK_PLAN_CODE`
(free Paystack account → paystack.com/za). Save → the app redeploys and
checkout switches from demo to real ZAR payments automatically.

### ⚠️ Know before launch (free tier)
- **Naps when idle:** first visit after ~15 min takes ±30–50s to wake. Normal, free-tier thing.
- **Free = forgetful:** member data (SQLite) resets if the service redeploys. Perfect for a
  demo/launch week — when paying members arrive, tell me and I'll move it to a
  **paid persistent disk (~R130/mo)** or Postgres in one session.

### 🌍 Custom domain (optional, ~R100/yr)
Buy `macfxacademy.co.za` → Render dashboard → your service → **Settings → Custom Domains**
→ follow the DNS steps → free HTTPS included. Tell me when you have it and I'll help.
