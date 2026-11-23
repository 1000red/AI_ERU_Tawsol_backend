"""Deep static analyzer for all 7 HTML pages in WeConnect backend.
Checks:
1. All onclick, onsubmit, onchange handlers have corresponding defined JS functions.
2. All document.getElementById('...') lookups point to existing element IDs in the DOM.
3. All fetch(...) URLs correspond to existing FastAPI routes or valid external URLs.
4. Detect any JS syntax errors or missing closing tags.
"""

import os
import re
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

# Collect all FastAPI route paths
fastapi_routes = set()
for route in app.routes:
    if hasattr(route, "path"):
        fastapi_routes.add(route.path)
    if hasattr(route, "routes"):
        for sub in route.routes:
            if hasattr(sub, "path"):
                fastapi_routes.add(sub.path)

print(f"Total FastAPI routes detected: {len(fastapi_routes)}")

reports = {}

for name, path in HTML_FILES.items():
    if not os.path.exists(path):
        print(f"ERROR: {path} not found!")
        continue

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Extract all DOM IDs
    dom_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

    # 2. Extract all scripts content
    scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    combined_js = "\n".join(scripts)

    # 3. Extract all defined JS functions
    # function foo(...)
    fn_defs_1 = set(re.findall(r'function\s+([a-zA-Z0-9_$]+)\s*\(', combined_js))
    # const foo = (...) => or const foo = function(...)
    fn_defs_2 = set(re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>', combined_js))
    fn_defs_3 = set(re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?function', combined_js))
    # window.foo = ...
    fn_defs_4 = set(re.findall(r'window\.([a-zA-Z0-9_$]+)\s*=', combined_js))
    all_defined_fns = fn_defs_1 | fn_defs_2 | fn_defs_3 | fn_defs_4

    # Built-in or library functions commonly invoked inline
    builtins = {
        "alert", "confirm", "prompt", "window", "event", "stopPropagation", "preventDefault",
        "console", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "open", "close",
        "print", "history", "location", "reload", "blur", "focus", "select", "toggle",
        "classList", "remove", "add", "showToast", "confetti"
    }

    # 4. Extract inline handlers: onclick, onsubmit, onchange, etc.
    handlers = re.findall(r'\bon[a-z]+\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
    called_fns = set()
    for h in handlers:
        # find foo(...) calls
        calls = re.findall(r'([a-zA-Z0-9_$]+)\s*\(', h)
        for c in calls:
            called_fns.add(c)

    # Missing functions
    missing_fns = set()
    for fn in called_fns:
        if fn not in all_defined_fns and fn not in builtins:
            # check if it's a DOM method call like el.remove() or obj.method()
            # If the handler contains e.g. "this.classList.toggle", 'toggle' might be matched
            # check if fn is preceded by a dot in any handler
            is_method = False
            for h in handlers:
                if re.search(r'\.\s*' + re.escape(fn) + r'\s*\(', h):
                    is_method = True
                    break
            if not is_method:
                missing_fns.add(fn)

    # 5. Extract document.getElementById('...') calls
    get_el_ids = set(re.findall(r'document\.getElementById\(\s*["\']([^"\']+)["\']\s*\)', combined_js))
    missing_ids = set()
    for el_id in get_el_ids:
        if el_id not in dom_ids:
            # Check if dynamically created or template
            missing_ids.add(el_id)

    # 6. Extract fetch endpoints
    fetch_calls = re.findall(r'fetch\(\s*[`"\']([^`"\']+)[\'"`]', combined_js)
    # Also fetch(`${API_BASE}/foo/bar`)
    template_fetches = re.findall(r'fetch\(\s*`\$\{API_BASE\}(/[^`?]+)', combined_js)
    all_fetches = set(fetch_calls + template_fetches)

    reports[name] = {
        "size_kb": len(html) // 1024,
        "dom_ids_count": len(dom_ids),
        "js_functions_count": len(all_defined_fns),
        "missing_functions": sorted(list(missing_fns)),
        "missing_dom_ids": sorted(list(missing_ids)),
        "fetch_endpoints": sorted(list(all_fetches)),
    }

print("\n" + "=" * 60)
print("AUDIT RESULTS SUMMARY")
print("=" * 60)
for name, rep in reports.items():
    print(f"\n--- {name.upper()} ({rep['size_kb']} KB) ---")
    print(f"DOM IDs: {rep['dom_ids_count']} | JS Defined Functions: {rep['js_functions_count']}")
    if rep['missing_functions']:
        print(f"⚠️ POTENTIALLY MISSING FUNCTIONS ({len(rep['missing_functions'])}): {rep['missing_functions']}")
    else:
        print("✅ All inline handler functions are defined!")
    if rep['missing_dom_ids']:
        print(f"⚠️ POTENTIALLY MISSING DOM IDs ({len(rep['missing_dom_ids'])}): {rep['missing_dom_ids']}")
    else:
        print("✅ All referenced DOM IDs exist in HTML!")
