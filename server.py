import json
import os
import sys
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import random
import time

PORT = int(os.environ.get("PORT", 3000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database.json")

def read_db():
    if not os.path.exists(DB_FILE):
        initial = {
            "students": [],
            "admins": [],
            "notices": [],
            "requests": [],
            "reminders": [],
            "exam": []
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2)
        return initial
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading database.json: {e}")
        return {"students": [], "admins": [], "notices": [], "requests": [], "reminders": [], "exam": []}

def write_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error writing to database.json: {e}")

def generate_id(prefix):
    millis = str(int(time.time() * 1000))[-4:]
    rand = random.randint(10, 99)
    return f"{prefix}-{millis}{rand}"

class CampusEaseHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_body_json(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # API Routes
        if path.startswith("/api/"):
            db = read_db()

            if path == "/api/notices":
                return self._send_json(200, db.get("notices", []))

            if path == "/api/requests":
                who = qs.get("who", [""])[0]
                role = qs.get("role", [""])[0]
                reqs = db.get("requests", [])
                if role != "admin" and who:
                    reqs = [r for r in reqs if r.get("who", "").lower() == who.lower()]
                return self._send_json(200, reqs)

            if path == "/api/reminders":
                who = qs.get("who", [""])[0]
                rems = db.get("reminders", [])
                if who:
                    rems = [r for r in rems if r.get("who", "").lower() == who.lower()]
                return self._send_json(200, rems)

            if path == "/api/exam":
                cat = qs.get("cat", [""])[0]
                exams = db.get("exam", [])
                if cat:
                    exams = [e for e in exams if e.get("cat") == cat]
                return self._send_json(200, exams)

            if path == "/api/contact":
                contact = db.get("contact", {
                    "email": "registrar@campusease.edu",
                    "phone": "+1 (555) 019-2834",
                    "office": "Student Affairs & Registrar Office, Administration Block B, Room 102",
                    "hours": "Monday - Friday, 09:00 - 17:00",
                    "emergency": "Campus Security & Medical: ext 100 / +1 (555) 019-2899"
                })
                return self._send_json(200, contact)

            return self._send_json(404, {"error": "API route not found"})

        # Static files serving (index.html, etc.)
        relative_path = path.lstrip("/")
        if not relative_path:
            relative_path = "index.html"

        file_path = os.path.join(BASE_DIR, relative_path)
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(BASE_DIR, "index.html")

        if os.path.exists(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "text/html; charset=utf-8"
            elif mime_type.startswith("text/") or mime_type == "application/json":
                mime_type += "; charset=utf-8"

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._get_body_json()
        db = read_db()
        today = time.strftime("%Y-%m-%d")

        # Auth Login
        if path == "/api/auth/login":
            user_id = str(body.get("id", "")).strip()
            password = str(body.get("pass", ""))
            role = str(body.get("role", ""))

            if not user_id or not password or not role:
                return self._send_json(400, {"error": "Please provide ID, password, and role."})

            lst = db.get("students" if role == "student" else "admins", [])
            key = "roll" if role == "student" else "emp"

            user = next((u for u in lst if str(u.get(key, "")).strip() == user_id and u.get("pass") == password), None)
            if not user:
                return self._send_json(401, {"error": "Invalid identifier or password. Please verify your credentials."})

            safe_user = {k: v for k, v in user.items() if k != "pass"}
            return self._send_json(200, {"user": safe_user, "role": role})

        # Auth Signup
        if path == "/api/auth/signup":
            role = str(body.get("role", ""))
            user_id = str(body.get("id", "")).strip()
            password = str(body.get("pass", ""))
            name = str(body.get("name", "")).strip()

            if not user_id or not password or not name or not role:
                return self._send_json(400, {"error": "All mandatory fields must be completed."})

            lst = db.get("students" if role == "student" else "admins", [])
            key = "roll" if role == "student" else "emp"

            if any(str(u.get(key, "")).strip() == user_id for u in lst):
                return self._send_json(409, {"error": "An account with that identifier is already registered."})

            if role == "student":
                new_user = {
                    "roll": user_id,
                    "pass": password,
                    "name": name,
                    "branch": body.get("branch", "General"),
                    "hosteller": bool(body.get("hosteller", False)),
                    "room": str(body.get("room", "")).strip() if body.get("hosteller") else ""
                }
            else:
                new_user = {
                    "emp": user_id,
                    "pass": password,
                    "name": name
                }

            lst.append(new_user)
            write_db(db)
            safe_user = {k: v for k, v in new_user.items() if k != "pass"}
            return self._send_json(201, {"user": safe_user, "role": role})

        # Create Notice
        if path == "/api/notices":
            title = str(body.get("title", "")).strip()
            body_text = str(body.get("body", "")).strip()
            if not title or not body_text:
                return self._send_json(400, {"error": "Title and notice content are required."})

            new_notice = {
                "id": generate_id("NT"),
                "title": title,
                "body": body_text,
                "at": today
            }
            db.setdefault("notices", []).insert(0, new_notice)
            write_db(db)
            return self._send_json(201, new_notice)

        # Create Request
        if path == "/api/requests":
            req_type = body.get("type", "")
            who = body.get("who", "")
            f = body.get("f", {})
            if not req_type or not who or not f:
                return self._send_json(400, {"error": "Type, applicant name, and form data required."})

            prefix_map = {"leave": "LV", "gate_pass": "GP", "hostel_complaint": "HC", "fee_query": "FQ"}
            prefix = prefix_map.get(req_type, "RQ")

            new_req = {
                "id": generate_id(prefix),
                "type": req_type,
                "who": who,
                "branch": body.get("branch", "General"),
                "f": f,
                "status": "pending",
                "notes": [],
                "hist": [{"s": "pending", "at": today}]
            }
            db.setdefault("requests", []).insert(0, new_req)
            write_db(db)
            return self._send_json(201, new_req)

        # Add Request Note: /api/requests/:id/notes
        if path.startswith("/api/requests/") and path.endswith("/notes"):
            req_id = path.split("/")[3]
            by = body.get("by", "")
            t = str(body.get("t", "")).strip()
            if not t or not by:
                return self._send_json(400, {"error": "Note text and author required."})

            target = next((r for r in db.get("requests", []) if r.get("id") == req_id), None)
            if not target:
                return self._send_json(404, {"error": "Request not found."})

            new_note = {"by": by, "t": t, "at": today}
            target.setdefault("notes", []).insert(0, new_note)
            write_db(db)
            return self._send_json(201, target)

        # Create Reminder
        if path == "/api/reminders":
            who = body.get("who", "")
            title = str(body.get("title", "")).strip()
            due = str(body.get("due", ""))
            if not who or not title or not due:
                return self._send_json(400, {"error": "Title and due date required."})

            new_rem = {
                "id": generate_id("RM"),
                "who": who,
                "title": title,
                "due": due
            }
            db.setdefault("reminders", []).insert(0, new_rem)
            write_db(db)
            return self._send_json(201, new_rem)

        # Create Exam Publication
        if path == "/api/exam":
            cat = body.get("cat", "")
            branch = str(body.get("branch", "")).strip().upper()
            sem = str(body.get("sem", "")).strip()
            title = str(body.get("title", "")).strip()
            content = str(body.get("content", "")).strip()
            media = str(body.get("media", "")).strip()
            media_name = str(body.get("media_name", "")).strip()
            if not cat or not branch or not sem or not title or not content:
                return self._send_json(400, {"error": "All publication fields required."})

            new_exam = {
                "id": generate_id("EX"),
                "cat": cat,
                "branch": branch,
                "sem": sem,
                "title": title,
                "content": content,
                "media": media,
                "media_name": media_name,
                "at": today
            }
            db.setdefault("exam", []).insert(0, new_exam)
            write_db(db)
            return self._send_json(201, new_exam)

        # Update Contact Details (Admin only)
        if path == "/api/contact":
            contact = {
                "email": str(body.get("email", "")).strip(),
                "phone": str(body.get("phone", "")).strip(),
                "office": str(body.get("office", "")).strip(),
                "hours": str(body.get("hours", "")).strip(),
                "emergency": str(body.get("emergency", "")).strip()
            }
            db["contact"] = contact
            write_db(db)
            return self._send_json(200, contact)

        return self._send_json(404, {"error": "Endpoint not found"})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._get_body_json()
        db = read_db()
        today = time.strftime("%Y-%m-%d")

        # Update Request Status: /api/requests/:id/status
        if path.startswith("/api/requests/") and path.endswith("/status"):
            req_id = path.split("/")[3]
            status = body.get("status")
            if not status:
                return self._send_json(400, {"error": "Status is required."})

            target = next((r for r in db.get("requests", []) if r.get("id") == req_id), None)
            if not target:
                return self._send_json(404, {"error": "Request not found."})

            target["status"] = status
            target.setdefault("hist", []).append({"s": status, "at": today})
            write_db(db)
            return self._send_json(200, target)

        return self._send_json(404, {"error": "Endpoint not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        db = read_db()

        # Delete Notice
        if path.startswith("/api/notices/"):
            notice_id = path.split("/")[3]
            db["notices"] = [n for n in db.get("notices", []) if n.get("id") != notice_id]
            write_db(db)
            return self._send_json(200, {"success": True, "id": notice_id})

        # Delete Single Request: /api/requests/:id
        if path.startswith("/api/requests/"):
            req_id = path.split("/")[3]
            db["requests"] = [r for r in db.get("requests", []) if r.get("id") != req_id]
            write_db(db)
            return self._send_json(200, {"success": True, "id": req_id})

        # Clear All or Filtered Requests: /api/requests
        if path == "/api/requests":
            qs = parse_qs(parsed.query)
            status_filter = qs.get("status", [""])[0]
            if status_filter:
                db["requests"] = [r for r in db.get("requests", []) if r.get("status") != status_filter]
            else:
                db["requests"] = []
            write_db(db)
            return self._send_json(200, {"success": True, "requests": db["requests"]})

        # Delete Reminder
        if path.startswith("/api/reminders/"):
            rem_id = path.split("/")[3]
            db["reminders"] = [r for r in db.get("reminders", []) if r.get("id") != rem_id]
            write_db(db)
            return self._send_json(200, {"success": True, "id": rem_id})

        # Delete Exam
        if path.startswith("/api/exam/"):
            exam_id = path.split("/")[3]
            db["exam"] = [e for e in db.get("exam", []) if e.get("id") != exam_id]
            write_db(db)
            return self._send_json(200, {"success": True, "id": exam_id})

        return self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        # Clean terminal output format
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {format % args}\n")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), CampusEaseHandler)
    print("====================================================")
    print(f"CampusEase Backend Server running on port {PORT}")
    print(f"Web application URL: http://localhost:{PORT}")
    print(f"Database storage:    {DB_FILE}")
    print("====================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down CampusEase backend server.")
        server.server_close()
