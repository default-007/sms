# Module Status & Accurate Setup

> A ground-truth companion to `README.md` / `QUICK_START.md`, which describe an
> aspirational feature set. This file records what is actually wired and working
> as of 2026-06-30, verified by running the app. For the bugs referenced here see
> [`KNOWN_BUGS.md`](./KNOWN_BUGS.md).

## Verified working setup (clean checkout)

The system runs on **Python 3.12 + Django 5.2.1 + SQLite**. There is no `venv`,
`.env`, `.env.example`, or `db.sqlite3` in the repo — all must be created.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt          # single file; there is no requirements/ dir

# Create .env (SECRET_KEY/DEBUG/ALLOWED_HOSTS are required by base.py at import time)
cat > .env <<'EOF'
DEBUG=True
SECRET_KEY=<any-50-char-random-string>
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EOF

# USE_SQLITE is read from the OS env, NOT from .env (see KNOWN_BUGS DOC-1)
export USE_SQLITE=True

python manage.py migrate                 # 77 migrations, builds db.sqlite3
python create_superuser.py               # admin / admin123  (logs BUG-9/BUG-10, still succeeds)
python manage.py runserver 127.0.0.1:8000
```

`manage.py check` reports 0 issues — but that does **not** mean the UI works; see
module table below.

## Settings selection

- `manage.py` sets `DJANGO_SETTINGS_MODULE=config.settings` (the package).
- `config/settings/__init__.py` imports `base`, then chooses `development`,
  `production`, or `testing`. With the default value it falls through to
  **development** (DEBUG=True, console email, debug-toolbar, django-extensions).
- DB: `base.py` switches to SQLite only when the **shell** env var
  `USE_SQLITE=true` is set; otherwise it expects PostgreSQL via `config()`.

## Web module status (logged in as admin)

After the debugging session, **all module dashboards return HTTP 200**. The
table shows the original audit result and the current state.

| Module | URL | Original | Now | Notes |
|--------|-----|----------|-----|-------|
| core / dashboard | `/` | ✅ 200 | ✅ 200 | |
| students | `/students/` | ✅ 200 | ✅ 200 | |
| academics | `/academics/` | ✅ 200 | ✅ 200 | |
| exams | `/exams/` | ✅ 200 | ✅ 200 | |
| accounts | `/accounts/login/` | ✅ login | ✅ login | `/accounts/` index is 404 |
| attendance | `/attendance/dashboard/` | ❌ (404 at root) | ✅ 200 | fixed `select_related("user")`; `/attendance/` root still has no index |
| teachers | `/teachers/` | ❌ 500 | ✅ 200 | fixed tag-as-filter |
| subjects | `/subjects/` | ❌ 500 | ✅ 200 | fixed template name |
| scheduling | `/scheduling/` | ❌ 500 | ✅ 200 | fixed `term-list` reverse |
| assignments | `/assignments/` | ❌ 500 | ✅ 200 | fixed tag-as-filter |
| finance | `/finance/` | ❌ 500 | ✅ 200 | fixed template name + `core/base.html` |
| communications | `/communications/` | ❌ 500 | ✅ 200 | dashboard authored; rest of UI still missing |

See [`KNOWN_BUGS.md`](./KNOWN_BUGS.md) for the per-bug detail and what remains.
Deeper (non-landing) pages may still hit latent issues — e.g.
`scheduling/timetable_list.html` references a `academics:ajax_classes_by_grade`
URL that doesn't exist yet.

## Stub modules (in INSTALLED_APPS, otherwise empty)

`library`, `transport`, `reports`, `analytics` are 3-line default stubs with no
models, views, URLs, or API. They are commented out of both `config/urls.py` and
`src/api/urls.py`. README/QUICK_START describe library & transport features that
do not exist in code.

## REST API

Mounted at `/api/v1/`. `/api/docs/` (Swagger) and `/api/redoc/` work. Note the
project ships **two** schema generators — drf-yasg (`/api/docs/` in
`config/urls.py`) and drf-spectacular (`/api/v1/docs/` in `src/api/urls.py`).

Wired API routers: `auth`, `academics`, `students`, `teachers`, `subjects`,
`scheduling`, `assignments`, `exams`, `finance`, `communications`, `core`.
Commented out: `attendance`, `library`, `transport`, `analytics`, `reports`.
Spot check: `/api/v1/academics/` → 200, `/api/v1/finance/` → 200.

## Custom management commands (undocumented)

```
accounts:    cleanup_accounts, create_default_roles,
             create_superuser_with_roles, import_users, user_statistics
core:        setup_academic_year
students:    generate_sample_students, generate_registration_numbers,
             student_data_cleanup, student_operations
teachers:    calculate_teacher_analytics, data_migration_helpers,
             migrate_teacher_data, optimize_teacher_database
subjects:    calculate_curriculum_analytics
exams:       calculate_exam_analytics, cleanup_exam_data,
             generate_exam_statistics, generate_sample_exam_data
finance:     calculate_financial_analytics
scheduling:  generate_sample_scheduling_data, generate_timetable,
             optimize_timetable
```

> README references `generate_sample_data` and `calculate_analytics` — neither
> exists. Use the per-app commands above.
