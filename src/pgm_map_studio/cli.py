"""CLI entry point for PGM Map Studio."""
import argparse


def main():
    parser = argparse.ArgumentParser(description="PGM Map Studio")
    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Start the Map Studio web server")
    serve_p.add_argument("--port", type=int, default=7892, help="Port (default: 7892)")
    serve_p.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    serve_p.add_argument("--no-browser", action="store_true", help="Do not open browser")

    args = parser.parse_args()

    if args.command == "serve" or args.command is None:
        from pgm_map_studio.studio import run_server
        port = getattr(args, "port", 7892)
        host = getattr(args, "host", "0.0.0.0")
        open_browser = not getattr(args, "no_browser", False)
        run_server(port=port, host=host, open_browser=open_browser)
    else:
        parser.print_help()
