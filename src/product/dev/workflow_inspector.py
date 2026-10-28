"""Serve the current application AI configuration without the app frontend."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from product.application.workflows.inspection_models import (
    ApplicationConfigurationInspectionDTO,
)
from product.dev.current_configuration import current_application_configuration


def make_server(
    configuration: ApplicationConfigurationInspectionDTO,
    *,
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Build a loopback-only server over the assembled application configuration."""
    page = Path(__file__).with_name("workflow_inspector.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/configuration":
                payload = configuration.model_dump_json().encode("utf-8")
                content_type = "application/json; charset=utf-8"
            elif self.path == "/":
                payload = page
                content_type = "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(
    configuration: ApplicationConfigurationInspectionDTO,
    *,
    port: int = 8765,
) -> None:
    """Serve one provider-free snapshot assembled from the current application code."""
    with make_server(configuration, port=port) as server:
        print(f"Workflow inspector: http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="View current AI configuration locally.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(current_application_configuration(), port=args.port)


if __name__ == "__main__":
    main()
