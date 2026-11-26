"""End-to-end HTML page and functionality test suite for WeConnect.
Verifies:
1. All 7 HTML pages load with HTTP 200.
2. No broken relative *.html href links exist on any page.
3. All inline <script> blocks parse cleanly via HTMLParser (catches unescaped </script>) and pass `node --check`.
4. All static inline handlers, DOM IDs, fetch routes/methods, and navigation links are valid.
5. Key interactivity elements, buttons, and handlers are present.
"""

import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

PAGES_TO_TEST = [
    {
        "url": "/teacher",
        "expected_title": "بوابة المعلمين والمهندسين",
        "required_strings": ["live-subtitle-bar", "credentials-drawer", "/gateway", "/checkin", "/pitch"],
    },
    {
        "url": "/checkin",
        "expected_title": "تسجيل الحضور الذكي للطلاب",
        "required_strings": ["tab-btn-checkin", "tab-btn-summary", "tab-btn-exam", "gauge-circle-progress"],
    },
    {
        "url": "/pitch",
        "expected_title": "WeConnect | عرض مسابقة HP IDEA Egypt",
        "required_strings": ["openPitchVideo", "modal-video-backup", "backup-video-el", "1080p"],
    },
    {
        "url": "/gateway",
        "expected_title": "بوابة المعلم التفاعلية",
        "required_strings": ["/api/v1/games", "sel-course-id"],
    },
    {
        "url": "/users",
        "expected_title": "لوحة التحكم والمراقبة المركزية",
        "required_strings": ["admin-honor-roll-table-body", "filterAdminHonorRoll", "printAdminHonorRollCharter", "/teacher", "/checkin", "/pitch"],
    },
    {
        "url": "/dashboard",
        "expected_title": "لوحة تحكم إدارة النظام",
        "required_strings": ["API_BASE"],
    },
    {
        "url": "/storage",
        "expected_title": "مركز قيادة التخزين السحابي",
        "required_strings": ["API_BASE"],
    },
]


class _ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self.cur = []
        self.cur_line = 0

    def handle_starttag(self, tag, attrs):
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


@pytest.mark.parametrize("page", PAGES_TO_TEST)
def test_html_page_loading_and_integrity(page):
    """Test that all 7 HTML pages render HTTP 200 with valid JS syntax, required UI hooks, and zero broken links."""
    res = client.get(page["url"])
    assert res.status_code == 200, f"Page {page['url']} failed with status {res.status_code}"
    html = res.text
    assert len(html) > 5000, f"Page {page['url']} returned suspiciously short HTML ({len(html)} bytes)"

    # Check title
    assert page["expected_title"] in html, f"Page {page['url']} missing expected title '{page['expected_title']}'"

    # Check required strings / elements
    for req in page["required_strings"]:
        assert req in html, f"Page {page['url']} missing required element/script: {req}"

    # Strict check: Zero unhandled relative .html links
    broken_links = re.findall(r'href=["\']([a-zA-Z0-9_\-]+\.html)["\']', html)
    assert len(broken_links) == 0, f"Page {page['url']} contains broken relative .html links: {broken_links}"

    # Parse <script> blocks cleanly via HTMLParser (detects unescaped </script> inside JS template literals)
    parser = _ScriptParser()
    parser.feed(html)
    assert not parser.in_script, f"Page {page['url']} has unclosed <script> tag starting at line {parser.cur_line}"

    node_bin = shutil.which("node")
    if node_bin:
        for line, code in parser.scripts:
            if not code.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
                tf.write(code)
                tmp_path = tf.name
            try:
                chk = subprocess.run([node_bin, "--check", tmp_path], capture_output=True, text=True)
                assert chk.returncode == 0, (
                    f"Page {page['url']} <script> at line {line} failed JS syntax check:\n{chk.stderr}"
                )
            finally:
                os.unlink(tmp_path)


def test_audit_html_pages_zero_issues():
    """Run static analyzer across all 7 HTML files and assert zero missing handlers, DOM IDs, or broken fetches."""
    from audit_html_pages import HTML_FILES, audit_file

    node_bin = shutil.which("node")
    for name, path in HTML_FILES.items():
        rep = audit_file(name, path, node_bin=node_bin)
        assert not rep["js_errors"], f"{name} JS errors: {rep['js_errors']}"
        assert not rep["dup_ids"], f"{name} duplicate DOM IDs: {rep['dup_ids']}"
        assert not rep["dup_fns"], f"{name} duplicate function defs: {rep['dup_fns']}"
        assert not rep["missing_functions"], f"{name} missing functions: {rep['missing_functions']}"
        assert not rep["missing_dom_ids"], f"{name} missing DOM IDs: {rep['missing_dom_ids']}"
        assert not rep["fetch_mismatches"], f"{name} fetch mismatches: {rep['fetch_mismatches']}"
        assert not rep["bad_hrefs"], f"{name} bad hrefs: {rep['bad_hrefs']}"


def test_public_attendance_summary_no_500():
    """Verify /attendance/public-summary/{ident} uses valid User columns (uni_code/name) and never raises 500."""
    res = client.get("/attendance/public-summary/STU-101")
    assert res.status_code in (200, 404), f"Expected 200 or 404, got {res.status_code}: {res.text}"
    if res.status_code == 200:
        assert isinstance(res.json(), list)

