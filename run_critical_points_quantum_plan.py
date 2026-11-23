import sys
import json
from pathlib import Path

# Add skill script directory to path
skill_dir = Path(r"C:\Users\dell\.gemini\config\skills\quantum-project-planning\scripts")
sys.path.insert(0, str(skill_dir))

from quantum_project_planner import (
    ProjectTask,
    FeedbackSignal,
    find_missing_business_ideas,
    quantum_project_design_v8_1,
    generate_operational_map,
    apply_feedback_cycle,
)

tasks = [
    # Pillar 1: Discovery
    ProjectTask(
        task_id="cp_disc_student_ux",
        title="Student Exam UX & Mobile Low-Bandwidth Scanner Discovery",
        duration_slots=1,
        utility=92.0,
        cognitive_load=3.0,
        domain="discovery",
        risk_level=3,
        is_strategic=True,
        deliverable="Field ergonomics specification for student exam taking & 25s QR scanner",
        exit_kpi=">= 25 student tests across low-spec phones & lab tablets (99% scan rate)",
        feedback_target=None,
    ),
    # Pillar 2: Architecture
    ProjectTask(
        task_id="cp_arch_student_arena",
        title="Multi-Format Student Exam Runner & Realtime Submission Architecture",
        duration_slots=1,
        utility=88.0,
        cognitive_load=4.0,
        domain="architecture",
        risk_level=2,
        is_strategic=True,
        deliverable="Data contract for 4 question types (MCQ, T/F, Matching, Short Answer)",
        exit_kpi="Deterministic auto-grading latency < 120ms with KaTeX formula support",
        feedback_target="cp_disc_student_ux",
    ),
    # Pillar 3: MVP Build (Student Multi-Format Exam Runner & Summary Gauge)
    ProjectTask(
        task_id="cp_mvp_student_runner",
        title="Interactive Student Multi-Format Exam Runner & Attendance History Gauge",
        duration_slots=2,
        utility=86.0,
        cognitive_load=4.2,
        domain="mvp_build",
        risk_level=2,
        is_strategic=False,
        deliverable="Student quiz taker with True/False, Matching, Short Answer & attendance % gauge",
        exit_kpi="100% test pass on 4 question types with instant rubric feedback",
        feedback_target="cp_arch_student_arena",
    ),
    # Pillar 4: MVP Build (Multimedia Pitch Video Player & Live Showcase)
    ProjectTask(
        task_id="cp_mvp_pitch_showcase",
        title="WeConnect HP IDEA Pitch Video Player & Live Showcase Integration",
        duration_slots=2,
        utility=85.0,
        cognitive_load=3.8,
        domain="mvp_build",
        risk_level=2,
        is_strategic=False,
        deliverable="Embedded 1080p pitch video modal, live app demo launcher & bilingual tabs in /pitch",
        exit_kpi="Smooth 1080p video playback, audio ducking sync & zero video frame drops",
        feedback_target="cp_arch_student_arena",
    ),
    # Pillar 5: Finance & Unit Economics
    ProjectTask(
        task_id="cp_econ_token_cost",
        title="Gemini Context Caching & Free-Tier Token Optimization",
        duration_slots=1,
        utility=84.0,
        cognitive_load=3.5,
        domain="finance_unit_econ",
        risk_level=3,
        is_strategic=True,
        deliverable="Token accounting & caching policy saving > 70% input tokens",
        exit_kpi="Cost per full 10-question multi-format exam < $0.015",
        feedback_target="cp_disc_student_ux",
    ),
    # Pillar 6: Go-to-Market (Inter-School Department Federation)
    ProjectTask(
        task_id="cp_gtm_federation",
        title="Inter-School Question Bank Federation Protocol (Suez - Cairo - Alex)",
        duration_slots=1,
        utility=76.0,
        cognitive_load=3.5,
        domain="go_to_market",
        risk_level=2,
        is_strategic=False,
        deliverable="Federated bank export/import API for cross-campus teacher collaboration",
        exit_kpi="Seamless bank exchange across 3 WE Applied Tech Schools with > 300 shared questions",
        feedback_target="cp_mvp_student_runner",
    ),
    # Pillar 7: Operations & SOPs
    ProjectTask(
        task_id="cp_ops_lab_proctor",
        title="Exam Lab Proctoring SOPs & Offline Scanner Fallback Playbook",
        duration_slots=1,
        utility=72.0,
        cognitive_load=3.0,
        domain="operations",
        risk_level=1,
        is_strategic=False,
        deliverable="Proctor emergency manual check-in SOP and exam recovery guide",
        exit_kpi="Proctor resolution time < 90 seconds for any attendance/network glitch",
        feedback_target="cp_mvp_student_runner",
    ),
    # Pillar 8: Feedback Review
    ProjectTask(
        task_id="cp_fb_student_csat",
        title="Student CSAT, Exam Fairness Metrics & Auto-Remediation Feedback Loop",
        duration_slots=1,
        utility=80.0,
        cognitive_load=3.0,
        domain="feedback_review",
        risk_level=2,
        is_strategic=False,
        deliverable="Closed-loop dashboard tracking student completion rate & remediation adoption",
        exit_kpi="Student CSAT >= 4.6/5; remediation quiz adoption > 60%",
        feedback_target="cp_disc_student_ux",
    ),
]

# 1. Audit gaps
gaps = find_missing_business_ideas(tasks)
print(f"Business Gaps Identified: {len(gaps)}")

# 2. Run Quantum Scheduler
solution = quantum_project_design_v8_1(tasks, horizon_slots=12, max_window_load=8.5)
print(f"Quantum Solution Feasible: {solution.feasible}, Pure Utility: {solution.pure_utility}, Energy: {solution.energy}")

# 3. Generate Operational Map
op_map = generate_operational_map("WeConnect Master Platform Critical Points (WE Applied Tech Schools)", tasks, solution, missing_ideas=gaps)

# 4. Simulate Closed-Loop Feedback
signals = [
    FeedbackSignal(
        task_id="cp_disc_student_ux",
        kpi_achievement=0.98,
        customer_demand_delta=0.4,
        note="Students enthusiastically adopted 25s QR; requested instant attendance percentage view.",
    ),
    FeedbackSignal(
        task_id="cp_mvp_pitch_showcase",
        kpi_achievement=1.0,
        customer_demand_delta=0.5,
        note="Judging committee praised video clarity; requested embedded video player directly in /pitch.",
    ),
]

fb_result = apply_feedback_cycle(
    tasks,
    signals,
    12,
    max_window_load=8.5,
)
fb_solution = fb_result["solution"]
print(f"Post-Feedback Pure Utility: {fb_solution.pure_utility}")

results = {
    "feasible": solution.feasible,
    "pure_utility": solution.pure_utility,
    "post_feedback_utility": fb_solution.pure_utility,
    "schedule": solution.decoded_schedule,
    "gaps_count": len(gaps),
    "mermaid_map": op_map["mermaid_operational_map"],
    "steps": op_map["steps"],
}

out_file = Path(r"C:\Users\dell\.gemini\antigravity\brain\d97b79ec-93a6-4328-8dae-04cc19b9f5b6\scratch\master_quantum_critical_points_results.json")
out_file.parent.mkdir(parents=True, exist_ok=True)
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Results written to: {out_file}")
