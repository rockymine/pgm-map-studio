from __future__ import annotations

from flask import Blueprint, render_template, request

bp = Blueprint("pages", __name__)


@bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@bp.route("/editor")
def editor():
    return render_template("editor.html")


@bp.route("/configure")
def configure():
    map_name = request.args.get("map", "")
    return render_template("configure.html", map_name=map_name)


@bp.route("/design")
def design():
    return render_template("design.html")
