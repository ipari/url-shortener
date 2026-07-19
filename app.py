import os
import re
import secrets
import sqlite3
import string
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash


ALPHABET = string.ascii_letters + string.digits
SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
DANGEROUS_SCHEMES = {"javascript", "data", "vbscript"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("URL_SHORTENER_SECRET_KEY"),
        DATABASE=str(Path(app.instance_path) / "urls.sqlite3"),
        ADMIN_USERNAME=os.environ.get("URL_SHORTENER_USERNAME", "admin"),
        ADMIN_PASSWORD=os.environ.get("URL_SHORTENER_PASSWORD", "change-me"),
        ADMIN_PASSWORD_HASH=os.environ.get("URL_SHORTENER_PASSWORD_HASH"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        secret_file = Path(app.instance_path) / ".secret_key"
        if secret_file.exists():
            app.config["SECRET_KEY"] = secret_file.read_text(encoding="utf-8").strip()
        else:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
            secret_file.write_text(app.config["SECRET_KEY"], encoding="utf-8")

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        get_db().execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        get_db().commit()

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    def valid_csrf():
        supplied = request.form.get("csrf_token", "")
        return secrets.compare_digest(supplied, session.get("csrf_token", ""))

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def password_matches(candidate):
        password_hash = app.config.get("ADMIN_PASSWORD_HASH")
        if password_hash:
            return check_password_hash(password_hash, candidate)
        return secrets.compare_digest(candidate, app.config["ADMIN_PASSWORD"])

    def normalize_url(value):
        value = value.strip()
        if not value:
            return None

        if not SCHEME_PATTERN.match(value):
            value = "https://" + value

        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        if not scheme or scheme in DANGEROUS_SCHEMES:
            return None
        if scheme in {"http", "https"} and not parsed.netloc:
            return None
        if scheme not in {"http", "https"} and not value[len(parsed.scheme) + 1 :]:
            return None
        return value

    def new_code(length=7):
        db = get_db()
        while True:
            code = "".join(secrets.choice(ALPHABET) for _ in range(length))
            exists = db.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone()
            if not exists:
                return code

    @app.get("/")
    @login_required
    def dashboard():
        db = get_db()
        urls = db.execute(
            "SELECT id, code, original_url, clicks, created_at FROM urls ORDER BY id DESC"
        ).fetchall()
        created_code = request.args.get("created")
        created = (
            db.execute(
                "SELECT code FROM urls WHERE code = ?", (created_code,)
            ).fetchone()
            if created_code
            else None
        )
        created_url = (
            url_for("follow_short_url", code=created["code"], _external=True)
            if created
            else None
        )
        return render_template(
            "dashboard.html",
            urls=urls,
            created_url=created_url,
            result_kind=request.args.get("status"),
        )

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if request.method == "POST":
            if not valid_csrf():
                abort(400)
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            username_matches = secrets.compare_digest(
                username, app.config["ADMIN_USERNAME"]
            )
            if username_matches and password_matches(password):
                session.clear()
                session["logged_in"] = True
                return redirect(url_for("dashboard"))
            flash("아이디 또는 비밀번호가 올바르지 않습니다.", "error")
        return render_template("login.html")

    @app.post("/logout")
    @login_required
    def logout():
        if not valid_csrf():
            abort(400)
        session.clear()
        return redirect(url_for("login"))

    @app.post("/urls")
    @login_required
    def create_url():
        if not valid_csrf():
            abort(400)
        original_url = normalize_url(request.form.get("original_url", ""))
        if not original_url:
            flash("올바른 URL 또는 프로토콜 링크를 입력해 주세요.", "error")
            return redirect(url_for("dashboard"))
        db = get_db()
        existing = db.execute(
            "SELECT code FROM urls WHERE original_url = ? ORDER BY id LIMIT 1",
            (original_url,),
        ).fetchone()
        if existing:
            code, status = existing["code"], "existing"
        else:
            code, status = new_code(), "created"
            db.execute(
                "INSERT INTO urls (code, original_url) VALUES (?, ?)",
                (code, original_url),
            )
            db.commit()
        return redirect(url_for("dashboard", created=code, status=status), code=303)

    @app.post("/urls/<int:url_id>/delete")
    @login_required
    def delete_url(url_id):
        if not valid_csrf():
            abort(400)
        db = get_db()
        cursor = db.execute("DELETE FROM urls WHERE id = ?", (url_id,))
        db.commit()
        if cursor.rowcount:
            flash("단축 URL을 삭제했습니다.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/s/<code>")
    def follow_short_url(code):
        db = get_db()
        row = db.execute(
            "SELECT id, original_url FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            abort(404)
        db.execute("UPDATE urls SET clicks = clicks + 1 WHERE id = ?", (row["id"],))
        db.commit()
        return redirect(row["original_url"], code=302)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
