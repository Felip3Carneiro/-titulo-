import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


ROOT_DIR = Path(__file__).resolve().parent
ACTION_CATALOG = {
    "bike": {"title": "Vá de bike ou a pé", "points": 20},
    "plant": {"title": "Monte um prato vegetal", "points": 15},
    "energy": {"title": "Economize energia", "points": 10},
    "reusable": {"title": "Reutilize antes de descartar", "points": 15},
}
MISSION_TARGET = 3
MISSION_BONUS = 20
LEVEL_NAMES = ("Semente", "Broto", "Muda", "Árvore")


def create_app(test_config=None):
    app = Flask(__name__, template_folder=str(ROOT_DIR), static_folder=None)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get(
            "ECHO_SCORE_DATABASE",
            str(ROOT_DIR / "instance" / "echo_score.sqlite"),
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    database_directory = os.path.dirname(app.config["DATABASE"])
    if database_directory:
        os.makedirs(database_directory, exist_ok=True)

    @app.teardown_appcontext
    def close_database(_error=None):
        database = g.pop("database", None)
        if database is not None:
            database.close()

    with app.app_context():
        initialize_database()

    @app.before_request
    def load_current_user():
        user_id = session.get("user_id")
        g.current_user = None
        if user_id is not None:
            g.current_user = get_database().execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if g.current_user is None:
                session.clear()

    @app.get("/style.css")
    def stylesheet():
        return send_file(ROOT_DIR / "style.css", mimetype="text/css")

    @app.get("/")
    def home():
        if g.current_user is None:
            return render_template("index.html", current_user=None)
        return render_template(
            "index.html",
            current_user=g.current_user,
            **get_dashboard_data(g.current_user["id"]),
        )

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if g.current_user is not None:
            return redirect(url_for("home"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = get_database().execute(
                "SELECT id, name, email, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("E-mail ou senha incorretos.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Que bom ter você de volta!", "success")
                return redirect(url_for("home"))
        return render_template("auth.html", mode="login", current_user=None)

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if g.current_user is not None:
            return redirect(url_for("home"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name or len(name) > 40:
                flash("Informe um nome com até 40 caracteres.", "error")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Informe um e-mail válido.", "error")
            elif len(password) < 6:
                flash("A senha precisa ter pelo menos 6 caracteres.", "error")
            else:
                try:
                    database = get_database()
                    cursor = database.execute(
                        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    database.commit()
                except sqlite3.IntegrityError:
                    flash("Já existe uma conta com esse e-mail.", "error")
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("Conta criada! Sua jornada começa agora.", "success")
                    return redirect(url_for("home"))
        return render_template("auth.html", mode="register", current_user=None)

    @app.post("/logout")
    def logout():
        session.clear()
        flash("Você saiu da sua conta.", "success")
        return redirect(url_for("home"))

    @app.post("/actions/<action_id>")
    @login_required
    def register_action(action_id):
        action = ACTION_CATALOG.get(action_id)
        if action is None:
            abort(404)

        database = get_database()
        today = date.today().isoformat()
        already_registered = database.execute(
            """
            SELECT 1 FROM actions
            WHERE user_id = ? AND action_key = ? AND action_date = ?
            """,
            (g.current_user["id"], action_id, today),
        ).fetchone()
        if already_registered:
            flash("Você já registrou essa ação hoje.", "error")
            return redirect(url_for("home"))

        completed_today = database.execute(
            "SELECT COUNT(*) FROM actions WHERE user_id = ? AND action_date = ?",
            (g.current_user["id"], today),
        ).fetchone()[0]
        bonus = MISSION_BONUS if completed_today == MISSION_TARGET - 1 else 0
        database.execute(
            """
            INSERT INTO actions (user_id, action_key, action_date, points)
            VALUES (?, ?, ?, ?)
            """,
            (g.current_user["id"], action_id, today, action["points"] + bonus),
        )
        database.commit()

        message = f"Ação registrada: +{action['points']} XP."
        if bonus:
            message += f" Missão diária concluída: bônus de +{bonus} XP!"
        flash(message, "success")
        return redirect(url_for("home"))

    return app


def get_database():
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"])
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
    return g.database


def initialize_database():
    database = get_database()
    database.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action_key TEXT NOT NULL,
            action_date TEXT NOT NULL,
            points INTEGER NOT NULL,
            UNIQUE (user_id, action_key, action_date)
        );
        """
    )
    database.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.current_user is None:
            flash("Entre na sua conta para registrar uma ação.", "error")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def get_dashboard_data(user_id):
    database = get_database()
    total_points = database.execute(
        "SELECT COALESCE(SUM(points), 0) FROM actions WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    total_actions = database.execute(
        "SELECT COUNT(*) FROM actions WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    today = date.today()
    today_actions = database.execute(
        "SELECT action_key FROM actions WHERE user_id = ? AND action_date = ?",
        (user_id, today.isoformat()),
    ).fetchall()
    completed_actions = {row["action_key"] for row in today_actions}
    activity_dates = {
        date.fromisoformat(row["action_date"])
        for row in database.execute(
            "SELECT DISTINCT action_date FROM actions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    }

    cursor = today if today in activity_dates else today - timedelta(days=1)
    streak = 0
    while cursor in activity_dates:
        streak += 1
        cursor -= timedelta(days=1)

    level = total_points // 100 + 1
    progress = total_points % 100
    level_name = LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)]
    actions = [
        {
            **details,
            "id": action_id,
            "completed": action_id in completed_actions,
        }
        for action_id, details in ACTION_CATALOG.items()
    ]
    badges = [
        {
            "key": key,
            "title": title,
            "description": description,
            "unlocked": total_actions >= threshold,
        }
        for key, title, description, threshold in (
            ("first", "Primeiro passo", "Registre sua primeira ação", 1),
            ("five", "Raízes fortes", "Complete 5 ações", 5),
            ("twelve", "Agente de mudança", "Complete 12 ações", 12),
        )
    ]

    return {
        "total_points": total_points,
        "total_actions": total_actions,
        "today_count": len(today_actions),
        "streak": streak,
        "level": level,
        "level_name": level_name,
        "level_progress": progress,
        "level_progress_text": f"{progress} / 100 XP",
        "mission_progress": min(len(today_actions), MISSION_TARGET),
        "mission_target": MISSION_TARGET,
        "mission_bonus": MISSION_BONUS,
        "actions": actions,
        "badges": badges,
        "badge_count": sum(badge["unlocked"] for badge in badges),
    }


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")