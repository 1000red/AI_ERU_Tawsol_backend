from app.services.content_service._helpers import get_user_info

from app.services.content_service.announcements import (
    get_announcement,
    get_announcement_detail,
    get_announcements_for_user,
    get_sent_announcements,
    get_unread_count,
    mark_announcement_read,
    get_available_recipients,
    create_announcement,
    update_announcement,
    delete_announcement,
)

from app.services.content_service.material_files import (
    get_material_file,
    get_material_files,
    get_all_files_for_user,
    create_material_file,
    update_material_file,
    delete_material_file,
)

from app.services.content_service.assignments import (
    get_assignment,
    get_assignment_detail,
    get_material_assignments,
    get_all_assignments_for_user,
    get_upcoming_deadlines,
    create_assignment,
    update_assignment,
    delete_assignment,
)

from app.services.content_service.submissions import (
    get_submission,
    get_assignment_submissions,
    get_student_submission,
    get_my_submission,
    create_submission,
    update_submission,
    delete_submission,
)

__all__ = [
    "get_user_info",
    # Announcements
    "get_announcement", "get_announcement_detail",
    "get_announcements_for_user", "get_sent_announcements",
    "get_unread_count", "mark_announcement_read",
    "get_available_recipients",
    "create_announcement", "update_announcement", "delete_announcement",
    # Material Files
    "get_material_file", "get_material_files", "get_all_files_for_user",
    "create_material_file", "update_material_file", "delete_material_file",
    # Assignments
    "get_assignment", "get_assignment_detail",
    "get_material_assignments", "get_all_assignments_for_user", "get_upcoming_deadlines",
    "create_assignment", "update_assignment", "delete_assignment",
    # Submissions
    "get_submission", "get_assignment_submissions",
    "get_student_submission", "get_my_submission",
    "create_submission", "update_submission", "delete_submission",
]
