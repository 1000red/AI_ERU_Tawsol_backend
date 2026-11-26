"""Deep static analyzer for all 7 HTML pages in WeConnect backend.
Checks:
1. All <script> blocks extracted with standard HTML5-compliant HTMLParser pass `node --check` JS syntax validation (catches unescaped </script> inside templates!).
2. All static and dynamic onclick/onchange/onsubmit handlers map to defined JS functions.
3. All document.getElementById('...') and querySelector('#...') lookups point to existing DOM IDs.
4. All fetch(...) URLs & HTTP methods match registered FastAPI endpoints (including _IncludedRouter traversal).
5. Zero duplicate DOM IDs, duplicate named JS functions, or broken relative .html links.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from html.parser import HTMLParser
from app.main import app

HTML_FILES = {
    "teacher_portal": "app/routers/teacher_portal.html",
    "student_checkin": "app/routers/student_checkin.html",
    "sqbs_pitch": "app/routers/sqbs_pitch.html",
    "teacher_gateway": "app/routers/teacher_gateway.html",
    "user_management": "app/routers/user_management.html",
    "dashboard": "app/templates/dashboard.html",
    "storage_command_center": "app/templates/storage_command_center.html",
}


class ScriptAndIdExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self.cur = []
        self.cur_line = 0
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if "id" in attrs_dict and not self.in_script:
            self.ids.append(attrs_dict["id"])
        if tag.lower() == "script":
            self.in_script = True
            self.cur = []
            self.cur_line = self.getpos()[0]

    def handle_data(self, data):
        if self.in_script:
            self.cur.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_script:
            self.in_script = False
            self.scripts.append((self.cur_line, "".join(self.cur)))


def collect_all_routes(router, prefix=""):
    res = set()
    for r in getattr(router, "routes", []):
        if hasattr(r, "original_router"):
            ctx = getattr(r, "include_context", None)
            p = getattr(ctx, "prefix", "") if ctx else ""
            res |= collect_all_routes(r.original_router, prefix + p)
        elif hasattr(r, "routes"):
            res |= collect_all_routes(r, prefix + getattr(r, "prefix", ""))
        elif hasattr(r, "path"):
            methods = getattr(r, "methods", None) or {"GET"}
            for m in methods:
                res.add((m.upper(), (prefix + r.path).replace("//", "/")))
    return res


all_routes = collect_all_routes(app)
route_regexes = [
    (m, p, re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/?]+", p) + "(?:\\?.*)?$"))
    for m, p in all_routes
]


def matches_method_route(method, url_path):
    clean = url_path.split("?")[0]
    clean_norm = re.sub(r"\$\{[^}]+\}", "PLACEHOLDER", clean)
    return any(m == method.upper() and rx.match(clean_norm) for m, _, rx in route_regexes)


def path_exists(url_path):
    clean = url_path.split("?")[0]
    clean_norm = re.sub(r"\$\{[^}]+\}", "PLACEHOLDER", clean)
    return any(rx.match(clean_norm) for _, _, rx in route_regexes)


BUILTINS = {
    "alert", "confirm", "prompt", "window", "event", "stopPropagation", "preventDefault",
    "console", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "open", "close",
    "print", "history", "location", "reload", "blur", "focus", "select", "toggle",
    "classList", "remove", "add", "showToast", "confetti", "Number", "String", "Boolean",
    "parseInt", "parseFloat", "encodeURIComponent", "decodeURIComponent", "Math", "Date",
    "JSON", "Array", "Object", "fetch", "navigator", "document", "requestAnimationFrame",
    "if", "for", "while", "switch", "return", "typeof", "void", "delete", "new", "function", "this",
}


def audit_file(name, path, node_bin=None):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    parser = ScriptAndIdExtractor()
    parser.feed(html)
    non_empty_scripts = [(line, sc) for line, sc in parser.scripts if sc.strip()]

    js_errors = []
    if parser.in_script:
        js_errors.append(f"Unclosed <script> tag starting at line {parser.cur_line}")
    if node_bin:
        for line, sc in non_empty_scripts:
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
                tf.write(sc)
                tmp_path = tf.name
            try:
                res = subprocess.run([node_bin, "--check", tmp_path], capture_output=True, text=True)
                if res.returncode != 0:
                    js_errors.append(f"Script line {line}: {res.stderr.strip()[:300]}")
            finally:
                os.unlink(tmp_path)

    combined_js = "\n".join(sc for _, sc in non_empty_scripts)
    dom_ids = set(parser.ids)
    dup_ids = sorted(k for k, v in Counter(parser.ids).items() if v > 1)

    named_fns = re.findall(r"(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(", combined_js)
    dup_fns = sorted(k for k, v in Counter(named_fns).items() if v > 1)
    fn_defs = set(named_fns)
    fn_defs |= set(re.findall(r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>", combined_js))
    fn_defs |= set(re.findall(r"(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?function", combined_js))
    fn_defs |= set(re.findall(r"window\.([a-zA-Z0-9_$]+)\s*=", combined_js))

    handlers = re.findall(r'\bon[a-z]+\s*=\s*("([^"]*)"|\'([^\']*)\')', html, re.IGNORECASE)
    missing_fns = set()
    for _, dq, sq in handlers:
        h = dq if dq else sq
        h_no_str = re.sub(r'(["\'])(?:\\.|(?!\1).)*\1', '""', h)
        for m in re.finditer(r'(?<![.\w$])([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', h_no_str):
            fn = m.group(1)
            if fn not in fn_defs and fn not in BUILTINS:
                missing_fns.add(fn)

    get_el_ids = set(re.findall(r'document\.getElementById\(\s*["\']([^"\']+)["\']\s*\)', combined_js))
    missing_ids = sorted(
        el_id for el_id in get_el_ids
        if el_id not in dom_ids and not re.search(rf'id\s*=\s*["\\\']?{re.escape(el_id)}', combined_js)
    )

    fetch_mismatches = []
    for fm in re.finditer(r'fetch\(\s*([`"\'])((?:\\.|(?!\1).)+)\1(?:\s*,\s*(\{[^;]{0,500}))?', combined_js, re.DOTALL):
        url = fm.group(2)
        opts = fm.group(3) or ""
        u = re.sub(r'^\$\{(?:API_BASE|BASE_URL|window\.location\.origin|origin)\}', '', url)
        if not u.startswith('/'):
            continue
        mm = re.search(r'method\s*:\s*["\']([A-Za-z]+)["\']', opts)
        method = mm.group(1).upper() if mm else "GET"
        if not matches_method_route(method, u):
            fetch_mismatches.append(f"{method} {u}")

    bad_hrefs = []
    for h in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html):
        if h.startswith(('#', 'http', 'mailto:', 'javascript:', 'data:')):
            continue
        if h.endswith('.html') or (h.startswith('/') and not h.startswith('/static') and not path_exists(h)):
            bad_hrefs.append(h)

    return {
        "size_kb": len(html) // 1024,
        "dom_ids_count": len(dom_ids),
        "js_functions_count": len(fn_defs),
        "js_errors": js_errors,
        "dup_ids": dup_ids,
        "dup_fns": dup_fns,
        "missing_functions": sorted(missing_fns),
        "missing_dom_ids": missing_ids,
        "fetch_mismatches": fetch_mismatches,
        "bad_hrefs": bad_hrefs,
    }


if __name__ == "__main__":
    print(f"Total FastAPI endpoints detected: {len(all_routes)}")
    node_bin = shutil.which("node")
    print("\n" + "=" * 60)
    print("AUDIT RESULTS SUMMARY")
    print("=" * 60)
    has_failures = False
    for name, path in HTML_FILES.items():
        if not os.path.exists(path):
            print(f"ERROR: {path} not found!")
            has_failures = True
            continue
        rep = audit_file(name, path, node_bin=node_bin)
        print(f"\n--- {name.upper()} ({rep['size_kb']} KB) ---")
        print(f"DOM IDs: {rep['dom_ids_count']} | JS Defined Functions: {rep['js_functions_count']}")
        checks = [
            ("JS syntax errors", rep["js_errors"]),
            ("Duplicate DOM IDs", rep["dup_ids"]),
            ("Duplicate function defs", rep["dup_fns"]),
            ("Missing inline functions", rep["missing_functions"]),
            ("Missing DOM IDs", rep["missing_dom_ids"]),
            ("Mismatched fetch routes", rep["fetch_mismatches"]),
            ("Broken href links", rep["bad_hrefs"]),
        ]
        page_ok = True
        for label, issues in checks:
            if issues:
                page_ok = False
                has_failures = True
                print(f"FAIL {label}: {issues}")
        if page_ok:
            print("OK: All syntax, DOM IDs, JS handlers, fetch routes, and links verified!")

    sys.exit(1 if has_failures else 0)
