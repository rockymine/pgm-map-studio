"""Flask application factory for PGM Map Studio."""
from __future__ import annotations

import logging

from flask import Flask

from .routes import config, map_api, minecraft, pages, pipeline, sources, teams, spawns


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.register_blueprint(pages.bp)
    app.register_blueprint(config.bp)
    app.register_blueprint(sources.bp)
    app.register_blueprint(pipeline.bp)
    app.register_blueprint(map_api.bp)
    app.register_blueprint(teams.bp)
    app.register_blueprint(spawns.bp)
    app.register_blueprint(minecraft.bp)

    return app


def run_server(port: int = 7892, host: str = "0.0.0.0", open_browser: bool = True) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    app = create_app()
    url = f"http://localhost:{port}"
    print(f"PGM Map Studio running at {url}", flush=True)

    if open_browser:
        import webbrowser
        webbrowser.open(url)

    app.run(host=host, port=port, debug=False)
