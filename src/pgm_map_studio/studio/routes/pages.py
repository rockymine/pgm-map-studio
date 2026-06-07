from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)


@bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@bp.route("/editor")
def editor():
    return render_template("editor.html")


@bp.route("/sketch")
def sketch():
    return render_template("sketch.html")


@bp.route("/design")
def design():
    return render_template("design.html")
