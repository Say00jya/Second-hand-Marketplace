"""
app.py - ReMarket : Second-Hand Marketplace (Flask + MySQL)

Sections in this file
    1. Configuration and helpers
    2. Public pages          (home, browse, product details)
    3. Authentication        (register, login, logout)
    4. Buyer actions         (wishlist, inquiries, reports)
    5. Seller actions        (sell, edit, delete, mark sold, my listings)
    6. Profile
    7. Admin panel           (dashboard, users, products, categories, reports, SQL demo)
    8. Error handlers and entry point
"""
import os
import re
import uuid
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlencode

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from demo_queries import DEMO_QUERIES

# ---------------------------------------------------------------------------
# 1. CONFIGURATION AND HELPERS
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploying")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024          # 3 MB upload limit
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
IMAGE_FOLDER = os.path.join(app.root_path, "static", "images")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
CONDITIONS = ["New", "Like New", "Good", "Fair"]
REPORT_REASONS = ["Spam or fake listing", "Inappropriate content", "Prohibited item",
                  "Wrong category", "Suspected scam", "Other"]
SORT_OPTIONS = {
    "newest": ("Newest first", "p.created_at DESC"),
    "oldest": ("Oldest first", "p.created_at ASC"),
    "price_low": ("Price: low to high", "p.price ASC"),
    "price_high": ("Price: high to low", "p.price DESC"),
}
PER_PAGE = 12
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
ICON_RE = re.compile(r"^bi-[a-z0-9-]{1,35}$")

# Columns and joins shared by every product-card query
CARD_COLUMNS = """p.product_id, p.title, p.price, p.item_condition, p.location, p.image,
       p.status, p.created_at, p.seller_id,
       c.name AS category_name, u.full_name AS seller_name"""
CARD_FROM = """FROM products p
INNER JOIN categories c ON c.category_id = p.category_id
INNER JOIN users u      ON u.user_id = p.seller_id"""


def indian_rupees(value):
    """Format a number the Indian way: 1234567 -> Rs 12,34,567."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "₹0"
    digits = str(abs(number))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    return ("-" if number < 0 else "") + "₹" + digits


def format_date(value, pattern="%d %b %Y"):
    return value.strftime(pattern) if value else "-"


def time_ago(value):
    """Turn a datetime into text such as '3 days ago'."""
    if not value:
        return "-"
    from datetime import datetime
    seconds = int((datetime.now() - value).total_seconds())
    if seconds < 60:
        return "just now"
    for limit, unit in ((3600, "minute"), (86400, "hour"), (2592000, "day"), (31536000, "month")):
        if seconds < limit:
            divisor = {"minute": 60, "hour": 3600, "day": 86400, "month": 2592000}[unit]
            amount = seconds // divisor
            return f"{amount} {unit}{'s' if amount != 1 else ''} ago"
    amount = seconds // 31536000
    return f"{amount} year{'s' if amount != 1 else ''} ago"


def image_url(name):
    """Placeholders live in static/images, uploaded photos in static/uploads."""
    name = name or "placeholder-other.svg"
    folder = "images" if name.startswith("placeholder") else "uploads"
    return url_for("static", filename=f"{folder}/{name}")


app.jinja_env.filters["inr"] = indian_rupees
app.jinja_env.filters["fdate"] = format_date
app.jinja_env.filters["ago"] = time_ago
app.jinja_env.filters["image_url"] = image_url


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = uuid.uuid4().hex
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["CONDITIONS"] = CONDITIONS


def escape_like(text):
    """Escape the LIKE wildcards so a user typing % or _ searches for them literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_price(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def parse_int(text, default=None):
    try:
        return int(text)
    except (TypeError, ValueError):
        return default


def safe_next_url(target):
    """Only allow redirects to paths inside this website."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def placeholder_for(category_name):
    slug = re.sub(r"[^a-z0-9]+", "-", (category_name or "other").lower()).strip("-")
    filename = f"placeholder-{slug}.svg"
    if os.path.exists(os.path.join(IMAGE_FOLDER, filename)):
        return filename
    return "placeholder-other.svg"


def looks_like_image(header):
    return (header.startswith(b"\x89PNG") or header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"GIF8") or (header[:4] == b"RIFF" and header[8:12] == b"WEBP"))


def save_image(file):
    """Validate and store an uploaded photo. Returns the new file name or None."""
    if not file or not file.filename:
        return None
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Photo must be a PNG, JPG, GIF or WEBP file.")
    header = file.stream.read(16)
    file.stream.seek(0)
    if not looks_like_image(header):
        raise ValueError("That file does not look like a valid image.")
    filename = f"{uuid.uuid4().hex}.{extension}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def delete_image(filename):
    if filename and not filename.startswith("placeholder"):
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, os.path.basename(filename)))
        except OSError:
            pass


def get_categories():
    return db.query_all("SELECT category_id, name, icon FROM categories ORDER BY category_id")


# ----- decorators ----------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def load_user_and_check_csrf():
    """Runs before every request: loads the logged-in user and verifies the CSRF token."""
    g.user = None
    g.wishlist_ids = set()
    user_id = session.get("user_id")
    if user_id:
        user = db.query_one(
            "SELECT user_id, full_name, email, role, is_active FROM users WHERE user_id = %s",
            (user_id,))
        if user and user["is_active"]:
            g.user = user
            rows = db.query_all("SELECT product_id FROM wishlist WHERE user_id = %s", (user_id,))
            g.wishlist_ids = {row["product_id"] for row in rows}
        else:
            session.pop("user_id", None)
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not token or token != session.get("_csrf"):
            abort(400)


@app.context_processor
def inject_globals():
    return {"current_user": g.get("user"), "wishlist_ids": g.get("wishlist_ids", set())}


# ---------------------------------------------------------------------------
# 2. PUBLIC PAGES
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    categories = db.query_all(
        """SELECT c.category_id, c.name, c.icon, COUNT(p.product_id) AS product_count
           FROM categories c
           LEFT JOIN products p ON p.category_id = c.category_id AND p.status = 'active'
           GROUP BY c.category_id, c.name, c.icon
           ORDER BY c.category_id""")
    featured = db.query_all(
        f"SELECT {CARD_COLUMNS} {CARD_FROM} "
        "WHERE p.status = 'active' AND p.is_featured = 1 ORDER BY p.created_at DESC LIMIT 4")
    recent = db.query_all(
        f"SELECT {CARD_COLUMNS} {CARD_FROM} "
        "WHERE p.status = 'active' ORDER BY p.created_at DESC LIMIT 8")
    stats = db.query_one(
        """SELECT (SELECT COUNT(*) FROM products WHERE status = 'active') AS active_products,
                  (SELECT COUNT(DISTINCT seller_id) FROM products WHERE status = 'active') AS sellers,
                  (SELECT COUNT(*) FROM products WHERE status = 'sold') AS sold_products""")
    return render_template("index.html", categories=categories, featured=featured,
                           recent=recent, stats=stats)


@app.route("/products")
def products():
    q = request.args.get("q", "").strip()[:100]
    category = parse_int(request.args.get("category"))
    min_price = parse_price(request.args.get("min_price"))
    max_price = parse_price(request.args.get("max_price"))
    location = request.args.get("location", "").strip()[:100]
    sort = request.args.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"
    conditions = [c for c in request.args.getlist("condition") if c in CONDITIONS]
    page = max(1, parse_int(request.args.get("page"), 1))

    where = ["p.status = 'active'", "u.is_active = 1"]
    params = []
    if q:
        where.append("(p.title LIKE %s OR p.description LIKE %s)")
        like = f"%{escape_like(q)}%"
        params += [like, like]
    if category:
        where.append("p.category_id = %s")
        params.append(category)
    if min_price is not None and max_price is not None:
        where.append("p.price BETWEEN %s AND %s")
        params += [min_price, max_price]
    elif min_price is not None:
        where.append("p.price >= %s")
        params.append(min_price)
    elif max_price is not None:
        where.append("p.price <= %s")
        params.append(max_price)
    if conditions:
        where.append("p.item_condition IN (" + ", ".join(["%s"] * len(conditions)) + ")")
        params += conditions
    if location:
        where.append("p.location LIKE %s")
        params.append(f"%{escape_like(location)}%")
    where_sql = " AND ".join(where)

    total = db.query_one(f"SELECT COUNT(*) AS total {CARD_FROM} WHERE {where_sql}", params)["total"]
    pages = max(1, -(-total // PER_PAGE))
    page = min(page, pages)
    items = db.query_all(
        f"SELECT {CARD_COLUMNS} {CARD_FROM} WHERE {where_sql} "
        f"ORDER BY {SORT_OPTIONS[sort][1]} LIMIT %s OFFSET %s",
        params + [PER_PAGE, (page - 1) * PER_PAGE])

    locations = db.query_all(
        "SELECT DISTINCT location FROM products WHERE status = 'active' ORDER BY location")
    base_qs = urlencode([(k, v) for k, v in request.args.items(multi=True) if k != "page" and v])
    return render_template(
        "products.html", items=items, total=total, page=page, pages=pages,
        categories=get_categories(), locations=locations, base_qs=base_qs,
        sort_options={k: v[0] for k, v in SORT_OPTIONS.items()},
        filters={"q": q, "category": category, "min_price": request.args.get("min_price", ""),
                 "max_price": request.args.get("max_price", ""), "location": location,
                 "sort": sort, "conditions": conditions})


@app.route("/product/<int:product_id>")
def product_details(product_id):
    product = db.query_one(
        """SELECT p.*, c.name AS category_name,
                  u.full_name AS seller_name, u.phone AS seller_phone,
                  u.location AS seller_location, u.created_at AS seller_since,
                  (SELECT COUNT(*) FROM products WHERE seller_id = u.user_id AND status = 'active') AS seller_active,
                  (SELECT COUNT(*) FROM products WHERE seller_id = u.user_id AND status = 'sold') AS seller_sold,
                  (SELECT COUNT(*) FROM wishlist WHERE product_id = p.product_id) AS saved_count
           FROM products p
           INNER JOIN categories c ON c.category_id = p.category_id
           INNER JOIN users u      ON u.user_id = p.seller_id
           WHERE p.product_id = %s""", (product_id,))
    if product is None:
        abort(404)
    is_owner = g.user is not None and g.user["user_id"] == product["seller_id"]
    is_admin = g.user is not None and g.user["role"] == "admin"
    if product["status"] == "removed" and not (is_owner or is_admin):
        abort(404)
    related = db.query_all(
        f"SELECT {CARD_COLUMNS} {CARD_FROM} "
        "WHERE p.status = 'active' AND p.category_id = %s AND p.product_id <> %s "
        "ORDER BY p.created_at DESC LIMIT 4", (product["category_id"], product_id))
    return render_template("product_details.html", product=product, related=related,
                           is_owner=is_owner, report_reasons=REPORT_REASONS)


# ---------------------------------------------------------------------------
# 3. AUTHENTICATION
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    form, errors = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("full_name", "email", "phone", "location")}
        form["email"] = form["email"].lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not 2 <= len(form["full_name"]) <= 100:
            errors["full_name"] = "Enter your full name (2 to 100 characters)."
        if not EMAIL_RE.match(form["email"]) or len(form["email"]) > 120:
            errors["email"] = "Enter a valid email address."
        if not PHONE_RE.match(form["phone"]):
            errors["phone"] = "Enter a 10-digit mobile number starting with 6, 7, 8 or 9."
        if not 2 <= len(form["location"]) <= 100:
            errors["location"] = "Enter your town or city."
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            errors["password"] = "Use at least 8 characters with a letter and a number."
        if password != confirm:
            errors["confirm_password"] = "The two passwords do not match."
        if "email" not in errors and db.query_one(
                "SELECT user_id FROM users WHERE email = %s", (form["email"],)):
            errors["email"] = "An account with this email already exists. Try logging in."

        if not errors:
            try:
                db.insert(
                    "INSERT INTO users (full_name, email, password_hash, phone, location) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (form["full_name"], form["email"], generate_password_hash(password),
                     form["phone"], form["location"]))
            except db.IntegrityError:
                errors["email"] = "An account with this email already exists. Try logging in."
            else:
                flash("Account created. Log in to start buying and selling.", "success")
                return redirect(url_for("login"))
        flash("Please fix the highlighted fields.", "error")
    return render_template("register.html", form=form, errors=errors)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    next_url = safe_next_url(request.values.get("next"))
    form, error = {}, None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        form["email"] = email
        user = db.query_one("SELECT * FROM users WHERE email = %s", (email,))
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Email or password is incorrect."
        elif not user["is_active"]:
            error = "This account has been disabled. Contact the ReMarket admin."
        else:
            session.clear()
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['full_name'].split()[0]}!", "success")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "index"))
        flash(error, "error")
    return render_template("login.html", form=form, error=error, next_url=next_url)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# 4. BUYER ACTIONS : wishlist, inquiries, reports
# ---------------------------------------------------------------------------
@app.route("/wishlist")
@login_required
def wishlist():
    items = db.query_all(
        f"SELECT {CARD_COLUMNS}, w.created_at AS saved_on {CARD_FROM} "
        "INNER JOIN wishlist w ON w.product_id = p.product_id "
        "WHERE w.user_id = %s AND p.status <> 'removed' ORDER BY w.created_at DESC",
        (g.user["user_id"],))
    return render_template("wishlist.html", items=items)


@app.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
@login_required
def wishlist_toggle(product_id):
    product = db.query_one(
        "SELECT product_id, seller_id, status FROM products WHERE product_id = %s", (product_id,))
    wants_json = request.headers.get("X-Requested-With") == "fetch"
    if product is None or product["status"] == "removed":
        if wants_json:
            return jsonify(ok=False, message="This listing is no longer available."), 404
        abort(404)
    if product["seller_id"] == g.user["user_id"]:
        message = "You cannot save your own listing."
        if wants_json:
            return jsonify(ok=False, message=message), 400
        flash(message, "warning")
        return redirect(request.referrer or url_for("index"))

    existing = db.query_one(
        "SELECT wishlist_id FROM wishlist WHERE user_id = %s AND product_id = %s",
        (g.user["user_id"], product_id))
    if existing:
        db.execute("DELETE FROM wishlist WHERE wishlist_id = %s", (existing["wishlist_id"],))
        saved, message = False, "Removed from your wishlist."
    else:
        try:
            db.execute("INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)",
                       (g.user["user_id"], product_id))
        except db.IntegrityError:
            pass                                    # UNIQUE constraint: already saved
        saved, message = True, "Saved to your wishlist."
    count = db.query_one("SELECT COUNT(*) AS n FROM wishlist WHERE user_id = %s",
                         (g.user["user_id"],))["n"]
    if wants_json:
        return jsonify(ok=True, saved=saved, message=message, count=count)
    flash(message, "success")
    return redirect(safe_next_url(request.form.get("next")) or request.referrer or url_for("wishlist"))


@app.route("/product/<int:product_id>/inquiry", methods=["POST"])
@login_required
def send_inquiry(product_id):
    product = db.query_one(
        "SELECT product_id, seller_id, status FROM products WHERE product_id = %s", (product_id,))
    if product is None or product["status"] == "removed":
        abort(404)
    if product["seller_id"] == g.user["user_id"]:
        flash("You cannot send an inquiry about your own listing.", "warning")
    elif product["status"] == "sold":
        flash("This item has already been sold.", "warning")
    else:
        message = request.form.get("message", "").strip()
        if not 10 <= len(message) <= 1000:
            flash("Your message must be between 10 and 1000 characters.", "error")
        else:
            db.insert("INSERT INTO inquiries (product_id, sender_id, message) VALUES (%s, %s, %s)",
                      (product_id, g.user["user_id"], message))
            flash("Message sent. The seller will see it in their inbox.", "success")
    return redirect(url_for("product_details", product_id=product_id) + "#contact")


@app.route("/product/<int:product_id>/report", methods=["POST"])
@login_required
def report_product(product_id):
    product = db.query_one(
        "SELECT product_id, seller_id, status FROM products WHERE product_id = %s", (product_id,))
    if product is None or product["status"] == "removed":
        abort(404)
    reason = request.form.get("reason", "")
    details = request.form.get("details", "").strip()[:500]
    if product["seller_id"] == g.user["user_id"]:
        flash("You cannot report your own listing.", "warning")
    elif reason not in REPORT_REASONS:
        flash("Please choose a reason for the report.", "error")
    elif db.query_one("SELECT report_id FROM reports WHERE product_id = %s AND reporter_id = %s "
                      "AND status = 'pending'", (product_id, g.user["user_id"])):
        flash("You have already reported this listing. The admin will review it soon.", "info")
    else:
        db.insert("INSERT INTO reports (product_id, reporter_id, reason, details) VALUES (%s, %s, %s, %s)",
                  (product_id, g.user["user_id"], reason, details or None))
        flash("Thanks for the report. The admin team will review this listing.", "success")
    return redirect(url_for("product_details", product_id=product_id))


# ---------------------------------------------------------------------------
# 5. SELLER ACTIONS
# ---------------------------------------------------------------------------
def validate_listing(form, category_ids):
    """Server-side validation shared by the Sell and Edit pages."""
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "price": form.get("price", "").strip(),
        "category_id": form.get("category_id", ""),
        "item_condition": form.get("item_condition", ""),
        "location": form.get("location", "").strip(),
    }
    errors = {}
    if not 5 <= len(data["title"]) <= 150:
        errors["title"] = "Title must be 5 to 150 characters."
    if not 20 <= len(data["description"]) <= 2000:
        errors["description"] = "Description must be 20 to 2000 characters."
    price = parse_price(data["price"])
    if price is None or price <= 0 or price > Decimal("10000000"):
        errors["price"] = "Enter a price greater than 0 and up to ₹1,00,00,000."
    if parse_int(data["category_id"]) not in category_ids:
        errors["category_id"] = "Choose a category."
    if data["item_condition"] not in CONDITIONS:
        errors["item_condition"] = "Choose the item's condition."
    if not 2 <= len(data["location"]) <= 100:
        errors["location"] = "Enter the town where the item is available."
    data["price_value"] = price
    data["category_value"] = parse_int(data["category_id"])
    return data, errors


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    categories = get_categories()
    category_ids = {c["category_id"] for c in categories}
    form, errors = {}, {}
    if request.method == "POST":
        form, errors = validate_listing(request.form, category_ids)
        filename = None
        if not errors:
            try:
                filename = save_image(request.files.get("image"))
            except ValueError as exc:
                errors["image"] = str(exc)
        if not errors:
            if filename is None:
                category_name = next(c["name"] for c in categories
                                     if c["category_id"] == form["category_value"])
                filename = placeholder_for(category_name)
            new_id = db.insert(
                """INSERT INTO products (seller_id, category_id, title, description, price,
                                         item_condition, location, image)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (g.user["user_id"], form["category_value"], form["title"], form["description"],
                 form["price_value"], form["item_condition"], form["location"], filename))
            flash("Your listing is live.", "success")
            return redirect(url_for("product_details", product_id=new_id))
        flash("Please fix the highlighted fields.", "error")
    else:
        me = db.query_one("SELECT location FROM users WHERE user_id = %s", (g.user["user_id"],))
        form = {"location": me["location"]}
    return render_template("sell.html", categories=categories, form=form, errors=errors,
                           editing=False, product=None)


def get_own_product_or_404(product_id):
    """Authorisation: only the seller of a product may edit, delete or relist it."""
    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if product is None:
        abort(404)
    if product["seller_id"] != g.user["user_id"]:
        abort(403)
    return product


@app.route("/product/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = get_own_product_or_404(product_id)
    if product["status"] == "removed":
        flash("This listing was removed by an admin and cannot be edited.", "warning")
        return redirect(url_for("my_listings"))
    categories = get_categories()
    category_ids = {c["category_id"] for c in categories}
    form, errors = dict(product), {}
    form["category_id"] = product["category_id"]
    if request.method == "POST":
        form, errors = validate_listing(request.form, category_ids)
        new_file = None
        if not errors:
            try:
                new_file = save_image(request.files.get("image"))
            except ValueError as exc:
                errors["image"] = str(exc)
        if not errors:
            image = product["image"]
            if new_file:
                delete_image(product["image"])
                image = new_file
            elif product["image"].startswith("placeholder"):
                category_name = next(c["name"] for c in categories
                                     if c["category_id"] == form["category_value"])
                image = placeholder_for(category_name)
            db.execute(
                """UPDATE products
                   SET title = %s, description = %s, price = %s, category_id = %s,
                       item_condition = %s, location = %s, image = %s
                   WHERE product_id = %s AND seller_id = %s""",
                (form["title"], form["description"], form["price_value"], form["category_value"],
                 form["item_condition"], form["location"], image, product_id, g.user["user_id"]))
            flash("Listing updated.", "success")
            return redirect(url_for("product_details", product_id=product_id))
        flash("Please fix the highlighted fields.", "error")
    return render_template("sell.html", categories=categories, form=form, errors=errors,
                           editing=True, product=product)


@app.route("/product/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = get_own_product_or_404(product_id)
    db.execute("DELETE FROM products WHERE product_id = %s AND seller_id = %s",
               (product_id, g.user["user_id"]))
    delete_image(product["image"])
    flash("Listing deleted.", "success")
    return redirect(url_for("my_listings"))


@app.route("/product/<int:product_id>/status", methods=["POST"])
@login_required
def change_status(product_id):
    product = get_own_product_or_404(product_id)
    new_status = request.form.get("status")
    if product["status"] == "removed":
        flash("Removed listings can only be restored by an admin.", "warning")
    elif new_status in ("sold", "active"):
        db.execute("UPDATE products SET status = %s WHERE product_id = %s AND seller_id = %s",
                   (new_status, product_id, g.user["user_id"]))
        flash("Marked as sold. Congratulations!" if new_status == "sold"
              else "Listing is active again.", "success")
    return redirect(request.referrer or url_for("my_listings"))


@app.route("/my-listings")
@login_required
def my_listings():
    status = request.args.get("status", "all")
    uid = g.user["user_id"]
    sql = """SELECT p.product_id, p.title, p.price, p.item_condition, p.location, p.image,
                    p.status, p.created_at, c.name AS category_name,
                    (SELECT COUNT(*) FROM inquiries i WHERE i.product_id = p.product_id) AS inquiry_count,
                    (SELECT COUNT(*) FROM wishlist w WHERE w.product_id = p.product_id) AS wishlist_count
             FROM products p
             INNER JOIN categories c ON c.category_id = p.category_id
             WHERE p.seller_id = %s"""
    params = [uid]
    if status in ("active", "sold", "removed"):
        sql += " AND p.status = %s"
        params.append(status)
    else:
        status = "all"
    sql += " ORDER BY p.created_at DESC"
    listings = db.query_all(sql, params)
    counts = db.query_one(
        """SELECT COUNT(*) AS total,
                  SUM(status = 'active') AS active,
                  SUM(status = 'sold') AS sold,
                  SUM(status = 'removed') AS removed
           FROM products WHERE seller_id = %s""", (uid,))
    inquiries = db.query_all(
        """SELECT i.inquiry_id, i.message, i.is_read, i.created_at,
                  p.product_id, p.title, s.full_name AS sender_name,
                  s.email AS sender_email, s.phone AS sender_phone
           FROM inquiries i
           INNER JOIN products p ON p.product_id = i.product_id
           INNER JOIN users s    ON s.user_id = i.sender_id
           WHERE p.seller_id = %s
           ORDER BY i.is_read ASC, i.created_at DESC""", (uid,))
    return render_template("my_listings.html", listings=listings, counts=counts,
                           status=status, inquiries=inquiries)


@app.route("/inquiry/<int:inquiry_id>/read", methods=["POST"])
@login_required
def mark_inquiry_read(inquiry_id):
    # The JOIN makes sure the inquiry belongs to a product owned by this user.
    changed = db.execute(
        """UPDATE inquiries i INNER JOIN products p ON p.product_id = i.product_id
           SET i.is_read = 1 WHERE i.inquiry_id = %s AND p.seller_id = %s""",
        (inquiry_id, g.user["user_id"]))
    if not changed:
        abort(403)
    flash("Inquiry marked as read.", "success")
    return redirect(url_for("my_listings") + "#inbox")


# ---------------------------------------------------------------------------
# 6. PROFILE
# ---------------------------------------------------------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = g.user["user_id"]
    errors, pw_errors = {}, {}
    user = db.query_one("SELECT * FROM users WHERE user_id = %s", (uid,))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip()
            location = request.form.get("location", "").strip()
            if not 2 <= len(name) <= 100:
                errors["full_name"] = "Enter your full name (2 to 100 characters)."
            if not PHONE_RE.match(phone):
                errors["phone"] = "Enter a 10-digit mobile number starting with 6, 7, 8 or 9."
            if not 2 <= len(location) <= 100:
                errors["location"] = "Enter your town or city."
            if not errors:
                db.execute("UPDATE users SET full_name = %s, phone = %s, location = %s "
                           "WHERE user_id = %s", (name, phone, location, uid))
                flash("Profile updated.", "success")
                return redirect(url_for("profile"))
            user.update(full_name=name, phone=phone, location=location)
            flash("Please fix the highlighted fields.", "error")
        elif action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            if not check_password_hash(user["password_hash"], current):
                pw_errors["current_password"] = "Current password is incorrect."
            if len(new) < 8 or not re.search(r"[A-Za-z]", new) or not re.search(r"\d", new):
                pw_errors["new_password"] = "Use at least 8 characters with a letter and a number."
            if new != confirm:
                pw_errors["confirm_password"] = "The two passwords do not match."
            if not pw_errors:
                db.execute("UPDATE users SET password_hash = %s WHERE user_id = %s",
                           (generate_password_hash(new), uid))
                flash("Password changed.", "success")
                return redirect(url_for("profile"))
            flash("Password was not changed. Check the highlighted fields.", "error")

    stats = db.query_one(
        """SELECT
             (SELECT COUNT(*) FROM products WHERE seller_id = %s) AS total_listings,
             (SELECT COUNT(*) FROM products WHERE seller_id = %s AND status = 'active') AS active_listings,
             (SELECT COUNT(*) FROM products WHERE seller_id = %s AND status = 'sold') AS sold_listings,
             (SELECT COALESCE(SUM(price), 0) FROM products WHERE seller_id = %s AND status = 'sold') AS sold_value,
             (SELECT COUNT(*) FROM wishlist WHERE user_id = %s) AS wishlist_count,
             (SELECT COUNT(*) FROM inquiries i INNER JOIN products p ON p.product_id = i.product_id
                WHERE p.seller_id = %s) AS inquiries_received,
             (SELECT COUNT(*) FROM inquiries WHERE sender_id = %s) AS inquiries_sent""",
        (uid,) * 7)
    sent = db.query_all(
        """SELECT i.message, i.created_at, p.product_id, p.title, s.full_name AS seller_name
           FROM inquiries i
           INNER JOIN products p ON p.product_id = i.product_id
           INNER JOIN users s    ON s.user_id = p.seller_id
           WHERE i.sender_id = %s ORDER BY i.created_at DESC LIMIT 5""", (uid,))
    return render_template("profile.html", user=user, stats=stats, sent=sent,
                           errors=errors, pw_errors=pw_errors)


# ---------------------------------------------------------------------------
# 7. ADMIN PANEL
# ---------------------------------------------------------------------------
@app.route("/admin")
@admin_required
def admin_dashboard():
    totals = db.query_one(
        """SELECT (SELECT COUNT(*) FROM users WHERE role = 'user') AS users,
                  (SELECT COUNT(*) FROM products) AS products,
                  (SELECT COUNT(*) FROM products WHERE status = 'active') AS active_products,
                  (SELECT COUNT(*) FROM products WHERE status = 'sold') AS sold_products,
                  (SELECT COUNT(*) FROM categories) AS categories,
                  (SELECT COUNT(*) FROM inquiries) AS inquiries,
                  (SELECT COUNT(*) FROM wishlist) AS wishlist_items,
                  (SELECT COUNT(*) FROM reports WHERE status = 'pending') AS pending_reports,
                  (SELECT COALESCE(ROUND(AVG(price)), 0) FROM products WHERE status = 'active') AS avg_price""")
    category_stats = db.query_all(
        """SELECT c.name, COUNT(p.product_id) AS product_count,
                  COALESCE(ROUND(AVG(p.price)), 0) AS avg_price,
                  COALESCE(MIN(p.price), 0) AS min_price,
                  COALESCE(MAX(p.price), 0) AS max_price
           FROM categories c
           LEFT JOIN products p ON p.category_id = c.category_id AND p.status = 'active'
           GROUP BY c.category_id, c.name
           ORDER BY product_count DESC, c.name""")
    top_sellers = db.query_all(
        """SELECT u.full_name, u.location, COUNT(p.product_id) AS listings,
                  SUM(p.status = 'sold') AS sold
           FROM users u
           INNER JOIN products p ON p.seller_id = u.user_id
           GROUP BY u.user_id, u.full_name, u.location
           HAVING COUNT(p.product_id) >= 2
           ORDER BY listings DESC, u.full_name LIMIT 5""")
    recent = db.query_all(
        """SELECT p.product_id, p.title, p.price, p.status, p.created_at,
                  c.name AS category_name, u.full_name AS seller_name
           FROM products p
           INNER JOIN categories c ON c.category_id = p.category_id
           INNER JOIN users u ON u.user_id = p.seller_id
           ORDER BY p.created_at DESC LIMIT 6""")
    pending = db.query_all(
        """SELECT r.report_id, r.reason, r.created_at, p.title, p.product_id
           FROM reports r INNER JOIN products p ON p.product_id = r.product_id
           WHERE r.status = 'pending' ORDER BY r.created_at DESC LIMIT 5""")
    return render_template("admin/dashboard.html", totals=totals, category_stats=category_stats,
                           top_sellers=top_sellers, recent=recent, pending=pending)


@app.route("/admin/users")
@admin_required
def admin_users():
    q = request.args.get("q", "").strip()[:100]
    sql = """SELECT u.user_id, u.full_name, u.email, u.phone, u.location, u.role, u.is_active,
                    u.created_at, COUNT(p.product_id) AS listing_count
             FROM users u
             LEFT JOIN products p ON p.seller_id = u.user_id"""
    params = []
    if q:
        sql += " WHERE u.full_name LIKE %s OR u.email LIKE %s OR u.location LIKE %s"
        like = f"%{escape_like(q)}%"
        params = [like, like, like]
    sql += """ GROUP BY u.user_id, u.full_name, u.email, u.phone, u.location, u.role,
                        u.is_active, u.created_at
               ORDER BY u.created_at DESC"""
    return render_template("admin/users.html", users=db.query_all(sql, params), q=q)


@app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
@admin_required
def admin_user_action(user_id, action):
    user = db.query_one("SELECT user_id, full_name, role, is_active FROM users WHERE user_id = %s",
                        (user_id,))
    if user is None:
        abort(404)
    if user_id == g.user["user_id"]:
        flash("You cannot change or delete your own admin account.", "warning")
    elif action in ("disable", "enable"):
        db.execute("UPDATE users SET is_active = %s WHERE user_id = %s",
                   (1 if action == "enable" else 0, user_id))
        flash(f"{user['full_name']} has been {'enabled' if action == 'enable' else 'disabled'}.",
              "success")
    elif action == "delete":
        images = db.query_all("SELECT image FROM products WHERE seller_id = %s", (user_id,))
        db.execute("DELETE FROM users WHERE user_id = %s", (user_id,))   # cascades to products etc.
        for row in images:
            delete_image(row["image"])
        flash(f"{user['full_name']} and all of their data were deleted.", "success")
    else:
        abort(404)
    return redirect(url_for("admin_users"))


@app.route("/admin/products")
@admin_required
def admin_products():
    q = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    sql = """SELECT p.product_id, p.title, p.price, p.status, p.is_featured, p.created_at,
                    p.image, c.name AS category_name, u.full_name AS seller_name,
                    (SELECT COUNT(*) FROM reports r WHERE r.product_id = p.product_id
                       AND r.status = 'pending') AS open_reports
             FROM products p
             INNER JOIN categories c ON c.category_id = p.category_id
             INNER JOIN users u ON u.user_id = p.seller_id
             WHERE 1 = 1"""
    params = []
    if q:
        sql += " AND (p.title LIKE %s OR u.full_name LIKE %s)"
        like = f"%{escape_like(q)}%"
        params += [like, like]
    if status in ("active", "sold", "removed"):
        sql += " AND p.status = %s"
        params.append(status)
    else:
        status = ""
    sql += " ORDER BY p.created_at DESC"
    return render_template("admin/products.html", products=db.query_all(sql, params),
                           q=q, status=status)


@app.route("/admin/products/<int:product_id>/<action>", methods=["POST"])
@admin_required
def admin_product_action(product_id, action):
    product = db.query_one("SELECT product_id, title, image FROM products WHERE product_id = %s",
                           (product_id,))
    if product is None:
        abort(404)
    if action == "remove":
        db.execute("UPDATE products SET status = 'removed', is_featured = 0 WHERE product_id = %s",
                   (product_id,))
        flash("Listing removed from the marketplace.", "success")
    elif action == "restore":
        db.execute("UPDATE products SET status = 'active' WHERE product_id = %s", (product_id,))
        flash("Listing restored.", "success")
    elif action in ("feature", "unfeature"):
        db.execute("UPDATE products SET is_featured = %s WHERE product_id = %s AND status = 'active'",
                   (1 if action == "feature" else 0, product_id))
        flash("Featured status updated.", "success")
    elif action == "delete":
        db.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        delete_image(product["image"])
        flash("Listing permanently deleted.", "success")
    else:
        abort(404)
    return redirect(request.referrer or url_for("admin_products"))


@app.route("/admin/categories")
@admin_required
def admin_categories():
    categories = db.query_all(
        """SELECT c.category_id, c.name, c.description, c.icon, COUNT(p.product_id) AS product_count
           FROM categories c LEFT JOIN products p ON p.category_id = c.category_id
           GROUP BY c.category_id, c.name, c.description, c.icon
           ORDER BY c.category_id""")
    return render_template("admin/categories.html", categories=categories)


def read_category_form():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    icon = request.form.get("icon", "").strip() or "bi-grid"
    problems = []
    if not 2 <= len(name) <= 50:
        problems.append("Category name must be 2 to 50 characters.")
    if len(description) > 255:
        problems.append("Description can be at most 255 characters.")
    if not ICON_RE.match(icon):
        problems.append("Icon must be a Bootstrap Icons class such as bi-tv.")
    return name, description or None, icon, problems


@app.route("/admin/categories/add", methods=["POST"])
@admin_required
def admin_category_add():
    name, description, icon, problems = read_category_form()
    if problems:
        flash(" ".join(problems), "error")
    else:
        try:
            db.insert("INSERT INTO categories (name, description, icon) VALUES (%s, %s, %s)",
                      (name, description, icon))
            flash(f"Category “{name}” added.", "success")
        except db.IntegrityError:
            flash("A category with that name already exists.", "error")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/edit", methods=["POST"])
@admin_required
def admin_category_edit(category_id):
    name, description, icon, problems = read_category_form()
    if problems:
        flash(" ".join(problems), "error")
    else:
        try:
            db.execute("UPDATE categories SET name = %s, description = %s, icon = %s "
                       "WHERE category_id = %s", (name, description, icon, category_id))
            flash("Category updated.", "success")
        except db.IntegrityError:
            flash("A category with that name already exists.", "error")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_category_delete(category_id):
    used = db.query_one("SELECT COUNT(*) AS n FROM products WHERE category_id = %s",
                        (category_id,))["n"]
    if used:
        flash(f"This category still has {used} listing(s). Move or delete them first.", "error")
    else:
        db.execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
        flash("Category deleted.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/reports")
@admin_required
def admin_reports():
    status = request.args.get("status", "pending")
    if status not in ("pending", "resolved", "dismissed", "all"):
        status = "pending"
    sql = """SELECT r.report_id, r.reason, r.details, r.status, r.created_at, r.resolved_at,
                    p.product_id, p.title, p.status AS product_status,
                    rep.full_name AS reporter_name, s.full_name AS seller_name
             FROM reports r
             INNER JOIN products p ON p.product_id = r.product_id
             INNER JOIN users rep  ON rep.user_id = r.reporter_id
             INNER JOIN users s    ON s.user_id = p.seller_id"""
    params = []
    if status != "all":
        sql += " WHERE r.status = %s"
        params.append(status)
    sql += " ORDER BY r.created_at DESC"
    counts = db.query_one(
        """SELECT SUM(status = 'pending') AS pending, SUM(status = 'resolved') AS resolved,
                  SUM(status = 'dismissed') AS dismissed, COUNT(*) AS total FROM reports""")
    return render_template("admin/reports.html", reports=db.query_all(sql, params),
                           status=status, counts=counts)


@app.route("/admin/reports/<int:report_id>/<action>", methods=["POST"])
@admin_required
def admin_report_action(report_id, action):
    report = db.query_one("SELECT report_id, product_id FROM reports WHERE report_id = %s",
                          (report_id,))
    if report is None:
        abort(404)
    if action == "resolve":
        db.execute("UPDATE reports SET status = 'resolved', resolved_at = NOW() WHERE report_id = %s",
                   (report_id,))
        flash("Report marked as resolved.", "success")
    elif action == "dismiss":
        db.execute("UPDATE reports SET status = 'dismissed', resolved_at = NOW() WHERE report_id = %s",
                   (report_id,))
        flash("Report dismissed.", "success")
    elif action == "remove_listing":
        db.execute("UPDATE products SET status = 'removed', is_featured = 0 WHERE product_id = %s",
                   (report["product_id"],))
        db.execute("UPDATE reports SET status = 'resolved', resolved_at = NOW() "
                   "WHERE product_id = %s AND status = 'pending'", (report["product_id"],))
        flash("Listing removed and all its pending reports were resolved.", "success")
    else:
        abort(404)
    return redirect(url_for("admin_reports", status=request.form.get("view", "pending")))


@app.route("/admin/sql-demo")
@admin_required
def admin_sql_demo():
    results = []
    for item in DEMO_QUERIES:
        entry = dict(item)
        try:
            rows = db.query_all(item["sql"])
            entry["columns"] = list(rows[0].keys()) if rows else []
            entry["rows"] = rows[:15]
            entry["row_count"] = len(rows)
            entry["error"] = None
        except db.Error as exc:
            entry.update(columns=[], rows=[], row_count=0, error=str(exc))
        results.append(entry)
    return render_template("admin/sql_demo.html", results=results)


# ---------------------------------------------------------------------------
# 8. ERROR HANDLERS AND ENTRY POINT
# ---------------------------------------------------------------------------
ERROR_TEXT = {
    400: ("Request could not be verified", "Your session may have expired. Go back, refresh the page and try again."),
    403: ("You do not have access", "This page belongs to another account or needs admin rights."),
    404: ("We could not find that page", "The listing may have been sold, removed or the link may be wrong."),
    413: ("That file is too large", "Photos must be 3 MB or smaller. Choose a smaller image and try again."),
}


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
def show_error(error):
    title, message = ERROR_TEXT.get(error.code, ("Something went wrong", ""))
    return render_template("error.html", code=error.code, title=title, message=message), error.code


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", code=500, title="Something went wrong on our side",
                           message="Please try again in a moment. If this keeps happening, check that MySQL is running."), 500


if __name__ == "__main__":
    app.run(debug=True)
