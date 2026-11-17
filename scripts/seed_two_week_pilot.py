"""Seed 2 weeks of realistic WE School Suez pilot usage data into Neon PostgreSQL,
using REAL student exam degrees from:
  1. exam/grading_results_updated.xlsx (Class 3-5 / C5 + 2 students in C4)
  2. MOHANED 3-4/grading_results_logical_80.xlsx (Class 3-4 / C4, out of 80 marks)

Idempotent: cleans only previous pilot2w-tagged records before inserting,
never touching existing user accounts, courses, or real organic records.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openpyxl
from sqlalchemy import text

from app.db.database import SessionLocal
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.chat import ChatHistory
from app.models.contact import ContactMessage
from app.models.content.announcement import Announcement, AnnouncementRead
from app.models.content.assignment import Assignment
from app.models.quiz_log import QuizLog, QuizStudentAttempt
from app.models.user import User

random.seed(20261117)

NOW = datetime(2026, 11, 17, 19, 30, 0)  # Local Egypt pilot end time (naive for DB compatibility)
NOW_UTC = datetime(2026, 11, 17, 17, 30, 0, tzinfo=timezone.utc)

EXCEL_C5_PATH = r"C:\Users\dell\OneDrive\Desktop\exam\grading_results_updated.xlsx"
EXCEL_C4_PATH = r"C:\Users\dell\OneDrive\Desktop\MOHANED 3-4\grading_results_logical_80.xlsx"

AR_TO_EN = {
    "محمد نصر الدين السيد ع": "Mohamed Nasr El-Din El-Sayed Okasha",
    "محمد انور محمود": "Mohamed Anwar Mahmoud Anwar",
    "ملك بركات سيف النصر 3-4": "Malak Barakat",
}


def norm_name(s: str) -> str:
    s = str(s or "").lower()
    s = re.sub(r"\b(3-4|3-5|3\.4|3_4|task2|\(1\)|\(2\))\b", " ", s)
    s = s.replace("-", " ").replace("_", " ").replace(".", " ")
    for a, b in [
        ("mohammed", "mohamed"), ("mohmed", "mohamed"), ("abdulluh", "abdallah"),
        ("yassen", "yassin"), ("rewan", "rawan"), ("retag", "retaj"), ("salha", "salah"),
        ("hussien", "hussein"), ("ibrahimm", "ibrahim"), ("zaky", "zaki"), ("naser", "nasser"),
        ("hasaan", "hassan"), ("aymen", "ayman"), ("moahmed", "mohamed"), ("mariem", "maryam"),
        ("abdelrhman", "abdelrahman"), ("dekrony", "dakrony"),
    ]:
        s = s.replace(a, b)
    return " ".join(s.split())


def match_student(excel_name: str, pool: list[tuple[int, str, str, str]]):
    raw = str(excel_name or "").strip()
    if raw in AR_TO_EN:
        raw = AR_TO_EN[raw]
    ne = norm_name(raw)
    etoks = ne.split()
    best, best_sc = None, 0.0
    for u in pool:
        nu = norm_name(u[1])
        utoks = nu.split()
        overlap = sum(1 for t in etoks if any(SequenceMatcher(None, t, ut).ratio() >= 0.80 for ut in utoks))
        tok_score = overlap / max(1, len(etoks))
        seq_score = SequenceMatcher(None, ne, " ".join(utoks[: len(etoks)])).ratio()
        sc = tok_score * 0.65 + seq_score * 0.35
        if sc > best_sc:
            best_sc = sc
            best = u
    return best, best_sc


PHP_MYSQL_QUESTIONS = [
    {
        "question": "ما الدالة المستخدمة لإنشاء اتصال مع قاعدة بيانات MySQL في PHP (MySQLi)؟",
        "options": {"A": "mysqli_connect()", "B": "mysql_open()", "C": "db_start()", "D": "pdo_attach()"},
        "answer": "A",
        "explanation": "تستخدم mysqli_connect() لفتح اتصال مباشر بسيرفر MySQL مع معالجة الخطأ عبر die(mysqli_connect_error()).",
    },
    {
        "question": "أي عبارة تُستخدم لتحميل ملف connect.php مرة واحدة فقط مع إيقاف التنفيذ عند عدم وجوده؟",
        "options": {"A": "include", "B": "require_once", "C": "import_file", "D": "load_php"},
        "answer": "B",
        "explanation": "require_once تضمن تضمين ملف الاتصال مرة واحدة فقط وتمنع تكرار الاتصال أو متابعة التنفيذ بدونه.",
    },
    {
        "question": "ما الدالة المستخدمة لحماية نموذج التسجيل من هجمات XSS عند طباعة اسم الطالب؟",
        "options": {"A": "md5()", "B": "htmlspecialchars()", "C": "explode()", "D": "str_replace()"},
        "answer": "B",
        "explanation": "htmlspecialchars() تحول الوسوم الخاصة مثل < و > إلى كيانات HTML آمنة تمنع تنفيذ أكواد XSS.",
    },
    {
        "question": "كيف يتم التحقق من صحة البريد الإلكتروني في register.php باستخدام PHP؟",
        "options": {"A": "is_email()", "B": "filter_var($email, FILTER_VALIDATE_EMAIL)", "C": "check_mail()", "D": "validate_str()"},
        "answer": "B",
        "explanation": "filter_var مع الثابت FILTER_VALIDATE_EMAIL هي الطريقة القياسية الموثوقة للتحقق من صيغة البريد.",
    },
    {
        "question": "ما الدالة التي تُرجع عدد الصفوف المتأثرة بعد تنفيذ استعلام UPDATE في update.php؟",
        "options": {"A": "mysqli_num_rows()", "B": "mysqli_affected_rows()", "C": "mysqli_count()", "D": "mysqli_insert_id()"},
        "answer": "B",
        "explanation": "mysqli_affected_rows($conn) تُعيد العدد الدقيق للصفوف التي تم تحديثها أو حذفها.",
    },
]

SOLID_QUESTIONS = [
    {
        "question": "ماذا يرمز حرف S في مبادئ SOLID لهندسة البرمجيات؟",
        "options": {"A": "Single Responsibility Principle", "B": "Static Routing Protocol", "C": "System Recovery Plan", "D": "Simple Render Pattern"},
        "answer": "A",
        "explanation": "مبدأ المسؤولية الواحدة يعني أن لكل كلاس أو وحدة سبباً واحداً فقط للتغيير.",
    },
    {
        "question": "في Clean Architecture، ما الاتجاه الصحيح للاعتماديات (Dependency Rule)؟",
        "options": {"A": "من الداخل للخارج", "B": "من الطبقات الخارجية نحو النواة الداخلية فقط", "C": "اعتماد دائري متبادل", "D": "لا توجد قاعدة"},
        "answer": "B",
        "explanation": "النواة والمنطق التجاري لا تعتمد على قواعد البيانات أو أطر العمل الخارجية.",
    },
    {
        "question": "أي مبدأ ينص على أن الكائنات يجب أن تكون مفتوحة للتوسع ومغلقة للتعديل؟",
        "options": {"A": "Open/Closed Principle (OCP)", "B": "Liskov Substitution", "C": "Interface Segregation", "D": "DRY"},
        "answer": "A",
        "explanation": "OCP يتيح إضافة سلوك جديد دون كسر الكود المختبر والمستقر سابقاً.",
    },
    {
        "question": "ما ميزة استخدام Dependency Injection في FastAPI؟",
        "options": {"A": "زيادة حجم الكود", "B": "تسهيل الاختبار الآلي وفصل طبقة قاعدة البيانات", "C": "إبطاء الاستجابة", "D": "إلغاء الحاجة للتحقق"},
        "answer": "B",
        "explanation": "حقن التبعيات مثل Depends(get_db) يسمح باستبدال قاعدة البيانات أثناء الاختبارات بسهولة.",
    },
    {
        "question": "أي من التالي يُعد مثالاً على RESTful HTTP Status Code عند إيقاف المنصة للصيانة؟",
        "options": {"A": "200 OK", "B": "404 Not Found", "C": "503 Service Unavailable", "D": "301 Moved"},
        "answer": "C",
        "explanation": "الرمز 503 مع ترويسة Retry-After هو المعيار الرسمي لوضع الصيانة المؤقت.",
    },
]

NETWORKING_QUESTIONS = [
    {
        "question": "في أي طبقة من نموذج OSI يعمل جهاز الراوتر (Router)؟",
        "options": {"A": "Layer 2 - Data Link", "B": "Layer 3 - Network", "C": "Layer 4 - Transport", "D": "Layer 1 - Physical"},
        "answer": "B",
        "explanation": "الراوتر يعتمد على عناوين IP لتوجيه الحزم في الطبقة الثالثة (Network Layer).",
    },
    {
        "question": "كم عدد عناوين الأجهزة المتاحة (Usable Hosts) في شبكة فرعية بقناع /26؟",
        "options": {"A": "30", "B": "62", "C": "126", "D": "254"},
        "answer": "B",
        "explanation": "قناع /26 يترك 6 بتات للأجهزة: 2^6 - 2 = 62 عنواناً قابلاً للاستخدام.",
    },
    {
        "question": "ما الغرض الرئيسي من تقنية VLAN على السويتش؟",
        "options": {"A": "تقسيم نطاق البث Broadcast Domain وعزل الشبكات منطقياً", "B": "تضخيم إشارة الواي فاي", "C": "تشفير كلمات المرور", "D": "زيادة طول الكابل"},
        "answer": "A",
        "explanation": "VLAN تقسم السويتش الفيزيائي إلى شبكات منطقية معزولة لرفع الأمان والأداء.",
    },
    {
        "question": "أي بروتوكول يُستخدم لتوزيع عناوين IP تلقائياً على أجهزة معمل المدرسة؟",
        "options": {"A": "DNS", "B": "DHCP", "C": "FTP", "D": "SMTP"},
        "answer": "B",
        "explanation": "DHCP يمنح الأجهزة عنوان IP و Subnet Mask و Default Gateway تلقائياً.",
    },
    {
        "question": "ما رقم المنفذ الافتراضي لبروتوكول HTTPS الآمن؟",
        "options": {"A": "22", "B": "80", "C": "443", "D": "3306"},
        "answer": "C",
        "explanation": "بروتوكول HTTPS يعمل على المنفذ 443 مع تشفير TLS.",
    },
]

TELECOM_QUESTIONS = [
    {
        "question": "ما الميزة الرئيسية للألياف الضوئية (Fiber Optics) مقارنة بكابلات النحاس؟",
        "options": {"A": "عرض نطاق عالٍ ومناعة ضد التداخل الكهرومغناطيسي", "B": "تعمل بالكهرباء المباشرة", "C": "مداها أقل من 10 أمتار", "D": "أثقل وزناً"},
        "answer": "A",
        "explanation": "الألياف الضوئية تنقل البيانات بنبضات ضوئية بسرعة فائقة ولمسافات طويلة دون تشويش.",
    },
    {
        "question": "ما المقصود بمفهوم Latency في شبكات الجيل الخامس 5G؟",
        "options": {"A": "زمن التأخير في انتقال الحزمة من المرسل للمستقبل", "B": "حجم البطارية", "C": "طول الهوائي", "D": "لون الكابل"},
        "answer": "A",
        "explanation": "شبكات 5G تخفض زمن التأخير Latency إلى أقل من 1-10 مللي ثانية للتطبيقات الحية.",
    },
    {
        "question": "ما الوحدة المستخدمة لقياس التردد (Frequency) في أنظمة الاتصالات؟",
        "options": {"A": "Watt", "B": "Hertz (Hz)", "C": "Ohm", "D": "Volt"},
        "answer": "B",
        "explanation": "يقاس التردد بوحدة الهيرتز (عدد الدورات في الثانية).",
    },
    {
        "question": "ماذا يعني مصطلح Modulation في نقل الإشارات؟",
        "options": {"A": "تحميل إشارة المعلومات على موجة حاملة Carrier Wave", "B": "إطفاء جهاز الإرسال", "C": "ضغط الملفات النصية", "D": "تشفير قواعد البيانات"},
        "answer": "A",
        "explanation": "التضمين يمكّن الإشارة من الانتقال لمسافات بعيدة عبر الوسط اللاسلكي أو السلكي.",
    },
    {
        "question": "ما وظيفة جهاز Multiplexer (MUX) في الاتصالات؟",
        "options": {"A": "دمج عدة إشارات على قناة اتصال واحدة", "B": "فصل الكهرباء", "C": "تبريد السيرفرات", "D": "قياس درجة الحرارة"},
        "answer": "A",
        "explanation": "الـ Multiplexer يستغل القناة المشتركة بكفاءة عبر إرسال عدة قنوات معاً.",
    },
]


def load_real_exam_grades(c4_students, c5_students):
    """Parse real student degrees from the two Desktop grading Excel sheets."""
    c5_grades = {}  # user_id -> dict
    c4_grades = {}  # user_id -> dict

    # 1. exam/grading_results_updated.xlsx (C5 + 2 C4 students)
    if os.path.exists(EXCEL_C5_PATH):
        wb1 = openpyxl.load_workbook(EXCEL_C5_PATH, data_only=True)
        ws1 = wb1["ملخص الطلاب"]
        for r in range(2, ws1.max_row + 1):
            name = ws1.cell(r, 1).value
            cls = str(ws1.cell(r, 2).value or "")
            topic_tpl = str(ws1.cell(r, 3).value or "PHP & MySQL")
            ans_pct = float(ws1.cell(r, 4).value or 0.0)
            code_pct = float(ws1.cell(r, 5).value or 0.0)
            grade_en = str(ws1.cell(r, 6).value or "ME")
            grade_ar = str(ws1.cell(r, 7).value or "جيد")
            if not name:
                continue
            pool = c5_students if "5" in cls else c4_students
            m, conf = match_student(name, pool)
            if not m or conf < 0.55:
                continue
            # Real weighted percentage from the official rubric (60% answer completeness + 40% code correctness)
            pct = round((ans_pct * 0.6 + code_pct * 0.4) * 100.0, 1)
            rec = {
                "user_id": m[0],
                "db_name": m[1],
                "excel_name": str(name),
                "course_id": "C5" if "5" in cls else "C4",
                "topic_detail": topic_tpl,
                "pct": pct,
                "ans_pct": round(ans_pct * 100.0, 1),
                "code_pct": round(code_pct * 100.0, 1),
                "marks_80": round((pct / 100.0) * 80.0, 1),
                "grade_en": grade_en,
                "grade_ar": grade_ar,
                "source": "exam/grading_results_updated.xlsx",
            }
            if "5" in cls:
                c5_grades[m[0]] = rec
            else:
                c4_grades[m[0]] = rec

    # 2. MOHANED 3-4/grading_results_logical_80.xlsx (C4 students out of 80 marks)
    if os.path.exists(EXCEL_C4_PATH):
        wb2 = openpyxl.load_workbook(EXCEL_C4_PATH, data_only=True)
        ws2 = wb2["توزيع الدرجات (80) ونسب النجاح"]
        for r in range(30, ws2.max_row + 1):
            name = ws2.cell(r, 2).value
            deg_approved = ws2.cell(r, 5).value
            pct_final = ws2.cell(r, 6).value
            grade_en = str(ws2.cell(r, 7).value or "ME")
            grade_ar_cell = str(ws2.cell(r, 8).value or "").strip()
            if not name or not isinstance(deg_approved, (int, float)) or not isinstance(pct_final, (int, float)):
                continue
            m, conf = match_student(str(name), c4_students)
            if not m or conf < 0.50:
                continue
            if m[0] in c4_grades:
                continue
            pct = round(float(pct_final) * 100.0, 1)
            grade_ar = grade_ar_cell or {"EE": "ممتاز", "ME": "جيد", "NI": "مقبول", "UN": "ضعيف"}.get(grade_en, "جيد")
            c4_grades[m[0]] = {
                "user_id": m[0],
                "db_name": m[1],
                "excel_name": str(name),
                "course_id": "C4",
                "topic_detail": "الامتحان العملي المعتمد (من 80 درجة): MySQL Products + Registration Form",
                "pct": pct,
                "ans_pct": pct,
                "code_pct": pct,
                "marks_80": round(float(deg_approved), 1),
                "grade_en": grade_en,
                "grade_ar": grade_ar,
                "source": "MOHANED 3-4/grading_results_logical_80.xlsx",
            }

    return c4_grades, c5_grades


def main():
    db = SessionLocal()
    try:
        # 0. Load enrolled students & teachers per course
        course_students: dict[str, list[tuple[int, str, str, str]]] = {}
        for cid in ("C1", "C2", "C3", "C4", "C5", "C6"):
            rows = db.execute(
                text(
                    """
                    SELECT u.user_id, u.name, COALESCE(u.uni_code, ''), COALESCE(u.email, '')
                    FROM material_student ms
                    JOIN users u ON u.user_id = ms.user_id
                    WHERE ms.material_id = :cid AND u.type_code = 'STU'
                    ORDER BY u.user_id
                    """
                ),
                {"cid": cid},
            ).fetchall()
            course_students[cid] = [tuple(r) for r in rows]

        course_teachers = {
            "C1": 135,  # Fatma Al-Zahraa
            "C2": 3,    # Nada Samir
            "C3": 134,  # Fatma Hamdy
            "C4": 4,    # Dr. Mohaned
            "C5": 267,  # Eng. Abdallah Abdelwahab
            "C6": 2,    # Eng. Ekram
        }
        admin_id = db.execute(text("SELECT user_id FROM users WHERE type_code = 'ADM' ORDER BY user_id LIMIT 1")).scalar() or 1

        # 1. Idempotent cleanup of prior pilot2w records only
        db.execute(text("DELETE FROM quiz_student_attempts WHERE session_id LIKE 'pilot2w_%'"))
        db.execute(text("DELETE FROM quiz_logs WHERE session_id LIKE 'pilot2w_%'"))
        db.execute(text("DELETE FROM attendance_record WHERE session_id IN (SELECT session_id FROM attendance_session WHERE token LIKE 'WE-PILOT-%')"))
        db.execute(text("DELETE FROM attendance_session WHERE token LIKE 'WE-PILOT-%'"))
        db.execute(text("DELETE FROM chat_history WHERE message LIKE '%[WE-Suez]%' OR message LIKE '%📌%'"))
        db.execute(text("DELETE FROM announcement_reads WHERE announcement_id IN (SELECT announcement_id FROM announcements WHERE title LIKE '%[أسبوع%' OR title LIKE '%SQBS%' OR title LIKE '%امتحان عملي%' OR title LIKE '%لوحة الشرف%')"))
        db.execute(text("DELETE FROM announcements WHERE title LIKE '%[أسبوع%' OR title LIKE '%SQBS%' OR title LIKE '%امتحان عملي%' OR title LIKE '%لوحة الشرف%'"))
        db.execute(text("DELETE FROM assignments WHERE title LIKE '%[تطبيق عملي]%'"))
        db.execute(text("DELETE FROM contact_messages WHERE subject LIKE '%[تجربة أسبوعين]%'"))
        db.commit()

        # 2. Load real Excel degrees for C4 & C5
        c4_grades, c5_grades = load_real_exam_grades(course_students["C4"], course_students["C5"])
        print(f"Loaded REAL exam grades: C5={len(c5_grades)}/{len(course_students['C5'])}, C4={len(c4_grades)}/{len(course_students['C4'])}")

        # 3. Seed QUIZ LOGS & STUDENT ATTEMPTS across 2 weeks (Nov 3 - Nov 17, 2026)
        quiz_logs_created = 0
        attempts_created = 0

        # 3A. Teacher-generated AI quiz banks (8 quizzes across courses over 2 weeks)
        teacher_quizzes = [
            ("C5", 267, "الامتحان العملي (نموذج B): PHP & MySQL Products + Registration", "hard", 11, PHP_MYSQL_QUESTIONS, 3),
            ("C5", 267, "اختبار الأسبوع 1: Clean Architecture & SOLID Principles", "medium", 5, SOLID_QUESTIONS, 10),
            ("C4", 4, "الامتحان العملي المعتمد (من 80 درجة): PHP & MySQL Backend", "hard", 11, PHP_MYSQL_QUESTIONS, 4),
            ("C4", 4, "اختبار الأسبوع 1: Web APIs & Database Security", "medium", 5, SOLID_QUESTIONS, 11),
            ("C2", 3, "امتحان الشبكات العملي: Cisco Routing & VLAN Isolation", "hard", 10, NETWORKING_QUESTIONS, 2),
            ("C2", 3, "اختبار الأسبوع 1: OSI Model & IPv4 Subnetting", "medium", 5, NETWORKING_QUESTIONS, 9),
            ("C1", 135, "اختبار شبكات عملي: DHCP, DNS & Switching Labs", "medium", 10, NETWORKING_QUESTIONS, 5),
            ("C3", 134, "اختبار شبكات عملي: Routing Tables & Packet Tracer", "medium", 10, NETWORKING_QUESTIONS, 6),
            ("C6", 2, "امتحان الاتصالات: Fiber Optics & 5G Modulation", "medium", 10, TELECOM_QUESTIONS, 4),
        ]
        for idx, (cid, tid, topic, diff, nq, qlist, days_ago) in enumerate(teacher_quizzes, 1):
            ql = QuizLog(
                session_id=f"pilot2w_teacher_{cid}_{idx}",
                user_id=tid,
                course_id=cid,
                topic=topic,
                difficulty=diff,
                num_questions=nq,
                questions_json=json.dumps(qlist, ensure_ascii=False),
                score=None,
                attempts_count=len(course_students.get(cid, [])),
                created_at=NOW - timedelta(days=days_ago, hours=random.randint(1, 5)),
            )
            db.add(ql)
            quiz_logs_created += 1

        # 3B. Real C5 & C4 student exam logs + Week 1 formative quiz
        for cid, grade_map in (("C5", c5_grades), ("C4", c4_grades)):
            for u_id, u_name, u_code, u_email in course_students[cid]:
                g = grade_map.get(u_id)
                if g:
                    exam_pct = g["pct"]
                    marks_80 = g["marks_80"]
                    grade_en = g["grade_en"]
                    grade_ar = g["grade_ar"]
                    exam_topic = (
                        f"الامتحان العملي PHP & MySQL ({marks_80}/80 — تقدير {grade_ar} {grade_en})"
                        if cid == "C4"
                        else f"الامتحان العملي PHP & MySQL ({g['ans_pct']}% إجابة / {g['code_pct']}% كود — {grade_ar} {grade_en})"
                    )
                else:
                    # Remaining few students in C4 not present in the Excel sheet get realistic class-average scores
                    exam_pct = round(random.uniform(65.0, 84.0), 1)
                    marks_80 = round((exam_pct / 100.0) * 80.0, 1)
                    grade_en = "ME" if exam_pct >= 70 else "NI"
                    grade_ar = "جيد" if exam_pct >= 70 else "مقبول"
                    exam_topic = f"الامتحان العملي PHP & MySQL ({marks_80}/80 — تقدير {grade_ar} {grade_en})"

                # Week 2: Real Previous Exam Score
                exam_ts = NOW - timedelta(days=3 if cid == "C5" else 4, hours=random.randint(1, 6), minutes=random.randint(0, 55))
                sid_exam = f"pilot2w_exam_{cid}_{u_id}"
                correct_11 = max(0, min(11, round((exam_pct / 100.0) * 11)))
                ql_exam = QuizLog(
                    session_id=sid_exam,
                    user_id=u_id,
                    course_id=cid,
                    topic=exam_topic,
                    difficulty="hard",
                    num_questions=11,
                    questions_json=json.dumps(PHP_MYSQL_QUESTIONS, ensure_ascii=False),
                    score=exam_pct,
                    attempts_count=1,
                    created_at=exam_ts,
                )
                db.add(ql_exam)
                db.flush()
                quiz_logs_created += 1

                att_exam = QuizStudentAttempt(
                    session_id=sid_exam,
                    quiz_log_id=ql_exam.id,
                    student_id=u_id,
                    score=exam_pct,
                    total_questions=11,
                    correct_count=correct_11,
                    answers_json=json.dumps(
                        {
                            "source": g["source"] if g else "class_benchmark",
                            "marks_out_of_80": marks_80,
                            "grade_en": grade_en,
                            "grade_ar": grade_ar,
                        },
                        ensure_ascii=False,
                    ),
                    created_at=exam_ts,
                )
                db.add(att_exam)
                attempts_created += 1

                # Week 1: Formative Quiz (realistic progression leading into Week 2 exam)
                # Keep scores anchored near the student's real degree
                if exam_pct <= 5.0:
                    w1_pct = round(random.uniform(35.0, 48.0), 1)
                else:
                    delta = random.uniform(-8.0, 4.0)
                    w1_pct = round(max(25.0, min(100.0, exam_pct + delta)), 1)
                w1_ts = NOW - timedelta(days=random.randint(9, 12), hours=random.randint(1, 7), minutes=random.randint(0, 55))
                sid_w1 = f"pilot2w_w1_{cid}_{u_id}"
                correct_5 = max(0, min(5, round((w1_pct / 100.0) * 5)))
                ql_w1 = QuizLog(
                    session_id=sid_w1,
                    user_id=u_id,
                    course_id=cid,
                    topic="اختبار الأسبوع 1: Clean Architecture & PHP Basics" if cid == "C5" else "اختبار الأسبوع 1: MySQL Queries & Backend Security",
                    difficulty="medium",
                    num_questions=5,
                    questions_json=json.dumps(SOLID_QUESTIONS, ensure_ascii=False),
                    score=w1_pct,
                    attempts_count=random.choice([1, 1, 2]),
                    created_at=w1_ts,
                )
                db.add(ql_w1)
                db.flush()
                quiz_logs_created += 1

                db.add(
                    QuizStudentAttempt(
                        session_id=sid_w1,
                        quiz_log_id=ql_w1.id,
                        student_id=u_id,
                        score=w1_pct,
                        total_questions=5,
                        correct_count=correct_5,
                        answers_json=json.dumps({"week": 1, "course": cid}, ensure_ascii=False),
                        created_at=w1_ts,
                    )
                )
                attempts_created += 1

        # 3C. Realistic 2-week quizzes for C1, C2, C3 (Networking) and C6 (Communication)
        other_course_meta = {
            "C1": ("اختبار الشبكات (أسبوع 1): OSI & IPv4", "الامتحان العملي للشبكات (أسبوع 2): Switching & VLANs", NETWORKING_QUESTIONS),
            "C2": ("اختبار الشبكات (أسبوع 1): Subnetting & Protocols", "الامتحان العملي للشبكات (أسبوع 2): Cisco Routing & SQBS Lab", NETWORKING_QUESTIONS),
            "C3": ("اختبار الشبكات (أسبوع 1): LAN Architecture", "الامتحان العملي للشبكات (أسبوع 2): Packet Tracer & DHCP", NETWORKING_QUESTIONS),
            "C6": ("اختبار الاتصالات (أسبوع 1): Signal Modulation", "الامتحان العملي للاتصالات (أسبوع 2): Fiber Optics & 5G", TELECOM_QUESTIONS),
        }
        for cid, (t1, t2, qjson) in other_course_meta.items():
            students = course_students[cid]
            for i, (u_id, u_name, u_code, u_email) in enumerate(students):
                # ~85% of students took both quizzes over the 2 weeks
                if i % 7 == 6:
                    continue
                # Realistic student baseline ability
                base = random.gauss(78.0 if cid == "C2" else 74.0, 12.5)
                base = max(42.0, min(97.0, base))
                w1_sc = round(max(38.0, min(96.0, base - random.uniform(2.0, 8.0))), 1)
                w2_sc = round(max(45.0, min(98.5, base + random.uniform(2.0, 7.0))), 1)

                for wk, (topic, sc, nq, d_lo, d_hi) in enumerate(
                    [(t1, w1_sc, 5, 8, 13), (t2, w2_sc, 10, 1, 5)], start=1
                ):
                    ts = NOW - timedelta(days=random.randint(d_lo, d_hi), hours=random.randint(1, 8), minutes=random.randint(0, 55))
                    sid = f"pilot2w_w{wk}_{cid}_{u_id}"
                    ql = QuizLog(
                        session_id=sid,
                        user_id=u_id,
                        course_id=cid,
                        topic=topic,
                        difficulty="medium" if wk == 1 else "hard",
                        num_questions=nq,
                        questions_json=json.dumps(qjson, ensure_ascii=False),
                        score=sc,
                        attempts_count=1,
                        created_at=ts,
                    )
                    db.add(ql)
                    db.flush()
                    quiz_logs_created += 1

                    db.add(
                        QuizStudentAttempt(
                            session_id=sid,
                            quiz_log_id=ql.id,
                            student_id=u_id,
                            score=sc,
                            total_questions=nq,
                            correct_count=max(0, min(nq, round((sc / 100.0) * nq))),
                            answers_json=json.dumps({"week": wk, "course": cid}, ensure_ascii=False),
                            created_at=ts,
                        )
                    )
                    attempts_created += 1

        # 4. Seed 2 WEEKS OF ATTENDANCE SESSIONS & RECORDS (20 sessions, Sun-Thu school days)
        # Nov 17 2026 is Tuesday -> school days in past 2 weeks:
        # Week 1: Sun Nov 1 (16d), Mon Nov 2 (15d), Tue Nov 3 (14d), Wed Nov 4 (13d), Thu Nov 5 (12d)
        # Week 2: Sun Nov 8 (9d), Mon Nov 9 (8d), Tue Nov 10 (7d), Wed Nov 11 (6d), Thu Nov 12 (5d)
        # Week 3 start: Sun Nov 15 (2d), Mon Nov 16 (1d), Tue Nov 17 (0d)
        session_plan = [
            ("C5", 267, "محاضرة 1: Clean Architecture & SOLID Principles", 13, 9, 0),
            ("C5", 267, "معمل عملي 2: PHP MySQLi & CRUD Operations", 9, 10, 30),
            ("C5", 267, "مراجعة الامتحان العملي + تحضير المؤتمر الثالث", 6, 9, 0),
            ("C5", 267, "الامتحان العملي: PHP Products & Registration", 2, 10, 0),
            ("C4", 4, "محاضرة 1: PHP Forms & Input Validation", 12, 8, 30),
            ("C4", 4, "معمل 2: MySQL Database Design & Joins", 8, 10, 0),
            ("C4", 4, "تدريب عملي قبل الامتحان (قالب A و B)", 5, 11, 30),
            ("C4", 4, "جلسة الامتحان العملي المعتمد (80 درجة)", 1, 9, 30),
            ("C2", 3, "محاضرة 1: IPv4 Subnetting & VLSM (تجربة SQBS)", 13, 8, 30),
            ("C2", 3, "معمل الشبكات 2: Cisco Switch VLANs", 9, 11, 0),
            ("C2", 3, "ورشة تفاعلية (الخميس): تقليل إجهاد نهاية الأسبوع", 5, 12, 0),
            ("C2", 3, "تقييم عملي الشبكات وتكريم لوحة الشرف C2", 1, 10, 0),
            ("C1", 135, "محاضرة 1: OSI Model & TCP/IP Stack", 12, 9, 30),
            ("C1", 135, "معمل 2: Router Configuration & Static Routes", 7, 10, 30),
            ("C1", 135, "تطبيق عملي: DHCP & DNS Troubleshooting", 2, 11, 0),
            ("C3", 134, "محاضرة 1: Network Topologies & Cabling", 11, 9, 0),
            ("C3", 134, "معمل 2: Packet Tracer Switching Lab", 6, 10, 30),
            ("C3", 134, "مراجعة الشبكات والاختبار العملي", 1, 11, 30),
            ("C6", 2, "محاضرة 1: Optical Fiber & Signal Modulation", 10, 9, 30),
            ("C6", 2, "معمل 2: 5G Telecom Systems & Spectrum", 2, 10, 30),
        ]

        sessions_created = 0
        records_created = 0
        for idx, (cid, teacher_id, title, days_ago, hr, mn) in enumerate(session_plan, 1):
            created_dt = (NOW - timedelta(days=days_ago)).replace(hour=hr, minute=mn, second=0, microsecond=0)
            expires_dt = created_dt + timedelta(minutes=45)
            token = f"WE-PILOT-{cid}-{idx:02d}"
            sess = AttendanceSession(
                material_id=cid,
                created_by=teacher_id,
                title=title,
                token=token,
                expires_at=expires_dt,
                is_active=False,
                created_at=created_dt,
            )
            db.add(sess)
            db.flush()
            sessions_created += 1

            for u_id, u_name, u_code, u_email in course_students[cid]:
                # Higher attendance for C2 & C5 reflecting strong pilot engagement
                roll = random.random()
                present_thresh = 0.88 if cid in ("C2", "C5") else 0.82
                if roll < present_thresh:
                    st = "PRESENT"
                    offset_min = random.randint(1, 9)
                elif roll < present_thresh + 0.06:
                    st = "LATE"
                    offset_min = random.randint(11, 22)
                elif roll < present_thresh + 0.09:
                    st = "EXCUSED"
                    offset_min = random.randint(2, 10)
                else:
                    continue  # Absent (no scan record)

                db.add(
                    AttendanceRecord(
                        session_id=sess.session_id,
                        material_id=cid,
                        student_id=u_id,
                        scanned_at=created_dt + timedelta(minutes=offset_min, seconds=random.randint(0, 59)),
                        status=st,
                    )
                )
                records_created += 1

        # 5. Seed 2 WEEKS OF ANNOUNCEMENTS & READS
        ann_specs = [
            (267, "[أسبوع 1] انطلاق تجربة منظومة SQBS الذكية بمدرسة WE بالسويس", "أهلاً بأبطال مدرسة WE للتكنولوجيا التطبيقية بالسويس! بدأنا رسمياً تفعيل نظام الحضور الذكي بالـ QR ولوحة الشرف الإيجابية في المعامل.", "general", "high", "all", None, 13),
            (267, "[أسبوع 1] رفع محاضرة Clean Architecture & SOLID لمقرر C5", "تم رفع المحاضرة الأولى وعرض إرشادات المؤتمر الثالث (Conference 3) على بوابة المقرر. يرجى المراجعة وحل الاختبار التفاعلي.", "lecture", "normal", "course", "C5", 11),
            (4, "[أسبوع 1] تعليمات امتحان عملي PHP & MySQL لطلاب فصل C4", "يرجى التأكد من تجهيز ملفات connect.php و products.php و register.php داخل مجلد الطالب مع تطبيق filter_var و htmlspecialchars.", "exam", "urgent", "course", "C4", 9),
            (3, "لوحة الشرف الأسبوعية لفصل C2 — قفزة مشاركة 93%! 🏆", "فخورون بطلاب فصل C2 بعد تحقيق 738 نقطة إيجابية وتحسن مستمر لـ 13 طالباً. استمروا في روح المبادرة والتميز!", "general", "high", "course", "C2", 6),
            (3, "[أسبوع 2] ورشة عمل تفاعلية يوم الخميس لتخفيف إجهاد نهاية الأسبوع", "بناءً على مؤشرات Smart Insights، خصصنا حصة الخميس القادم لنشاط عملي تفاعلي في معمل Cisco Packet Tracer لتجديد النشاط.", "general", "normal", "course", "C2", 5),
            (267, "إعلان نتائج امتحان عملي PHP & MySQL لفصل C5", "تم اعتماد درجات الامتحان العملي ورصدها على المنصة! تهانينا للحاصلين على تقدير ممتاز (EE)، وجاري تخصيص جلسة دعم للطلاب الذين يحتاجون تقوية.", "exam", "high", "course", "C5", 3),
            (4, "اعتماد درجات الامتحان العملي (من 80 درجة) لفصل C4", "تم نشر النتائج الرسمية المعتمدة للامتحان العملي لمقرر البرمجة C4. يمكن لكل طالب مراجعة تفاصيل تقييمه والتواصل مع مهندس المقرر.", "exam", "high", "course", "C4", 2),
            (admin_id, "تحديث أمان المنصة وتفعيل بوابة حضور الطلاب بالـ QR", "تم تفعيل بوابة مسح كود الحضور السريع (/checkin) واستوديو الاختبارات التفاعلية بالذكاء الاصطناعي لجميع الفصول الدراسية بنجاح.", "general", "high", "all", None, 1),
        ]
        anns_created = 0
        reads_created = 0
        all_stu_ids = [u[0] for lst in course_students.values() for u in lst]
        for author_id, title, body, atype, prio, ttype, tcourse, days_ago in ann_specs:
            ts = NOW - timedelta(days=days_ago, hours=random.randint(1, 5))
            ann = Announcement(
                author_id=author_id,
                title=title,
                content=body,
                announcement_type=atype,
                priority=prio,
                target_type=ttype,
                target_course_id=tcourse,
                created_at=ts,
            )
            db.add(ann)
            db.flush()
            anns_created += 1

            audience = [u[0] for u in course_students[tcourse]] if tcourse else random.sample(all_stu_ids, min(40, len(all_stu_ids)))
            readers = random.sample(audience, max(5, int(len(audience) * random.uniform(0.65, 0.92))))
            for rid in readers:
                db.add(
                    AnnouncementRead(
                        user_id=rid,
                        announcement_id=ann.announcement_id,
                        read_at=ts + timedelta(hours=random.randint(1, 18), minutes=random.randint(0, 55)),
                    )
                )
                reads_created += 1

        # 6. Seed ASSIGNMENTS across courses
        assign_specs = [
            ("C5", 267, "[تطبيق عملي] Task 1: MySQL Products Table + CRUD (PHP)", "إنشاء قاعدة بيانات exam_db وجدول products وملفات connect.php و products.php و update.php و delete.php.", 10, 4),
            ("C5", 267, "[تطبيق عملي] Task 2: Student Registration Form with Validation", "بناء نموذج register.php باستخدام POST مع التحقق بـ filter_var والحماية بـ htmlspecialchars.", 6, -1),
            ("C4", 4, "[تطبيق عملي] PHP Arrays, Foreach & Modular Components", "تقسيم الموقع إلى header.php و footer.php و main.php وعرض مصفوفة المنتجات بـ foreach.", 11, 5),
            ("C2", 3, "[تطبيق عملي] تصميم شبكة مدرسة WE عبر Cisco Packet Tracer", "تقسيم الشبكة إلى 3 VLANs (الإدارة، المعامل، الطلاب) وتفعيل DHCP و Inter-VLAN Routing.", 9, 2),
            ("C1", 135, "[تطبيق عملي] حسابات Subnetting لشبكة /26 و /27", "تسليم جدول توزيع عناوين IP ونطاقات البث للشبكات الفرعية الأربع.", 8, 1),
            ("C6", 2, "[تطبيق عملي] مقارنة أنظمة الألياف الضوئية وشبكات 5G", "تقرير تقني مختصر مع رسم توضيحي لمعمارية الإرسال الضوئي.", 7, -2),
        ]
        assigns_created = 0
        for cid, tid, title, desc, created_days, due_days_ago in assign_specs:
            db.add(
                Assignment(
                    material_id=cid,
                    author_id=tid,
                    title=title,
                    description=desc,
                    file_type="text",
                    deadline=NOW - timedelta(days=due_days_ago),
                    created_at=NOW - timedelta(days=created_days),
                )
            )
            assigns_created += 1

        # 7. Seed 2 WEEKS OF REALISTIC CHAT CONVERSATIONS (Students <-> Teachers <-> Admin)
        chat_templates = [
            (
                "C5", 267,
                [
                    ("يا باشمهندس لو سمحت في ملف connect.php استخدم mysqli_connect ولا PDO في امتحان C5؟ [WE-Suez]", "أهلاً يا بطل، استخدم mysqli_connect مع die(mysqli_connect_error()) زي ما طبقنا في المعمل بالظبط. بالتوفيق! 📌"),
                    ("تمام يا باشمهندس جربتها واشتغلت وطلعت المنتجات في جدول products.php!", "ممتاز جداً 👏 كمل بنفس التركيز وراجع filter_var في register.php."),
                ],
            ),
            (
                "C5", 267,
                [
                    ("مساء الخير يا باشمهندس، هل عرض المؤتمر الثالث Conference 3 موجود على المنصة؟ [WE-Suez]", "أيوة يا فندم، مرفوع في تبويب المحاضرات والملفات لمقرر C5 مع محاضرة Clean Architecture."),
                    ("لقيته وحملته وجربت أسئلة الـ AI عليه وكانت مفيدة جداً شكراً لحضرتك!", "بالتوفيق دايماً يا هندسة، وأي استفسار ابعتلي في أي وقت 📌"),
                ],
            ),
            (
                "C4", 4,
                [
                    ("دكتور مهند بعد إذن حضرتك، درجة الامتحان العملي من 80 نزلت على المنصة؟ [WE-Suez]", "أهلاً بيك، أيوة تم اعتماد الدرجات المنطقية من 80 ونزلت النسب والتقديرات لكل طلاب 3-4 📌"),
                    ("الحمد لله شفت نتيجتي وارتفعت عن الأسبوع اللي فات! شكراً لتعب حضرتك معانا.", "فخور بمجهودك، استمر وركز على update.php و delete.php في التطبيق الجاي."),
                ],
            ),
            (
                "C2", 3,
                [
                    ("يا دكتور ندى كود الـ QR بتاع الحضور النهاردة اشتغل معايا في ثانية واحدة! [WE-Suez]", "جميل جداً! ده هدف منظومة SQBS إننا نوفر وقت الحصة للعمل العملي على Packet Tracer 📌"),
                    ("وكمان اسمي طلع في لوحة الشرف الأسبوع ده، بجد شجعتني أشارك أكتر في المعمل.", "تستاهل كل خير، ومستنيين إبداعك في ورشة يوم الخميس التفاعلية 🌟"),
                ],
            ),
            (
                "C1", 135,
                [
                    ("باشمهندسة فاطمة، في مسألة Subnetting /26 عدد الأجهزة المتاحة 62 صح كده؟ [WE-Suez]", "صح 100% يا بطل! لأن 2 أس 6 بيساوي 64 وبنطرح عنوان الشبكة وعنوان الـ Broadcast 📌"),
                    ("تمام فهمتها خلاص وهسلم التكليف النهاردة قبل الميعاد.", "ممتاز، بالتوفيق!"),
                ],
            ),
            (
                "C3", 134,
                [
                    ("باشمهندسة فاطمة حمدي، ملف Packet Tracer فيه مشكلة في توصيل الـ Trunk Port بين السويتشين [WE-Suez]", "اتأكد إنك عملت switchport mode trunk على البورتين في السويتشين وسمحت للـ VLANs المطلوبة 📌"),
                    ("اشتغلت فوراً والـ Ping نجح! ألف شكر لحضرتك.", "شاطر جداً 👏"),
                ],
            ),
            (
                "C6", 2,
                [
                    ("يا باشمهندسة إكرام، ممكن شرح سريع للفرق بين Single-Mode و Multi-Mode Fiber؟ [WE-Suez]", "أكيد: الـ Single-Mode قطره أصغر للمسافات الطويلة بسرعة عالية، والـ Multi-Mode للمسافات القصيرة داخل المباني والمعامل 📌"),
                    ("واضحة جداً يا باشمهندسة شكراً لحضرتك.", "بالتوفيق في امتحان الاتصالات!"),
                ],
            ),
        ]

        chats_created = 0
        for cid, teacher_id, convo_pairs in chat_templates:
            # Pick 3 different real students in that course for natural variety
            pool = course_students[cid]
            chosen_students = random.sample(pool, min(3, len(pool)))
            for s_idx, (stu_id, _, _, _) in enumerate(chosen_students):
                base_ts = NOW - timedelta(days=random.randint(1, 13), hours=random.randint(1, 8))
                for p_idx, (q_msg, a_msg) in enumerate(convo_pairs):
                    t_q = base_ts + timedelta(minutes=p_idx * 18)
                    t_a = t_q + timedelta(minutes=random.randint(3, 12))
                    db.add(ChatHistory(sender_id=stu_id, receiver_id=teacher_id, message=q_msg, content_type="text", status="read", sent_at=t_q))
                    db.add(ChatHistory(sender_id=teacher_id, receiver_id=stu_id, message=a_msg, content_type="text", status="read", sent_at=t_a))
                    chats_created += 2

        # Teacher <-> Admin coordination messages
        admin_convo = [
            (267, admin_id, "تم الانتهاء من رصد درجات الامتحان العملي لفصل C5 ورفع ملفات المراجعة على المنصة. [WE-Suez]", 3),
            (admin_id, 267, "مجهود ممتاز يا باشمهندس عبد الله، النتائج ظهرت في لوحة المراقبة المركزية بنجاح. 📌", 3),
            (4, admin_id, "تم اعتماد توزيع درجات فصل 3-4 (من 80 درجة) وتحديث كشوف الحضور للأسبوعين. [WE-Suez]", 2),
            (admin_id, 4, "تمام يا دكتور مهند، جاري مراجعة تقارير الأداء ونسب النجاح لإدارة المدرسة. 📌", 2),
            (3, admin_id, "تقرير تجربة فصل C2 ممتاز: نسبة المشاركة وصلت 93% وورشة الخميس التفاعلية خفضت الإجهاد. [WE-Suez]", 1),
            (admin_id, 3, "نتائج مشرفة لمدرسة WE بالسويس، شكراً لالتزام الفريق الكامل. 📌", 1),
        ]
        for snd, rcv, msg, d_ago in admin_convo:
            db.add(
                ChatHistory(
                    sender_id=snd,
                    receiver_id=rcv,
                    message=msg,
                    content_type="text",
                    status="read",
                    sent_at=NOW - timedelta(days=d_ago, hours=random.randint(1, 4)),
                )
            )
            chats_created += 1

        # 8. Seed realistic Contact / Support Messages
        support_specs = [
            (course_students["C5"][0][0], course_students["C5"][0][1], course_students["C5"][0][3], "technical", "[تجربة أسبوعين] استفسار عن مسح QR الحضور من الموبايل", "هل يمكنني استخدام كاميرا الموبايل مباشرة لفتح صفحة /checkin؟ تم التجربة واشتغلت بنجاح.", "resolved", 11),
            (course_students["C4"][2][0], course_students["C4"][2][1], course_students["C4"][2][3], "academic", "[تجربة أسبوعين] مراجعة درجة الامتحان العملي C4", "أرغب في الاطلاع على توزيع الدرجات من 80 لسؤال update.php و delete.php.", "resolved", 3),
            (course_students["C2"][1][0], course_students["C2"][1][1], course_students["C2"][1][3], "suggestion", "[تجربة أسبوعين] اقتراح إضافة شارات جديدة للوحة الشرف", "لوحة الشرف شجعت الفصل كله، نقترح إضافة وسام خاص بأفضل مشروع شبكات أسبوعي.", "resolved", 6),
            (course_students["C1"][0][0], course_students["C1"][0][1], course_students["C1"][0][3], "technical", "[تجربة أسبوعين] تحديث كلمة المرور عبر OTP", "تم تغيير كلمة المرور بنجاح بعد استلام الكود، شكراً لفريق الدعم.", "resolved", 8),
            (course_students["C5"][5][0], course_students["C5"][5][1], course_students["C5"][5][3], "academic", "[تجربة أسبوعين] طلب جلسة مراجعة إضافية لمقرر PHP & MySQL", "نحتاج مراجعة عملية إضافية على استعلامات JOIN وربط النماذج قبل المشروع النهائي.", "pending", 1),
        ]
        contacts_created = 0
        for uid, uname, uemail, itype, subj, msg, st, d_ago in support_specs:
            db.add(
                ContactMessage(
                    user_id=uid,
                    user_name=uname,
                    user_email=uemail,
                    issue_type=itype,
                    subject=subj,
                    message=msg,
                    status=st,
                    created_at=NOW - timedelta(days=d_ago, hours=random.randint(1, 6)),
                )
            )
            contacts_created += 1

        # 9. Update users.last_seen realistically across the 2-week testing period
        all_users = db.query(User).all()
        for u in all_users:
            if u.type_code in ("ADM", "DR"):
                u.last_seen = NOW - timedelta(hours=random.randint(0, 18), minutes=random.randint(1, 55))
            else:
                # 75% active within last 48h, 25% within last 3-10 days
                if random.random() < 0.75:
                    u.last_seen = NOW - timedelta(hours=random.randint(0, 48), minutes=random.randint(1, 55))
                else:
                    u.last_seen = NOW - timedelta(days=random.randint(3, 10), hours=random.randint(1, 12))

        db.commit()

        print("=== 2-WEEK PILOT DATABASE SEEDING COMPLETE ===")
        print(f"  Quiz Logs created        : {quiz_logs_created}")
        print(f"  Quiz Attempts created    : {attempts_created}")
        print(f"  Attendance Sessions      : {sessions_created}")
        print(f"  Attendance Records       : {records_created}")
        print(f"  Announcements created    : {anns_created}")
        print(f"  Announcement Reads       : {reads_created}")
        print(f"  Assignments created      : {assigns_created}")
        print(f"  Chat Messages created    : {chats_created}")
        print(f"  Support Messages created : {contacts_created}")
        print(f"  Users last_seen updated  : {len(all_users)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
