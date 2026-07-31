#!/usr/bin/env python3
"""
Mac FX Academy — Web Application
================================
Membership site with:
  • Register / Login (secure password hashing)
  • Monthly subscription (R500/month Signals + Mentorship)
  • Trading bot store (one-time purchases, delivered in dashboard)

Payment modes
-------------
DEMO MODE (default): no real money moves. A simulated checkout activates
the subscription / records purchases — perfect for development & demos.

LIVE MODE: set these environment variables and the checkout switches to a
real Paystack popup (ZAR) + webhook verification:
  PAYSTACK_PUBLIC_KEY   e.g. pk_live_...
  PAYSTACK_SECRET_KEY   e.g. sk_live_...
  PAYSTACK_PLAN_CODE    the R500/month plan code from your Paystack dashboard

Run:  python3 app.py   →   http://localhost:5000
"""

import hmac
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from urllib import request as urllib_request

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "macfx.db")

PLAN_NAME = "Signals + Mentorship"
PLAN_AMOUNT = 500_00          # cents (R500.00)
CURRENCY = "ZAR"

PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PLAN_CODE = os.environ.get("PAYSTACK_PLAN_CODE", "")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-" + secrets.token_hex(16))   # set SECRET_KEY in production!

# ---------------------------------------------------------------- database --

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    pw_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL,
    amount INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    next_billing_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    blurb TEXT NOT NULL,
    price INTEGER NOT NULL,
    features TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    amount INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, product_id)
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry TEXT NOT NULL,
    sl TEXT NOT NULL,
    tp TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

PRODUCTS = [
    ("gold-rush-ea", "MAC FX Gold Rush EA",
     "Our flagship XAUUSD scalper. Trades the London & New York sessions with "
     "tight risk control and a built-in equity protector.",
     1500_00, "XAUUSD scalping strategy|Prop-firm friendly settings|Equity protector built in|MT5 .ex5 file + setup guide"),
    ("trend-rider-ea", "MAC FX Trend Rider EA",
     "A swing/trend robot for the major pairs. Rides momentum with ATR-based "
     "stops and trailing take-profits. Set it and let it work.",
     950_00, "EURUSD · GBPUSD · USDJPY|ATR risk management|Trailing take-profit|MT5 .ex5 file + setup guide"),
    ("news-shield", "MAC FX News Shield",
     "A utility robot that guards your account — pauses trading around "
     "high-impact news and locks in daily-loss limits for any strategy.",
     650_00, "Blocks trading on red-folder news|Daily loss limit lockout|Works with any EA or manual trades|MT5 .ex5 file + setup guide"),
]

SIGNALS = [
    ("XAUUSD", "BUY", "2 341.50", "2 330.00", "2 365.00",
     "Pullback into H4 demand after NY open rejection wick. Risk 1%."),
    ("EURUSD", "SELL", "1.08650", "1.09000", "1.07950",
     "Liquidity sweep above Asian highs + bearish divergence on the 1H."),
    ("GBPUSD", "BUY", "1.27200", "1.26750", "1.28100",
     "Break & retest of the weekly level. Enter on 15m confirmation."),
]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    # Safe migration for older databases: add is_admin column if missing
    try:
        db.execute("SELECT is_admin FROM users LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO products (slug,name,blurb,price,features) VALUES (?,?,?,?,?)",
            PRODUCTS)
    if db.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        db.executemany(
            "INSERT INTO signals (pair,direction,entry,sl,tp,note,created_at) VALUES (?,?,?,?,?,?,?)",
            [s + (now,) for s in SIGNALS])
    db.commit()
    db.close()

# ------------------------------------------------------------------ helpers --

def now_iso():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")

@app.template_filter("rand")
def rand(cents):
    """Format cents as a South African Rand amount: 150000 -> 'R1 500'"""
    rands = cents / 100
    return "R{:,.0f}".format(rands).replace(",", " ") if rands == int(rands) else "R{:,.2f}".format(rands).replace(",", " ")

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        if not g.user["is_admin"]:
            flash("That area is for the site owner only.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped

def get_active_sub(user_id):
    return get_db().execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='active' "
        "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()

@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

# ------------------------------------------------------------------- pages ---

@app.route("/")
def index():
    return render_template("index.html")

# -------------------------------------------------------------------- auth ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        pw2 = request.form.get("confirm", "")
        db = get_db()
        if not name or not email or not pw:
            flash("Please fill in every field.", "error")
        elif len(pw) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif pw != pw2:
            flash("Passwords do not match.", "error")
        elif db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("An account with that email already exists — try logging in.", "error")
        else:
            # The FIRST account ever created automatically becomes the site admin
            is_first = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            cur = db.execute(
                "INSERT INTO users (name,email,pw_hash,is_admin,created_at) VALUES (?,?,?,?,?)",
                (name, email, generate_password_hash(pw), 1 if is_first else 0, now_iso()))
            db.commit()
            session["uid"] = cur.lastrowid
            if is_first:
                flash(f"Welcome, {name.split()[0]}! You're the first member — so you're now the site ADMIN 🛠 (see /admin).", "success")
                return redirect(url_for("admin"))
            flash(f"Welcome to Mac FX Academy, {name.split()[0]}! Activate your membership below.", "success")
            return redirect(url_for("checkout", kind="subscription"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["pw_hash"], pw):
            session["uid"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}.", "success")
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt if nxt.startswith("/") else url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out. Trade smart!", "info")
    return redirect(url_for("index"))

# -------------------------------------------------------------- members area -

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    sub = get_active_sub(g.user["id"])
    owned = db.execute(
        "SELECT p.*, pu.created_at FROM purchases pu JOIN products p ON p.id=pu.product_id "
        "WHERE pu.user_id=? ORDER BY pu.id DESC", (g.user["id"],)).fetchall()
    bots = db.execute("SELECT * FROM products ORDER BY price").fetchall()
    return render_template("dashboard.html", sub=sub, owned=owned, bots=bots)

@app.route("/signals")
@login_required
def signals():
    sub = get_active_sub(g.user["id"])
    if not sub:
        flash("The signals feed is for active members — activate your subscription to unlock it.", "info")
        return redirect(url_for("checkout", kind="subscription"))
    rows = get_db().execute("SELECT * FROM signals ORDER BY id DESC").fetchall()
    return render_template("signals.html", rows=rows)

# ------------------------------------------------------------------- store ---

@app.route("/store")
def store():
    products = get_db().execute("SELECT * FROM products ORDER BY price DESC").fetchall()
    owned_ids = set()
    if g.user:
        owned_ids = {r["product_id"] for r in get_db().execute(
            "SELECT product_id FROM purchases WHERE user_id=?", (g.user["id"],))}
    return render_template("store.html", products=products, owned_ids=owned_ids)

# --------------------------------------------------------------- checkout ----

@app.route("/checkout/<kind>")
@login_required
def checkout(kind):
    """kind = 'subscription'  |  'product-<id>'"""
    item = {"kind": "subscription", "name": PLAN_NAME + " — monthly", "amount": PLAN_AMOUNT}
    product = None
    if kind.startswith("product-"):
        pid = int(kind.split("-", 1)[1])
        product = get_db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if not product:
            abort(404)
        already = get_db().execute(
            "SELECT 1 FROM purchases WHERE user_id=? AND product_id=?",
            (g.user["id"], pid)).fetchone()
        if already:
            flash("You already own that bot — it's waiting in your dashboard.", "info")
            return redirect(url_for("dashboard"))
        item = {"kind": kind, "name": product["name"] + " (once-off)", "amount": product["price"]}
    elif kind != "subscription":
        abort(404)
    return render_template(
        "checkout.html", item=item, product=product,
        paystack_key=PAYSTACK_PUBLIC_KEY, plan_code=PAYSTACK_PLAN_CODE)

def fulfill(user_id, kind):
    """Record a successful payment: activate sub OR record bot purchase."""
    db = get_db()
    if kind == "subscription":
        existing = get_active_sub(user_id)
        if not existing:
            db.execute(
                "INSERT INTO subscriptions (user_id,status,plan,amount,started_at,next_billing_at) "
                "VALUES (?,?,?,?,?,?)",
                (user_id, "active", PLAN_NAME, PLAN_AMOUNT, now_iso(),
                 (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")))
            db.commit()
        return "Membership activated — welcome to the Academy! 📈"
    pid = int(kind.split("-", 1)[1])
    product = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if product:
        try:
            db.execute(
                "INSERT INTO purchases (user_id,product_id,amount,created_at) VALUES (?,?,?,?)",
                (user_id, pid, product["price"], now_iso()))
            db.commit()
        except sqlite3.IntegrityError:
            pass
        return f"{product['name']} purchased — it's now in your dashboard. 🤖"
    return "Payment recorded."

@app.route("/pay/demo", methods=["POST"])
@login_required
def pay_demo():
    """DEMO payment — no real money. Disabled automatically when
    PAYSTACK_SECRET_KEY is set (live mode uses /payment/return + webhook)."""
    if PAYSTACK_SECRET_KEY:
        abort(403)
    kind = request.form.get("kind", "")
    if kind != "subscription" and not kind.startswith("product-"):
        abort(400)
    flash(fulfill(g.user["id"], kind) + "  (demo payment)", "success")
    return redirect(url_for("dashboard"))

# ---------------------------------------------------------- ADMIN (owner) ----

@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    stats = {
        "members": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "active_subs": db.execute("SELECT COUNT(*) c FROM subscriptions WHERE status='active'").fetchone()["c"],
        "bots_sold": db.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"],
        "bot_revenue": db.execute("SELECT COALESCE(SUM(amount),0) s FROM purchases").fetchone()["s"],
        "mrr": db.execute("SELECT COALESCE(SUM(amount),0) s FROM subscriptions WHERE status='active'").fetchone()["s"],
    }
    recent_members = db.execute(
        "SELECT u.*, (SELECT status FROM subscriptions s WHERE s.user_id=u.id ORDER BY id DESC LIMIT 1) sub_status "
        "FROM users u ORDER BY u.id DESC LIMIT 8").fetchall()
    recent_payments = db.execute(
        "SELECT pu.created_at, u.name, u.email, p.name product, pu.amount "
        "FROM purchases pu JOIN users u ON u.id=pu.user_id JOIN products p ON p.id=pu.product_id "
        "ORDER BY pu.id DESC LIMIT 8").fetchall()
    return render_template("admin.html", tab="overview", stats=stats,
                           recent_members=recent_members, recent_payments=recent_payments)

@app.route("/admin/members")
@admin_required
def admin_members():
    rows = get_db().execute(
        "SELECT u.*, (SELECT status FROM subscriptions s WHERE s.user_id=u.id ORDER BY id DESC LIMIT 1) sub_status "
        "FROM users u ORDER BY u.id DESC").fetchall()
    return render_template("admin.html", tab="members", members=rows)

@app.route("/admin/member/<int:uid>/toggle-sub", methods=["POST"])
@admin_required
def admin_toggle_sub(uid):
    """Manually activate / pause a member's subscription (e.g. cash payments,
    WhatsApp EFT confirmations,comps)."""
    db = get_db()
    sub = db.execute("SELECT * FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT 1",
                     (uid,)).fetchone()
    if sub and sub["status"] == "active":
        db.execute("UPDATE subscriptions SET status='cancelled' WHERE id=?", (sub["id"],))
        msg = "Subscription paused."
    elif sub:
        db.execute("UPDATE subscriptions SET status='active', next_billing_at=? WHERE id=?",
                   ((datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M"), sub["id"]))
        msg = "Subscription re-activated (30 days)."
    else:
        db.execute("INSERT INTO subscriptions (user_id,status,plan,amount,started_at,next_billing_at) "
                   "VALUES (?,?,?,?,?,?)",
                   (uid, "active", PLAN_NAME, PLAN_AMOUNT, now_iso(),
                    (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")))
        msg = "Manual membership activated (30 days)."
    db.commit()
    flash(msg, "success")
    return redirect(url_for("admin_members"))

@app.route("/admin/member/<int:uid>/toggle-admin", methods=["POST"])
@admin_required
def admin_toggle_admin(uid):
    if uid == g.user["id"]:
        flash("You can't revoke your own admin rights.", "error")
        return redirect(url_for("admin_members"))
    db = get_db()
    u = db.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    if u:
        db.execute("UPDATE users SET is_admin=? WHERE id=?", (0 if u["is_admin"] else 1, uid))
        db.commit()
        flash("Admin rights updated.", "success")
    return redirect(url_for("admin_members"))

@app.route("/admin/member/<int:uid>/delete", methods=["POST"])
@admin_required
def admin_delete_member(uid):
    if uid == g.user["id"]:
        flash("You can't delete your own account from here.", "error")
        return redirect(url_for("admin_members"))
    db = get_db()
    db.execute("DELETE FROM subscriptions WHERE user_id=?", (uid,))
    db.execute("DELETE FROM purchases WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    flash("Member and their records deleted.", "success")
    return redirect(url_for("admin_members"))

@app.route("/admin/signals", methods=["GET", "POST"])
@admin_required
def admin_signals():
    db = get_db()
    if request.method == "POST":
        pair = request.form.get("pair", "").strip().upper()
        direction = request.form.get("direction", "").strip().upper()
        entry = request.form.get("entry", "").strip()
        sl = request.form.get("sl", "").strip()
        tp = request.form.get("tp", "").strip()
        note = request.form.get("note", "").strip()
        if pair and direction in ("BUY", "SELL") and entry and sl and tp:
            db.execute(
                "INSERT INTO signals (pair,direction,entry,sl,tp,note,created_at) VALUES (?,?,?,?,?,?,?)",
                (pair, direction, entry, sl, tp, note, now_iso()))
            db.commit()
            flash(f"Signal posted: {direction} {pair} — live in the members feed. 📡", "success")
        else:
            flash("Please complete pair, direction, entry, SL and TP.", "error")
        return redirect(url_for("admin_signals"))
    rows = db.execute("SELECT * FROM signals ORDER BY id DESC").fetchall()
    return render_template("admin.html", tab="signals", rows=rows)

@app.route("/admin/signals/<int:sid>/delete", methods=["POST"])
@admin_required
def admin_delete_signal(sid):
    db = get_db()
    db.execute("DELETE FROM signals WHERE id=?", (sid,))
    db.commit()
    flash("Signal removed.", "success")
    return redirect(url_for("admin_signals"))

@app.route("/admin/bots", methods=["GET", "POST"])
@admin_required
def admin_bots():
    db = get_db()
    if request.method == "POST":
        import re
        name = request.form.get("name", "").strip()
        blurb = request.form.get("blurb", "").strip()
        try:
            price = int(round(float(request.form.get("price", "0")) * 100))
        except ValueError:
            price = 0
        features = "|".join(line.strip() for line in
                            request.form.get("features", "").splitlines() if line.strip())
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if name and price > 0 and slug:
            try:
                db.execute("INSERT INTO products (slug,name,blurb,price,features) VALUES (?,?,?,?,?)",
                           (slug, name, blurb, price, features))
                db.commit()
                flash(f"Bot added to the store: {name} 🤖", "success")
            except sqlite3.IntegrityError:
                flash("A bot with a similar name already exists.", "error")
        else:
            flash("A bot needs a name and a price above R0.", "error")
        return redirect(url_for("admin_bots"))
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    return render_template("admin.html", tab="bots", products=products)

@app.route("/admin/bots/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_delete_bot(pid):
    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    flash("Bot removed from the store.", "success")
    return redirect(url_for("admin_bots"))

# ---------------------------------------------------------- paystack (live) --

def paystack_verify(reference):
    """Verify a transaction server-side with Paystack (live mode)."""
    req = urllib_request.Request(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"})
    with urllib_request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    return bool(data.get("status")) and data["data"]["status"] == "success"

@app.route("/payment/return")
@login_required
def payment_return():
    reference = request.args.get("reference", "")
    kind = request.args.get("kind", "")
    if not PAYSTACK_SECRET_KEY:
        flash("Live keys not configured — nothing was charged.", "error")
        return redirect(url_for("dashboard"))
    try:
        ok = paystack_verify(reference)
    except Exception:
        ok = False
    if ok:
        flash(fulfill(g.user["id"], kind), "success")
    else:
        flash("Payment could not be verified — please contact support.", "error")
    return redirect(url_for("dashboard"))

@app.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():
    """Paystack → us. Verifies the signature, then fulfills the order.
    Set this URL in your Paystack dashboard: https://YOURDOMAIN/paystack/webhook"""
    if not PAYSTACK_SECRET_KEY:
        abort(404)
    signature = request.headers.get("x-paystack-signature", "")
    computed = hmac.new(PAYSTACK_SECRET_KEY.encode(), request.data, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(signature, computed):
        abort(401)
    event = request.get_json(silent=True) or {}
    if event.get("event") == "charge.success":
        data = event.get("data", {})
        meta = data.get("metadata", {}) or {}
        email = (data.get("customer", {}) or {}).get("email", "").lower()
        user = sqlite3.connect(DB_PATH)
        user.row_factory = sqlite3.Row
        row = user.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if row and meta.get("purpose"):
            kind = "subscription" if meta["purpose"] == "subscription" else f"product-{meta.get('product_id')}"
            # reuse fulfill() with its own connection
            try:
                fulfill(row["id"], kind)
            except Exception:
                pass
        user.close()
    return "ok", 200

# -------------------------------------------------------------------- main ---

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))   # hosts like Render set PORT automatically
    print(f"\n  📈  Mac FX Academy running at  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port)
