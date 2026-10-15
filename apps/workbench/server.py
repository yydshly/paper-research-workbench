"""Run with python -m apps.workbench.server. No third-party dependencies."""
import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from apps.workbench.service import ROOT, Workbench
from research.errors import ResearchError

WEB = Path(__file__).with_name("web")
DOCS = {"requirements", "goals", "competitors", "roadmap", "acceptance", "data-licensing", "architecture", "model-contract"}


def make_server(port=8765, service=None):
    workbench = service or Workbench()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not record query contents or article requests.

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def send_body(self, status, body, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, data):
            self.send_body(status, json.dumps(data, ensure_ascii=False).encode())

        def do_GET(self):
            try:
                if not self.valid_host():
                    raise ResearchError("INVALID_HOST", "此服务仅供本机访问。", 403)
                path = unquote(urlsplit(self.path).path)
                if path == "/api/status":
                    return self.send_json(200, workbench.status())
                if path.startswith("/api/papers/"):
                    return self.send_json(200, workbench.paper(path.removeprefix("/api/papers/")))
                if path.startswith("/api/docs/"):
                    name = path.removeprefix("/api/docs/")
                    if name not in DOCS:
                        raise ResearchError("NOT_FOUND", "文档不存在。", 404)
                    return self.send_json(200, {"name": name, "content": (ROOT / "docs" / (name + ".md")).read_text(encoding="utf-8")})
                static = (WEB / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
                if not static.is_relative_to(WEB.resolve()) or not static.is_file():
                    raise ResearchError("NOT_FOUND", "页面不存在。", 404)
                content_type = mimetypes.guess_type(static.name)[0] or "application/octet-stream"
                if static.suffix == ".js":
                    content_type = "text/javascript"
                return self.send_body(200, static.read_bytes(), content_type + "; charset=utf-8")
            except ResearchError as exc:
                self.send_json(exc.status, exc.as_dict())
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.send_json(500, {"error": {"code": "INTERNAL_ERROR", "message": "本地服务发生错误，请重试或查看测试记录。"}})

        def do_POST(self):
            try:
                if not self.valid_host():
                    raise ResearchError("INVALID_HOST", "此服务仅供本机访问。", 403)
                expected = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
                if self.headers.get("Origin") not in (None, *expected):
                    raise ResearchError("CROSS_ORIGIN", "不接受其他网页发起的请求。", 403)
                if self.headers.get_content_type() != "application/json":
                    raise ResearchError("INVALID_INPUT", "需要 JSON 请求。", 400)
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 16384:
                        raise ValueError("size")
                    payload = json.loads(self.rfile.read(size))
                    if not isinstance(payload, dict):
                        raise ValueError("shape")
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ResearchError("INVALID_INPUT", "请求格式或大小无效。", 400) from exc
                if self.path == "/api/search":
                    return self.send_json(200, workbench.search(payload.get("query"), payload.get("count", 75)))
                if self.path == "/api/explain":
                    workbench.explain()
                raise ResearchError("NOT_FOUND", "接口不存在。", 404)
            except ResearchError as exc:
                self.send_json(exc.status, exc.as_dict())
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.send_json(500, {"error": {"code": "INTERNAL_ERROR", "message": "本地服务发生错误，请重试。"}})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"Paper Research Workbench: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
