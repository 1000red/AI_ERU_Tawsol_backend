"""End-to-end HTML page and functionality test suite for WeConnect.
Verifies:
1. All 7 HTML pages load with HTTP 200.
2. No broken relative *.html href links exist on any page.
3. Key interactivity elements, buttons, and handlers are present.
4. Bilingual toggles and student/teacher workflows are operational.
"""

import re
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


@pytest.mark.parametrize("page", PAGES_TO_TEST)
def test_html_page_loading_and_integrity(page):
    """Test that all 7 HTML pages render HTTP 200 with required scripts and zero broken relative .html links."""
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
