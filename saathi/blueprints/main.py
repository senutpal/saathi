from flask import Blueprint, abort, current_app, redirect, render_template
from flask_login import current_user

bp = Blueprint("main", __name__)


@bp.get("/")
def index() -> str:
    if not current_user.is_authenticated:
        return redirect("/auth/login")
    return render_template("main/home.html")


@bp.get("/dev/style")
def style() -> str:
    if current_app.config["SAATHI_ENV"] != "development":
        abort(404)
    return render_template("main/style.html")
