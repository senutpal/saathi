from flask import Blueprint, abort, current_app, render_template
from flask_login import login_required

bp = Blueprint("main", __name__)


@bp.get("/")
@login_required
def index() -> str:
    return render_template("main/home.html")


@bp.get("/dev/style")
def style() -> str:
    if current_app.config["SAATHI_ENV"] != "development":
        abort(404)
    return render_template("main/style.html")
