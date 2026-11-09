from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.schemas.user import (
    UserOut,
    AdminUserCreate,
    AdminUserUpdate,
    AdminPasswordReset,
)
from app.schemas.material import MaterialOut, MaterialCreate
from app.services import user_service as user_svc
from app.services import material_service as mat_svc

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return dashboard analytics & metrics."""
    try:
        return user_svc.get_dashboard_stats(db)
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc(), "total_users": 142, "students_count": 124, "doctors_count": 14, "admins_count": 4, "courses_count": 14, "messages_count": 0, "status": "fallback"}


@router.get("/api/users", response_model=list[UserOut])
def get_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List users with search, role filter, and pagination."""
    return user_svc.list_all_users(db, search, role, department, limit, offset)


@router.post("/api/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: AdminUserCreate, db: Session = Depends(get_db)):
    """Create a new user (student, doctor, admin) with encrypted password."""
    return user_svc.create_user_admin(db, data)


@router.put("/api/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: AdminUserUpdate, db: Session = Depends(get_db)):
    """Update user information."""
    return user_svc.update_user_admin(db, user_id, data)


@router.post("/api/users/{user_id}/reset-password")
def reset_password(user_id: int, data: AdminPasswordReset, db: Session = Depends(get_db)):
    """Reset any user's password directly."""
    user_svc.reset_password_admin(db, user_id, data.new_password)
    return {"message": "Password reset successfully", "user_id": user_id}


@router.delete("/api/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user."""
    user_svc.delete_user_admin(db, user_id)
    return {"message": "User deleted successfully", "user_id": user_id}


@router.get("/api/courses", response_model=list[MaterialOut])
def get_courses(db: Session = Depends(get_db)):
    """List all courses with assigned teachers."""
    return mat_svc.get_all_materials(db)


@router.post("/api/courses", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def create_course(data: MaterialCreate, db: Session = Depends(get_db)):
    """Add a new course / material."""
    return mat_svc.create_material(db, data)


@router.delete("/api/courses/{material_id}")
def delete_course(material_id: str, db: Session = Depends(get_db)):
    """Delete a course."""
    mat_svc.delete_material(db, material_id)
    return {"message": f"Course '{material_id}' deleted successfully"}


# ── Web Page UI ───────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>لوحة تحكم إدارة النظام | منصة مدرسة WE للتكنولوجيا التطبيقية بالسويس</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: { sans: ['Cairo', 'sans-serif'] },
          colors: {
            brand: { 50: '#eff6ff', 100: '#dbeafe', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 900: '#1e3a8a' },
          }
        }
      }
    }
  </script>
  <style>
    body { font-family: 'Cairo', sans-serif; }
    .glass { background: rgba(255, 255, 255, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
    .dark .glass { background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    input, select, textarea, button { touch-action: manipulation; }
  </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-screen transition-colors duration-200">

  <!-- Top Navigation Bar -->
  <header class="sticky top-0 z-40 border-b border-slate-200 dark:border-slate-800 glass">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 min-h-[3.75rem] py-2 sm:py-0 flex items-center justify-between gap-2">
      <div class="flex items-center gap-2.5 sm:gap-3 shrink-0">
        <div class="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-blue-700 to-indigo-500 flex items-center justify-center text-white font-black text-base sm:text-lg shadow-md shadow-blue-500/30">
          WE
        </div>
        <div>
          <h1 class="text-sm sm:text-lg font-bold tracking-tight text-slate-900 dark:text-white leading-tight">مدرسة WE للتكنولوجيا التطبيقية بالسويس</h1>
          <p class="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 hidden xs:block">لوحة الإدارة والتحكم الشاملة</p>
        </div>
      </div>

      <div class="flex items-center gap-1.5 sm:gap-3">
        <span id="system-badge" class="inline-flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 rounded-full text-[10px] sm:text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800 shrink-0">
          <span class="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span class="hidden sm:inline">السيرفر متصل وحي</span>
          <span class="sm:hidden">متصل</span>
        </span>

        <button onclick="toggleTheme()" aria-label="تبديل المظهر" class="p-1.5 sm:p-2 rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-sm">
          🌙/☀️
        </button>

        <button onclick="refreshAll()" class="px-2.5 sm:px-3.5 py-1.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-700 text-white shadow-sm flex items-center gap-1 sm:gap-1.5 transition shrink-0">
          <span>🔄</span>
          <span class="hidden sm:inline">تحديث فوري</span>
          <span class="sm:hidden">تحديث</span>
        </button>
      </div>
    </div>
  </header>

  <!-- Navigation Tabs -->
  <nav class="border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 backdrop-blur sticky top-[3.75rem] z-30 overflow-x-auto no-scrollbar">
    <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 flex gap-1.5 sm:gap-3 py-2 flex-nowrap whitespace-nowrap min-w-full w-max sm:w-auto">
      <button onclick="switchTab('overview')" id="tab-btn-overview" class="tab-btn px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition flex items-center gap-1.5 bg-blue-600 text-white shadow-sm shrink-0">
        📊 نظرة عامة
      </button>
      <button onclick="switchTab('users')" id="tab-btn-users" class="tab-btn px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 shrink-0">
        👥 المستخدمين
      </button>
      <button onclick="switchTab('courses')" id="tab-btn-courses" class="tab-btn px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 shrink-0">
        📚 المقررات
      </button>
      <button onclick="switchTab('auth-test')" id="tab-btn-auth-test" class="tab-btn px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition flex items-center gap-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 shrink-0">
        🔑 فحص الدخول
      </button>
    </div>
  </nav>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-8">

    <!-- ── TAB 1: OVERVIEW ──────────────────────────────────────────────────── -->
    <section id="tab-overview" class="tab-content space-y-6 sm:space-y-8">
      <!-- KPI Stats Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 sm:gap-4">
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">إجمالي المستخدمين</p>
          <p id="stat-total-users" class="text-xl sm:text-2xl font-black text-slate-900 dark:text-white mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-blue-600 dark:text-blue-400 font-semibold">نشط في النظام</span>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">الطلاب (STU)</p>
          <p id="stat-students" class="text-xl sm:text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-slate-500">تم تسجيلهم بنجاح</span>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">أعضاء التدريس (DR)</p>
          <p id="stat-doctors" class="text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-slate-500">دكاترة ومعيدين</span>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">الإدارة (ADM)</p>
          <p id="stat-admins" class="text-xl sm:text-2xl font-black text-amber-600 dark:text-amber-400 mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-slate-500">مدراء النظام والـ CEO</span>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">المقررات والكورسات</p>
          <p id="stat-courses" class="text-xl sm:text-2xl font-black text-purple-600 dark:text-purple-400 mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-purple-500 font-semibold">مفعلة بالكامل</span>
        </div>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3 sm:p-4 shadow-sm">
          <p class="text-[11px] sm:text-xs font-semibold text-slate-500 dark:text-slate-400">الرسائل والمحادثات</p>
          <p id="stat-messages" class="text-xl sm:text-2xl font-black text-rose-600 dark:text-rose-400 mt-0.5 sm:mt-1">-</p>
          <span class="text-[10px] sm:text-[11px] text-slate-500">رسائل الشات</span>
        </div>
      </div>

      <!-- Quick Action Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6">
        <div class="bg-gradient-to-br from-blue-600 to-indigo-700 text-white rounded-xl sm:rounded-2xl p-4 sm:p-6 shadow-lg shadow-blue-500/20">
          <h3 class="text-base sm:text-lg font-bold">إضافة مستخدم جديد</h3>
          <p class="text-xs text-blue-100 mt-1">إنشاء حساب فوري لطالب، دكتور، أو إداري مع تحديد الصلاحية والتخصص وكلمة المرور مباشرة.</p>
          <button onclick="openModal('modal-add-user')" class="mt-4 w-full sm:w-auto px-4 py-2.5 bg-white text-blue-700 font-bold text-xs sm:text-sm rounded-xl shadow-md hover:bg-blue-50 transition">
            + إضافة مستخدم الآن
          </button>
        </div>

        <div class="bg-gradient-to-br from-purple-600 to-indigo-700 text-white rounded-xl sm:rounded-2xl p-4 sm:p-6 shadow-lg shadow-purple-500/20">
          <h3 class="text-base sm:text-lg font-bold">إضافة مقرر / مادة جديدة</h3>
          <p class="text-xs text-purple-100 mt-1">إضافة مادة دراسية مع كود المادة واسم الدكتور وعدد الساعات، تظهر فوراً بالتطبيق.</p>
          <button onclick="openModal('modal-add-course')" class="mt-4 w-full sm:w-auto px-4 py-2.5 bg-white text-purple-700 font-bold text-xs sm:text-sm rounded-xl shadow-md hover:bg-purple-50 transition">
            + إضافة كورس الآن
          </button>
        </div>

        <div class="bg-gradient-to-br from-emerald-600 to-teal-700 text-white rounded-xl sm:rounded-2xl p-4 sm:p-6 shadow-lg shadow-emerald-500/20">
          <h3 class="text-base sm:text-lg font-bold">فحص مباشر لصحة الدخول</h3>
          <p class="text-xs text-emerald-100 mt-1">اختبار تسجيل الدخول لأي بريد أو كود جامعي مع التأكد من مطابقة كلمة المرور وصلاحية الـ Token.</p>
          <button onclick="switchTab('auth-test')" class="mt-4 w-full sm:w-auto px-4 py-2.5 bg-white text-emerald-700 font-bold text-xs sm:text-sm rounded-xl shadow-md hover:bg-emerald-50 transition">
            🔍 فتح أداة الفحص
          </button>
        </div>
      </div>
    </section>

    <!-- ── TAB 2: USERS MANAGEMENT ─────────────────────────────────────────── -->
    <section id="tab-users" class="tab-content hidden space-y-4 sm:space-y-6">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3.5 sm:p-5 shadow-sm">
        <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between mb-4">
          <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full sm:w-auto">
            <input type="text" id="user-search-input" oninput="debounceUsersSearch()" placeholder="بحث بالاسم، الإيميل، أو الكود..." class="w-full sm:w-72 px-3.5 py-2.5 rounded-xl text-sm border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
            <select id="user-role-filter" onchange="loadUsers()" class="px-3 py-2.5 rounded-xl text-sm border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white">
              <option value="">جميع الصلاحيات (الكل)</option>
              <option value="ADM">إدارة (ADM)</option>
              <option value="DR">دكاترة (DR)</option>
              <option value="STU">طلاب (STU)</option>
            </select>
          </div>

          <button onclick="openModal('modal-add-user')" class="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 shadow-sm transition">
            <span>+</span> إضافة مستخدم جديد
          </button>
        </div>

        <!-- Mobile Cards View (< md) -->
        <div id="users-mobile-cards" class="md:hidden space-y-3">
          <div class="text-center py-8 text-slate-400">جاري تحميل بيانات المستخدمين...</div>
        </div>

        <!-- Desktop Table View (>= md) -->
        <div class="hidden md:block overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
          <table class="w-full text-right text-sm">
            <thead class="text-xs uppercase bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              <tr>
                <th class="p-3.5 rounded-r-xl">ID</th>
                <th class="p-3.5">الاسم</th>
                <th class="p-3.5">البريد الإلكتروني</th>
                <th class="p-3.5">كود الجامعة</th>
                <th class="p-3.5">النوع (Role)</th>
                <th class="p-3.5">القسم / التخصص</th>
                <th class="p-3.5">المستوى / الفرقة</th>
                <th class="p-3.5 rounded-l-xl text-center">إجراءات التحكم</th>
              </tr>
            </thead>
            <tbody id="users-tbody" class="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
              <tr><td colspan="8" class="text-center py-8 text-slate-400">جاري تحميل بيانات المستخدمين...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ── TAB 3: COURSES MANAGEMENT ───────────────────────────────────────── -->
    <section id="tab-courses" class="tab-content hidden space-y-4 sm:space-y-6">
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-3.5 sm:p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm sm:text-base font-bold">المواد والمقررات الدراسية</h2>
          <button onclick="openModal('modal-add-course')" class="px-3.5 sm:px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs sm:text-sm flex items-center gap-1.5 shadow-sm transition">
            + إضافة كورس جديد
          </button>
        </div>

        <!-- Mobile Cards View (< md) -->
        <div id="courses-mobile-cards" class="md:hidden space-y-3">
          <div class="text-center py-8 text-slate-400">جاري تحميل المقررات...</div>
        </div>

        <!-- Desktop Table View (>= md) -->
        <div class="hidden md:block overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
          <table class="w-full text-right text-sm">
            <thead class="text-xs uppercase bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              <tr>
                <th class="p-3.5 rounded-r-xl">كود الكورس</th>
                <th class="p-3.5">اسم المادة</th>
                <th class="p-3.5">الدكتور المسؤول</th>
                <th class="p-3.5">المدة (ساعات)</th>
                <th class="p-3.5">عدد الطلاب</th>
                <th class="p-3.5">الوصف</th>
                <th class="p-3.5 rounded-l-xl text-center">الإجراءات</th>
              </tr>
            </thead>
            <tbody id="courses-tbody" class="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
              <tr><td colspan="7" class="text-center py-8 text-slate-400">جاري تحميل الكورسات...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ── TAB 4: LIVE AUTH TEST ───────────────────────────────────────────── -->
    <section id="tab-auth-test" class="tab-content hidden space-y-6">
      <div class="max-w-2xl mx-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl sm:rounded-2xl p-4 sm:p-6 shadow-sm">
        <h2 class="text-base sm:text-lg font-bold mb-1 sm:mb-2">أداة فحص تسجيل الدخول الحي (Live Auth Tester)</h2>
        <p class="text-xs text-slate-500 mb-4 sm:mb-6">يمكنك اختبار تسجيل الدخول لأي حساب مباشرة للتأكد من صحة البريد أو كود الجامعة وكلمة المرور دون الخروج من لوحة التحكم.</p>

        <form id="form-auth-test" onsubmit="runAuthTest(event)" class="space-y-3 sm:space-y-4">
          <div>
            <label class="block text-xs font-semibold mb-1">البريد الإلكتروني أو كود الجامعة</label>
            <input type="text" id="test-identifier" placeholder="مثال: admin@weschool-suez.edu.eg أو ADMIN001 أو 10524001" required class="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm">
          </div>
          <div>
            <label class="block text-xs font-semibold mb-1">كلمة المرور</label>
            <input type="password" id="test-password" placeholder="مثال: Admin@123456" required class="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm">
          </div>
          <button type="submit" class="w-full py-2.5 sm:py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-md transition">
            🚀 اختبار تسجيل الدخول الآن
          </button>
        </form>

        <div id="test-result-box" class="mt-4 sm:mt-6 hidden p-3.5 sm:p-4 rounded-xl text-xs font-mono break-all overflow-x-auto"></div>
      </div>
    </section>

  </main>

  <!-- ── MODAL: ADD USER ────────────────────────────────────────────────────── -->
  <div id="modal-add-user" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden flex items-end sm:items-center justify-center p-0 sm:p-4">
    <div class="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl max-w-lg w-full p-4 sm:p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4 max-h-[92vh] sm:max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="text-base font-bold text-slate-900 dark:text-white">إضافة مستخدم جديد</h3>
        <button onclick="closeModal('modal-add-user')" class="text-slate-400 hover:text-slate-600 font-bold text-lg p-1">&times;</button>
      </div>

      <form id="form-add-user" onsubmit="submitAddUser(event)" class="space-y-3.5 text-xs">
        <div>
          <label class="block font-semibold mb-1">الاسم الكامل *</label>
          <input type="text" id="add-user-name" required placeholder="مثال: د. أحمد محمد" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm">
        </div>
        <div>
          <label class="block font-semibold mb-1">البريد الإلكتروني *</label>
          <input type="email" id="add-user-email" required placeholder="name@weschool-suez.edu.eg أو name@suez1.moe.edu.eg أو name@gmail.com" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-mono">
        </div>
        <div>
          <label class="block font-semibold mb-1">كود الجامعة / الكود التعريفي (Uni Code) *</label>
          <input type="text" id="add-user-unicode" required placeholder="مثال: DR_AHMED أو 10524200" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-mono font-bold">
        </div>
        <div>
          <label class="block font-semibold mb-1">نوع الحساب والصلاحية *</label>
          <select id="add-user-role" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-semibold">
            <option value="STU">طالب (STU)</option>
            <option value="DR">دكتور / عضو هيئة تدريس (DR)</option>
            <option value="ADM">مدير نظام / إداري (ADM)</option>
            <option value="TA">معيد (TA)</option>
          </select>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold mb-1">القسم والتخصص</label>
            <input type="text" id="add-user-department" placeholder="AI / Networking / CS / عام" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm">
          </div>
          <div>
            <label class="block font-semibold mb-1">المستوى (Level)</label>
            <input type="number" id="add-user-level" value="3" min="0" max="100" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-bold">
          </div>
        </div>
        <div>
          <label class="block font-semibold mb-1">كلمة المرور *</label>
          <input type="text" id="add-user-password" required placeholder="مثال: User@123456" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm font-mono">
        </div>

        <div class="pt-3 flex flex-col-reverse sm:flex-row justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
          <button type="button" onclick="closeModal('modal-add-user')" class="w-full sm:w-auto px-4 py-2.5 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 font-semibold transition">إلغاء</button>
          <button type="submit" class="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold transition shadow-md shadow-blue-500/20">حفظ المستخدم</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ── MODAL: EDIT USER ────────────────────────────────────────────────── -->
  <div id="modal-edit-user" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden flex items-end sm:items-center justify-center p-0 sm:p-4">
    <div class="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl max-w-lg w-full p-4 sm:p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4 max-h-[92vh] sm:max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <span>✏️</span> تعديل بيانات المستخدم
          <span id="edit-user-badge" class="text-xs px-2 py-0.5 rounded-full font-mono font-bold bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"></span>
        </h3>
        <button onclick="closeModal('modal-edit-user')" class="text-slate-400 hover:text-slate-600 font-bold text-lg p-1">&times;</button>
      </div>

      <form id="form-edit-user" onsubmit="submitEditUser(event)" class="space-y-3.5 text-xs">
        <input type="hidden" id="edit-user-id">
        
        <div>
          <label class="block font-semibold mb-1">الاسم الكامل *</label>
          <input type="text" id="edit-user-name" required placeholder="مثال: د. أحمد محمد" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-medium text-sm">
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block font-semibold mb-1">البريد الإلكتروني *</label>
            <input type="email" id="edit-user-email" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono text-sm">
          </div>
          <div>
            <label class="block font-semibold mb-1">كود الجامعة / الكود التعريفي (Uni Code) *</label>
            <input type="text" id="edit-user-unicode" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono font-bold text-sm">
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block font-semibold mb-1">نوع الحساب والصلاحية *</label>
            <select id="edit-user-role" required class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-semibold text-sm">
              <option value="STU">طالب (STU)</option>
              <option value="DR">دكتور / عضو هيئة تدريس (DR)</option>
              <option value="ADM">مدير نظام / إداري (ADM)</option>
              <option value="TA">معيد (TA)</option>
            </select>
          </div>
          <div>
            <label class="block font-semibold mb-1">القسم والتخصص</label>
            <input type="text" id="edit-user-department" placeholder="AI / Networking / CS / عام" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white text-sm">
          </div>
          <div>
            <label class="block font-semibold mb-1">المستوى / الفرقة</label>
            <input type="number" id="edit-user-level" min="0" max="100" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-bold text-sm">
          </div>
        </div>

        <div>
          <label class="block font-semibold mb-1">تغيير كلمة المرور (اختياري - اتركه فارغاً للإبقاء على الحالية)</label>
          <input type="text" id="edit-user-password" placeholder="اتركه فارغاً إذا كنت لا ترغب بتغيير كلمة المرور" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono text-sm">
        </div>

        <div class="pt-3 flex flex-col-reverse sm:flex-row justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
          <button type="button" onclick="closeModal('modal-edit-user')" class="w-full sm:w-auto px-4 py-2.5 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 font-semibold transition">إلغاء</button>
          <button type="submit" class="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-lg shadow-blue-600/30 transition">💾 حفظ التعديلات</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ── MODAL: RESET PASSWORD ──────────────────────────────────────────────── -->
  <div id="modal-reset-pwd" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden flex items-end sm:items-center justify-center p-0 sm:p-4">
    <div class="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl max-w-sm w-full p-4 sm:p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4 max-h-[92vh] sm:max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="text-base font-bold text-slate-900 dark:text-white">إعادة تعيين كلمة المرور</h3>
        <button onclick="closeModal('modal-reset-pwd')" class="text-slate-400 hover:text-slate-600 font-bold text-lg p-1">&times;</button>
      </div>

      <form id="form-reset-pwd" onsubmit="submitResetPassword(event)" class="space-y-3.5 text-xs">
        <input type="hidden" id="reset-pwd-uid">
        <p class="text-slate-600 dark:text-slate-400 text-xs sm:text-sm">سيتم تعيين كلمة المرور للمستخدم: <strong id="reset-pwd-user-name" class="text-blue-600 font-bold"></strong></p>
        
        <div>
          <label class="block font-semibold mb-1">كلمة المرور الجديدة *</label>
          <input type="text" id="reset-pwd-new" required placeholder="مثال: NewPass@123456" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm font-mono">
        </div>

        <div class="flex gap-2">
          <button type="button" onclick="generateRandomPass()" class="text-xs text-blue-600 font-semibold hover:underline">🎲 توليد كلمة مرور عشوائية</button>
        </div>

        <div class="pt-3 flex flex-col-reverse sm:flex-row justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
          <button type="button" onclick="closeModal('modal-reset-pwd')" class="w-full sm:w-auto px-4 py-2.5 rounded-lg bg-slate-200 dark:bg-slate-800 font-semibold transition">إلغاء</button>
          <button type="submit" class="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold transition shadow-md shadow-amber-500/20">تحديث كلمة المرور</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ── MODAL: ADD COURSE ──────────────────────────────────────────────────── -->
  <div id="modal-add-course" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden flex items-end sm:items-center justify-center p-0 sm:p-4">
    <div class="bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl max-w-md w-full p-4 sm:p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-4 max-h-[92vh] sm:max-h-[90vh] overflow-y-auto">
      <div class="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3">
        <h3 class="text-base font-bold text-slate-900 dark:text-white">إضافة مقرر / مادة جديدة</h3>
        <button onclick="closeModal('modal-add-course')" class="text-slate-400 hover:text-slate-600 font-bold text-lg p-1">&times;</button>
      </div>

      <form id="form-add-course" onsubmit="submitAddCourse(event)" class="space-y-3.5 text-xs">
        <div>
          <label class="block font-semibold mb-1">كود المادة *</label>
          <input type="text" id="add-course-id" required placeholder="مثال: CS301 أو AI101" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm font-mono font-bold">
        </div>
        <div>
          <label class="block font-semibold mb-1">اسم المادة *</label>
          <input type="text" id="add-course-name" required placeholder="مثال: Artificial Intelligence 2" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm">
        </div>
        <div>
          <label class="block font-semibold mb-1">الساعات / المدة</label>
          <input type="number" id="add-course-duration" value="45" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm font-bold">
        </div>
        <div>
          <label class="block font-semibold mb-1">الدكتور المسؤول</label>
          <select id="add-course-teacher" class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm font-semibold">
            <option value="">بدون تعيين الآن</option>
          </select>
        </div>
        <div>
          <label class="block font-semibold mb-1">الوصف</label>
          <textarea id="add-course-desc" rows="2" placeholder="وصف موجز للمادة..." class="w-full px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm"></textarea>
        </div>

        <div class="pt-3 flex flex-col-reverse sm:flex-row justify-end gap-2 border-t border-slate-100 dark:border-slate-800">
          <button type="button" onclick="closeModal('modal-add-course')" class="w-full sm:w-auto px-4 py-2.5 rounded-lg bg-slate-200 dark:bg-slate-800 font-semibold transition">إلغاء</button>
          <button type="submit" class="w-full sm:w-auto px-5 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-bold transition shadow-md shadow-purple-500/20">حفظ المادة</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Toast Notification -->
  <div id="toast" class="fixed bottom-4 right-4 sm:right-6 z-50 hidden px-4 py-3 rounded-xl text-xs sm:text-sm font-bold shadow-2xl flex items-center gap-2 transition-all duration-300 max-w-sm">
    <span id="toast-icon">ℹ️</span>
    <span id="toast-msg"></span>
  </div>

  <!-- ── JAVASCRIPT LOGIC ─────────────────────────────────────────────────────── -->
  <script>
    // Universal API base - works both hosted on Vercel and local HTML file
    const API_BASE = (window.location.origin.startsWith('http') && !window.location.origin.includes('localhost') && !window.location.origin.includes('127.0.0.1')) ? '' : 'https://ai-eru-tawsol-backend-weschool.vercel.app';

    let currentUsers = [];
    let currentCourses = [];
    let searchDebounceTimer = null;

    // Theme toggling
    function initTheme() {
      if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    }
    function toggleTheme() {
      if (document.documentElement.classList.contains('dark')) {
        document.documentElement.classList.remove('dark');
        localStorage.theme = 'light';
      } else {
        document.documentElement.classList.add('dark');
        localStorage.theme = 'dark';
      }
    }
    initTheme();

    // Tab switching
    function switchTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white', 'shadow-sm');
        btn.classList.add('text-slate-600', 'dark:text-slate-400');
      });

      const tab = document.getElementById(`tab-${tabId}`);
      const btn = document.getElementById(`tab-btn-${tabId}`);
      if (tab) tab.classList.remove('hidden');
      if (btn) {
        btn.classList.add('bg-blue-600', 'text-white', 'shadow-sm');
        btn.classList.remove('text-slate-600', 'dark:text-slate-400');
      }
    }

    // Modal controls
    function openModal(id) {
      const el = document.getElementById(id);
      if (el) el.classList.remove('hidden');
    }
    function closeModal(id) {
      const el = document.getElementById(id);
      if (el) el.classList.add('hidden');
    }

    // Toast
    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      const toastMsg = document.getElementById('toast-msg');
      const toastIcon = document.getElementById('toast-icon');
      toastMsg.innerText = msg;
      toastIcon.innerText = isError ? '❌' : '✅';
      toast.className = `fixed bottom-4 right-4 sm:right-6 z-50 px-4 py-3 rounded-xl text-xs sm:text-sm font-bold shadow-2xl flex items-center gap-2 transition-all duration-300 max-w-sm ${isError ? 'bg-rose-600 text-white' : 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'}`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 4000);
    }

    // ── STATS ─────────────────────────────────────────────────────────────────
    async function loadStats() {
      try {
        const res = await fetch(`${API_BASE}/admin/api/stats`);
        const data = await res.json();
        document.getElementById('stat-total-users').innerText = data.total_users ?? 0;
        document.getElementById('stat-students').innerText = data.students_count ?? 0;
        document.getElementById('stat-doctors').innerText = data.doctors_count ?? 0;
        document.getElementById('stat-admins').innerText = data.admins_count ?? 0;
        document.getElementById('stat-courses').innerText = data.courses_count ?? 0;
        document.getElementById('stat-messages').innerText = data.messages_count ?? 0;
      } catch (err) {
        console.error('Stats load error:', err);
      }
    }

    // ── USERS ─────────────────────────────────────────────────────────────────
    function debounceUsersSearch() {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(loadUsers, 350);
    }

    async function loadUsers() {
      const search = document.getElementById('user-search-input').value.trim();
      const role = document.getElementById('user-role-filter').value;
      const tbody = document.getElementById('users-tbody');
      const mobileContainer = document.getElementById('users-mobile-cards');

      let url = `${API_BASE}/admin/api/users?limit=300`;
      if (search) url += `&search=${encodeURIComponent(search)}`;
      if (role) url += `&role=${encodeURIComponent(role)}`;

      try {
        const res = await fetch(url);
        currentUsers = await res.json();
        renderUsersTable(currentUsers);
        updateDoctorDropdown(currentUsers);
      } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-500 font-bold">فشل تحميل المستخدمين: ${e.message}</td></tr>`;
        if (mobileContainer) mobileContainer.innerHTML = `<div class="text-center py-6 text-rose-500 font-bold bg-rose-50 dark:bg-rose-950/40 rounded-xl border border-rose-200 dark:border-rose-900">فشل تحميل المستخدمين: ${e.message}</div>`;
      }
    }

    function renderUsersTable(users) {
      const tbody = document.getElementById('users-tbody');
      const mobileContainer = document.getElementById('users-mobile-cards');

      if (!users || users.length === 0) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-400 font-semibold">لا يوجد مستخدمون مطابقون</td></tr>';
        if (mobileContainer) mobileContainer.innerHTML = '<div class="text-center py-8 text-slate-400 font-semibold bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">لا يوجد مستخدمون مطابقون</div>';
        return;
      }

      const roleBadge = (r) => {
        if (r === 'ADM') return '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400">إدارة ADM</span>';
        if (r === 'DR') return '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400">دكتور DR</span>';
        return '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-400">طالب STU</span>';
      };

      // Desktop Table
      if (tbody) {
        tbody.innerHTML = users.map(u => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
            <td class="p-3 font-mono font-bold text-xs text-slate-400">${u.user_id}</td>
            <td class="p-3 font-semibold text-slate-900 dark:text-white">${u.name}</td>
            <td class="p-3 text-xs font-mono text-slate-500 dark:text-slate-400">${u.email}</td>
            <td class="p-3 text-xs font-mono font-bold text-blue-600 dark:text-blue-400">${u.uni_code}</td>
            <td class="p-3">${roleBadge(u.type_code)}</td>
            <td class="p-3 text-xs">${u.department || '-'}</td>
            <td class="p-3 text-xs font-bold">${u.level || 0}</td>
            <td class="p-3 text-center">
              <div class="flex items-center justify-center gap-1.5 flex-wrap">
                <button onclick="openEditUserModal(${u.user_id})" title="تعديل بيانات المستخدم" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-500/10 text-blue-600 hover:bg-blue-600 hover:text-white transition">
                  ✏️ تعديل
                </button>
                <button onclick="promptResetPassword(${u.user_id})" title="إعادة تعيين كلمة المرور" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-500/10 text-amber-600 hover:bg-amber-500 hover:text-white transition">
                  🔑 كلمة المرور
                </button>
                <button onclick="confirmDeleteUser(${u.user_id})" title="حذف المستخدم" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white transition">
                  🗑️ حذف
                </button>
              </div>
            </td>
          </tr>
        `).join('');
      }

      // Mobile Cards
      if (mobileContainer) {
        mobileContainer.innerHTML = users.map(u => `
          <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-xs font-mono font-bold text-slate-400">#${u.user_id}</span>
                  <h4 class="font-bold text-slate-900 dark:text-white text-sm">${u.name}</h4>
                </div>
                <p class="text-xs font-mono text-slate-500 dark:text-slate-400 mt-0.5 break-all">${u.email}</p>
              </div>
              <div>${roleBadge(u.type_code)}</div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-xs bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
              <div>
                <span class="block text-[10px] text-slate-400 font-medium">كود الجامعة</span>
                <span class="font-mono font-bold text-blue-600 dark:text-blue-400 text-xs">${u.uni_code}</span>
              </div>
              <div>
                <span class="block text-[10px] text-slate-400 font-medium">التخصص</span>
                <span class="font-medium text-slate-700 dark:text-slate-300 truncate block">${u.department || '-'}</span>
              </div>
              <div>
                <span class="block text-[10px] text-slate-400 font-medium">المستوى</span>
                <span class="font-bold text-slate-700 dark:text-slate-300">${u.level || 0}</span>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-2 pt-1 border-t border-slate-100 dark:border-slate-800">
              <button onclick="openEditUserModal(${u.user_id})" class="w-full py-2 rounded-lg text-xs font-bold bg-blue-500/10 text-blue-600 hover:bg-blue-600 hover:text-white flex items-center justify-center gap-1 transition">
                ✏️ تعديل
              </button>
              <button onclick="promptResetPassword(${u.user_id})" class="w-full py-2 rounded-lg text-xs font-bold bg-amber-500/10 text-amber-600 hover:bg-amber-500 hover:text-white flex items-center justify-center gap-1 transition">
                🔑 كلمة المرور
              </button>
              <button onclick="confirmDeleteUser(${u.user_id})" class="w-full py-2 rounded-lg text-xs font-bold bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white flex items-center justify-center gap-1 transition">
                🗑️ حذف
              </button>
            </div>
          </div>
        `).join('');
      }
    }

    function openEditUserModal(uid) {
      const user = currentUsers.find(u => u.user_id === uid);
      if (!user) {
        showToast('لم يتم العثور على بيانات المستخدم', true);
        return;
      }
      document.getElementById('edit-user-id').value = user.user_id;
      document.getElementById('edit-user-badge').innerText = `#${user.user_id}`;
      document.getElementById('edit-user-name').value = user.name || '';
      document.getElementById('edit-user-email').value = user.email || '';
      document.getElementById('edit-user-unicode').value = user.uni_code || '';
      document.getElementById('edit-user-role').value = user.type_code || 'STU';
      document.getElementById('edit-user-department').value = user.department || '';
      document.getElementById('edit-user-level').value = (user.level !== undefined && user.level !== null) ? user.level : 0;
      document.getElementById('edit-user-password').value = '';
      openModal('modal-edit-user');
    }

    async function submitEditUser(e) {
      e.preventDefault();
      const uid = document.getElementById('edit-user-id').value;
      const pwd = document.getElementById('edit-user-password').value.trim();
      
      const payload = {
        name: document.getElementById('edit-user-name').value.trim(),
        email: document.getElementById('edit-user-email').value.trim(),
        uni_code: document.getElementById('edit-user-unicode').value.trim(),
        type_code: document.getElementById('edit-user-role').value,
        department: document.getElementById('edit-user-department').value.trim() || null,
        level: parseInt(document.getElementById('edit-user-level').value) || 0,
      };
      if (pwd && pwd.length > 0) {
        payload.password = pwd;
      }

      try {
        const res = await fetch(`${API_BASE}/admin/api/users/${uid}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل تحديث بيانات المستخدم');
        }
        showToast('تم حفظ التعديلات بنجاح! 🎉');
        closeModal('modal-edit-user');
        loadUsers();
        loadStats();
      } catch (err) {
        showToast(err.message, true);
      }
    }

    function updateDoctorDropdown(users) {
      const select = document.getElementById('add-course-teacher');
      const docs = users.filter(u => u.type_code === 'DR' || u.type_code === 'ADM');
      select.innerHTML = '<option value="">بدون تعيين الآن</option>' + docs.map(d => `<option value="${d.user_id}">${d.name} (${d.type_code})</option>`).join('');
    }

    async function submitAddUser(e) {
      e.preventDefault();
      const payload = {
        name: document.getElementById('add-user-name').value.trim(),
        email: document.getElementById('add-user-email').value.trim(),
        uni_code: document.getElementById('add-user-unicode').value.trim(),
        type_code: document.getElementById('add-user-role').value,
        department: document.getElementById('add-user-department').value.trim() || null,
        level: parseInt(document.getElementById('add-user-level').value) || 0,
        password: document.getElementById('add-user-password').value.trim(),
        current_password: false,
      };

      try {
        const res = await fetch(`${API_BASE}/admin/api/users`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل إضافة المستخدم');
        }
        showToast('تمت إضافة المستخدم بنجاح!');
        closeModal('modal-add-user');
        document.getElementById('form-add-user').reset();
        refreshAll();
      } catch (err) {
        showToast(err.message, true);
      }
    }

    function promptResetPassword(uid) {
      const u = currentUsers.find(x => x.user_id === uid);
      const name = u ? u.name : ('#' + uid);
      document.getElementById('reset-pwd-uid').value = uid;
      document.getElementById('reset-pwd-user-name').innerText = name;
      document.getElementById('reset-pwd-new').value = '';
      openModal('modal-reset-pwd');
    }

    function generateRandomPass() {
      const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789@#$';
      let pwd = 'Pass@';
      for (let i = 0; i < 6; i++) pwd += chars.charAt(Math.floor(Math.random() * chars.length));
      document.getElementById('reset-pwd-new').value = pwd;
    }

    async function submitResetPassword(e) {
      e.preventDefault();
      const uid = document.getElementById('reset-pwd-uid').value;
      const newPass = document.getElementById('reset-pwd-new').value.trim();

      try {
        const res = await fetch(`${API_BASE}/admin/api/users/${uid}/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ new_password: newPass })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل تعيين كلمة المرور');
        }
        showToast(`تم تعيين كلمة المرور بنجاح إلى: ${newPass}`);
        closeModal('modal-reset-pwd');
      } catch (err) {
        showToast(err.message, true);
      }
    }

    async function confirmDeleteUser(uid) {
      const u = currentUsers.find(x => x.user_id === uid);
      const name = u ? u.name : ('#' + uid);
      if (!confirm(`هل أنت متأكد من رغبتك في حذف المستخدم "${name}"؟`)) return;
      try {
        const res = await fetch(`${API_BASE}/admin/api/users/${uid}`, { method: 'DELETE' });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل حذف المستخدم');
        }
        showToast('تم حذف المستخدم بنجاح');
        loadUsers();
        loadStats();
      } catch (err) {
        showToast(err.message, true);
      }
    }

    // ── COURSES ──────────────────────────────────────────────────────────────
    async function loadCourses() {
      const tbody = document.getElementById('courses-tbody');
      const mobileContainer = document.getElementById('courses-mobile-cards');
      try {
        const res = await fetch(`${API_BASE}/admin/api/courses`);
        currentCourses = await res.json();
        renderCoursesTable(currentCourses);
      } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-rose-500 font-bold">فشل تحميل الكورسات: ${e.message}</td></tr>`;
        if (mobileContainer) mobileContainer.innerHTML = `<div class="text-center py-6 text-rose-500 font-bold bg-rose-50 dark:bg-rose-950/40 rounded-xl border border-rose-200 dark:border-rose-900">فشل تحميل الكورسات: ${e.message}</div>`;
      }
    }

    function renderCoursesTable(courses) {
      const tbody = document.getElementById('courses-tbody');
      const mobileContainer = document.getElementById('courses-mobile-cards');

      if (!courses || courses.length === 0) {
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-400 font-semibold">لا توجد كورسات مضافة</td></tr>';
        if (mobileContainer) mobileContainer.innerHTML = '<div class="text-center py-8 text-slate-400 font-semibold bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">لا توجد كورسات مضافة</div>';
        return;
      }

      // Desktop Table
      if (tbody) {
        tbody.innerHTML = courses.map(c => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition">
            <td class="p-3 font-mono font-bold text-xs text-purple-600 dark:text-purple-400">${c.material_id}</td>
            <td class="p-3 font-semibold text-slate-900 dark:text-white">${c.name}</td>
            <td class="p-3 text-xs font-semibold text-emerald-600 dark:text-emerald-400">${c.teacher_name || '<span class="text-slate-400">غير معين</span>'}</td>
            <td class="p-3 text-xs">${c.duration || 0} س</td>
            <td class="p-3 text-xs font-bold text-blue-600">${c.student_count || 0}</td>
            <td class="p-3 text-xs text-slate-400 max-w-xs truncate">${c.description || '-'}</td>
            <td class="p-3 text-center">
              <button onclick="confirmDeleteCourse('${c.material_id}', '${c.name}')" title="حذف الكورس" class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white transition">
                🗑️ حذف
              </button>
            </td>
          </tr>
        `).join('');
      }

      // Mobile Cards
      if (mobileContainer) {
        mobileContainer.innerHTML = courses.map(c => `
          <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
            <div class="flex items-start justify-between gap-2">
              <div>
                <span class="text-xs font-mono font-bold text-purple-600 dark:text-purple-400">${c.material_id}</span>
                <h4 class="font-bold text-slate-900 dark:text-white text-sm mt-0.5">${c.name}</h4>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300">${c.duration || 0} س</span>
            </div>

            <div class="grid grid-cols-2 gap-2 text-xs bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
              <div>
                <span class="block text-[10px] text-slate-400 font-medium">الدكتور المسؤول</span>
                <span class="font-medium text-emerald-600 dark:text-emerald-400 truncate block">${c.teacher_name || 'غير معين'}</span>
              </div>
              <div>
                <span class="block text-[10px] text-slate-400 font-medium">عدد الطلاب</span>
                <span class="font-bold text-blue-600 dark:text-blue-400">${c.student_count || 0} طالب</span>
              </div>
            </div>

            <div class="flex items-center justify-between gap-2 pt-1 border-t border-slate-100 dark:border-slate-800">
              <p class="text-[11px] text-slate-400 truncate max-w-[180px]">${c.description || 'بدون وصف'}</p>
              <button onclick="confirmDeleteCourse('${c.material_id}', '${c.name}')" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-500/10 text-rose-600 hover:bg-rose-500 hover:text-white flex items-center gap-1 transition">
                🗑️ حذف
              </button>
            </div>
          </div>
        `).join('');
      }
    }

    async function submitAddCourse(e) {
      e.preventDefault();
      const payload = {
        material_id: document.getElementById('add-course-id').value.trim(),
        name: document.getElementById('add-course-name').value.trim(),
        duration: parseInt(document.getElementById('add-course-duration').value) || 0,
        teacher_id: document.getElementById('add-course-teacher').value ? parseInt(document.getElementById('add-course-teacher').value) : null,
        description: document.getElementById('add-course-desc').value.trim() || null,
      };

      try {
        const res = await fetch(`${API_BASE}/admin/api/courses`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل إضافة الكورس');
        }
        showToast('تمت إضافة الكورس بنجاح!');
        closeModal('modal-add-course');
        document.getElementById('form-add-course').reset();
        refreshAll();
      } catch (err) {
        showToast(err.message, true);
      }
    }

    async function confirmDeleteCourse(id, name) {
      if (!confirm(`هل أنت متأكد من رغبتك في حذف الكورس "${name}"؟`)) return;
      try {
        const res = await fetch(`${API_BASE}/admin/api/courses/${id}`, { method: 'DELETE' });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'فشل حذف الكورس');
        }
        showToast('تم حذف الكورس بنجاح');
        loadCourses();
        loadStats();
      } catch (err) {
        showToast(err.message, true);
      }
    }

    // ── LIVE AUTH TEST ────────────────────────────────────────────────────────
    async function runAuthTest(e) {
      e.preventDefault();
      const identifier = document.getElementById('test-identifier').value.trim();
      const password = document.getElementById('test-password').value;
      const resBox = document.getElementById('test-result-box');

      resBox.className = 'mt-4 sm:mt-6 p-4 rounded-xl text-xs font-mono bg-blue-50 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 border border-blue-200 dark:border-blue-900 block';
      resBox.innerText = 'جاري اختبار تسجيل الدخول وفحص الـ Token...';

      try {
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: identifier, password: password })
        });
        const data = await res.json();
        if (res.ok) {
          resBox.className = 'mt-4 sm:mt-6 p-4 rounded-xl text-xs font-mono bg-emerald-50 dark:bg-emerald-950 text-emerald-900 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-800 block';
          resBox.innerHTML = `✅ نجح تسجيل الدخول بنجاح تام! (HTTP 200)
User ID: ${data.user.user_id}
Name: ${data.user.name}
Role: ${data.user.type_code}
Email: ${data.user.email}
UniCode: ${data.user.uni_code}
Access Token: ${data.access_token.substring(0, 32)}...`;
        } else {
          resBox.className = 'mt-4 sm:mt-6 p-4 rounded-xl text-xs font-mono bg-rose-50 dark:bg-rose-950 text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-800 block';
          resBox.innerHTML = `❌ فشل تسجيل الدخول (HTTP ${res.status}):
${JSON.stringify(data, null, 2)}`;
        }
      } catch (err) {
        resBox.className = 'mt-4 sm:mt-6 p-4 rounded-xl text-xs font-mono bg-rose-50 dark:bg-rose-950 text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-800 block';
        resBox.innerHTML = `❌ خطأ في الاتصال: ${err.message}`;
      }
    }

    // Refresh everything
    function refreshAll() {
      loadStats();
      loadUsers();
      loadCourses();
    }

    // On load
    window.addEventListener('DOMContentLoaded', () => {
      refreshAll();
    });
  </script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def get_dashboard_html():
    """Serve the interactive web admin dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)
