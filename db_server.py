"""Lightweight HTTP API server for the knowledge base database."""

import http.server
import json
import base64
import sqlite3
import os
import re
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "knowledge_base.db"
IMG_DIR = BASE_DIR / "kb_images"
PDF_DIR = BASE_DIR / "pdfs"
UI_DIR = BASE_DIR / "ui"
PORT = 8080

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".pdf": "application/pdf",
}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    if not row:
        return None
    d = dict(row)
    # Parse JSON string fields into actual arrays
    for field in ("links", "case_references", "images"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    # Parse comma-separated fields into arrays
    for field in ("tags", "people_mentioned"):
        if field in d and isinstance(d[field], str):
            d[field] = [t.strip() for t in d[field].split(",") if t.strip()]
        elif field in d and not d[field]:
            d[field] = []
    # Remove search_text from API responses (internal field)
    d.pop("search_text", None)
    # Remove rank if present (FTS internal)
    d.pop("rank", None)
    return d


class KBHandler(http.server.BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            if path == "/api/articles":
                self.handle_create_article(self.read_json_body())
            elif path == "/api/images/upload":
                self.handle_upload_images(self.read_json_body())
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            m = re.match(r"^/api/articles/(\d+)$", path)
            if m:
                self.handle_update_article(int(m.group(1)), self.read_json_body())
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            m = re.match(r"^/api/articles/(\d+)$", path)
            if m:
                self.handle_delete_article(int(m.group(1)))
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/search":
                self.handle_search(qs)
            elif path == "/api/articles":
                self.handle_articles_list(qs)
            elif re.match(r"^/api/articles/(\d+)$", path):
                aid = int(re.match(r"^/api/articles/(\d+)$", path).group(1))
                self.handle_article_detail(aid)
            elif path == "/api/categories":
                self.handle_categories()
            elif path == "/api/tags":
                self.handle_tags()
            elif path.startswith("/api/images/"):
                fname = path[len("/api/images/"):]
                self.handle_image(fname)
            elif path.startswith("/api/pdfs/"):
                fname = urllib.parse.unquote(path[len("/api/pdfs/"):])
                self.handle_pdf(fname)
            else:
                self.handle_static(parsed.path)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_search(self, qs):
        q = qs.get("q", [""])[0].strip()
        category = qs.get("category", [None])[0]
        tag = qs.get("tag", [None])[0]

        conn = get_db()
        if q:
            # FTS search - add prefix matching for partial words
            fts_query = q.replace('"', '""')
            words = fts_query.split()
            if words:
                fts_terms = " ".join(f'"{w}"*' for w in words)
            else:
                fts_terms = f'"{fts_query}"*'
            sql = """
                SELECT a.*, rank FROM articles_fts fts
                JOIN articles a ON a.id = fts.rowid
                WHERE articles_fts MATCH ?
            """
            params = [fts_terms]
            if category:
                sql += " AND a.category = ?"
                params.append(category)
            if tag:
                sql += " AND a.tags LIKE ?"
                params.append(f"%{tag}%")
            sql += " ORDER BY rank LIMIT 50"
        else:
            sql = "SELECT * FROM articles WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if tag:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")
            sql += " ORDER BY id LIMIT 50"

        rows = conn.execute(sql, params).fetchall()
        results = [dict_from_row(r) for r in rows]
        conn.close()
        self.send_json({"results": results, "total": len(results)})

    def handle_articles_list(self, qs):
        page = int(qs.get("page", ["1"])[0])
        limit = int(qs.get("limit", ["20"])[0])
        limit = min(limit, 100)
        offset = (page - 1) * limit

        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY id LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        results = [dict_from_row(r) for r in rows]
        conn.close()
        self.send_json({
            "results": results,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        })

    def handle_article_detail(self, aid):
        conn = get_db()
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (aid,)).fetchone()
        conn.close()
        if row:
            self.send_json(dict_from_row(row))
        else:
            self.send_json({"error": "Not found"}, 404)

    def handle_categories(self):
        conn = get_db()
        rows = conn.execute(
            "SELECT category as name, COUNT(*) as count FROM articles GROUP BY category ORDER BY count DESC"
        ).fetchall()
        conn.close()
        self.send_json({"categories": [dict_from_row(r) for r in rows]})

    def handle_tags(self):
        conn = get_db()
        rows = conn.execute("SELECT tags FROM articles WHERE tags != ''").fetchall()
        conn.close()
        tag_counts = {}
        for row in rows:
            for tag in row["tags"].split(", "):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        result = [{"name": t, "count": c} for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])]
        self.send_json({"tags": result})

    def handle_image(self, fname):
        fpath = IMG_DIR / fname
        if not fpath.exists():
            self.send_json({"error": "Image not found"}, 404)
            return
        ext = fpath.suffix.lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        data = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def handle_pdf(self, fname):
        fpath = PDF_DIR / fname
        if not fpath.exists():
            self.send_json({"error": "PDF not found"}, 404)
            return
        data = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'inline; filename="{fname}"')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def handle_create_article(self, data):
        conn = get_db()
        tags = ", ".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else data.get("tags", "")
        links = json.dumps(data.get("links", []))
        case_refs = json.dumps(data.get("case_references", []))
        images = json.dumps(data.get("images", []))
        people = ", ".join(data.get("people_mentioned", [])) if isinstance(data.get("people_mentioned"), list) else data.get("people_mentioned", "")
        title = data.get("title", "")
        content = data.get("content", "")
        search_text = f"{title} {content} {tags}"
        cursor = conn.execute(
            """INSERT INTO articles (title, content, category, tags, links, case_references,
               images, source_page, created_date, people_mentioned, search_text, source_pdf)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, content, data.get("category", ""), tags, links, case_refs,
             images, data.get("source_page"), data.get("created_date", ""),
             people, search_text, data.get("source_pdf", ""))
        )
        conn.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        conn.commit()
        article_id = cursor.lastrowid
        conn.close()
        self.send_json({"id": article_id, "message": "Article created"}, 201)

    def handle_update_article(self, aid, data):
        conn = get_db()
        if not conn.execute("SELECT id FROM articles WHERE id = ?", (aid,)).fetchone():
            conn.close()
            self.send_json({"error": "Not found"}, 404)
            return
        tags = ", ".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else data.get("tags", "")
        links = json.dumps(data.get("links", []))
        case_refs = json.dumps(data.get("case_references", []))
        images = json.dumps(data.get("images", []))
        people = ", ".join(data.get("people_mentioned", [])) if isinstance(data.get("people_mentioned"), list) else data.get("people_mentioned", "")
        title = data.get("title", "")
        content = data.get("content", "")
        search_text = f"{title} {content} {tags}"
        conn.execute(
            """UPDATE articles SET title=?, content=?, category=?, tags=?, links=?,
               case_references=?, images=?, source_page=?, created_date=?,
               people_mentioned=?, search_text=?, source_pdf=? WHERE id=?""",
            (title, content, data.get("category", ""), tags, links, case_refs,
             images, data.get("source_page"), data.get("created_date", ""),
             people, search_text, data.get("source_pdf", ""), aid)
        )
        conn.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()
        self.send_json({"message": "Article updated"})

    def handle_delete_article(self, aid):
        conn = get_db()
        if not conn.execute("SELECT id FROM articles WHERE id = ?", (aid,)).fetchone():
            conn.close()
            self.send_json({"error": "Not found"}, 404)
            return
        conn.execute("DELETE FROM articles WHERE id = ?", (aid,))
        conn.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()
        self.send_json({"message": "Article deleted"})

    def handle_upload_images(self, data):
        import time as _time
        uploaded = []
        for img in data.get("images", []):
            fname = img.get("filename", "upload.png")
            safe = re.sub(r'[^\w.\-]', '_', fname)
            base, ext = os.path.splitext(safe)
            safe = f"{base}_{int(_time.time() * 1000)}{ext}"
            (IMG_DIR / safe).write_bytes(base64.b64decode(img["data"]))
            uploaded.append(safe)
        self.send_json({"uploaded": uploaded})

    def handle_static(self, request_path):
        if request_path in ("", "/"):
            request_path = "/index.html"
        fpath = UI_DIR / request_path.lstrip("/")
        if not fpath.exists():
            self.send_json({"error": "Not found"}, 404)
            return
        ext = fpath.suffix.lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        data = fpath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    UI_DIR.mkdir(parents=True, exist_ok=True)
    server = http.server.HTTPServer(("0.0.0.0", PORT), KBHandler)
    print(f"Knowledge Base API server running on http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    print(f"Images:   {IMG_DIR}")
    print(f"UI:       {UI_DIR}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
