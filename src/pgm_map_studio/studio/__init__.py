"""Flask application factory for PGM Map Studio."""
from __future__ import annotations

import logging

from flask import Flask

from .routes import apply_rules, build_regions, config, configure, filters, map_api, minecraft, objectives, pages, pipeline, regions, sketch_api, sources, teams, spawns, wiring


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.register_blueprint(pages.bp)
    app.register_blueprint(config.bp)
    app.register_blueprint(configure.bp)
    app.register_blueprint(sources.bp)
    app.register_blueprint(pipeline.bp)
    app.register_blueprint(map_api.bp)
    app.register_blueprint(regions.bp)
    app.register_blueprint(teams.bp)
    app.register_blueprint(spawns.bp)
    app.register_blueprint(minecraft.bp)
    app.register_blueprint(sketch_api.bp)
    app.register_blueprint(build_regions.bp)
    app.register_blueprint(objectives.bp)
    app.register_blueprint(filters.bp)
    app.register_blueprint(apply_rules.bp)
    app.register_blueprint(wiring.bp)

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
