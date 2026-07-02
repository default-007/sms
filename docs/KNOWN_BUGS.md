# Known Bugs & Errors

> Status as of 2026-06-30. All items below were reproduced on a clean checkout
> (Python 3.12, Django 5.2.1, SQLite) by running the app, not inferred from
> reading code. Each entry lists the symptom, how to reproduce, the root cause,
> and a suggested fix.

## ✅ Fixes applied (debugging session)

After the initial audit, the following were fixed and verified — **all 13 module
dashboards now return HTTP 200** (was: login broken + 6 modules 500):

| # | Fix | Files |
|---|-----|-------|
| BUG-0 | Login rate limiter counted GET page loads → users locked out | `accounts/middleware.py` |
| BUG-1 | `teacher_avatar` + 5 badge tags were `@register.filter` used as `{% %}` tags → registered as both filter & simple_tag | `teachers/templatetags/teacher_tags.py` |
| BUG-2 | `get_student_submission` filter used as tag → simple_tag | `assignments/templatetags/assignment_tags.py` |
| BUG-3 | `subjects_base.html` → renamed to `base.html` (+ fixed 1 ref) | `subjects/templates/...` |
| BUG-4 | `finance_dashboard.html` → renamed to `dashboard.html` | `finance/templates/...` |
| BUG-5 | authored the **entire communications UI** — dashboard, notifications, announcements (list/detail/form), messages (list/thread/compose), templates, bulk, quick-send, preferences, analytics, search (16 templates) | `communications/templates/...` |
| BUG-6 | scheduling `academics:term_list` → `academics:term-list` (3 templates) | `scheduling/templates/...` |
| NEW-A | missing `core/base.html` (referenced by finance/scheduling/students) → created passthrough; added `title`/`extra_css` blocks to global base | `core/templates/core/base.html`, `templates/base.html` |
| NEW-B | attendance `select_related("user"/"student__user")` — Student has no `user` FK → removed | `attendance/views.py`, `attendance/services.py` |
| BUG-7 | `finance/models.py` defined every model twice → removed the dead first block (kept `Expense` + the richer second block); `makemigrations --check` reports no changes | `finance/models.py` |
| BUG-8 | academics system check registered on a bound method → wrapped in a plain function | `academics/apps.py` |
| BUG-9 | duplicate `CommunicationPreference` on user create → `get_or_create` (idempotent) | `communications/signals.py` |
| BUG-10 | `clear_model_cache` did `instance.user.pk` on a None user → guard with `getattr(..., None)` | `api/signals.py` |
| BUG-11 | DRF `min_value=0.01` not a Decimal → `Decimal("0.01")` | `finance/api/serializers.py` |
| BUG-13 | `fee_waiver_form.tml` typo → renamed `.html` | `finance/templates/...` |
| NEW-C | `academics:ajax_classes_by_grade` URL didn't exist (view did) → wired both ajax dropdown views into `academics/urls.py` | `academics/urls.py` |
| HYGIENE | 282 committed `*.pyc` files → untracked (`git rm --cached`); `.gitignore` already ignored them | repo-wide |
| NEW-D | `academics/structure` & `section_hierarchy` used `\|div:`/`\|mul:` filters that didn't exist → added an `academics_extras` templatetag library (`mul`/`div`/`sub`) and loaded it | `academics/templatetags/academics_extras.py`, 2 templates |
| NEW-E | `accounts/decorators.py` used bare `redirect("login")`/`redirect("dashboard")` (names are `accounts:login`/`core:dashboard`) → fixed; also let **superusers bypass** the role/permission checks so admin can reach role & user management | `accounts/decorators.py` |
| NEW-F | missing templates `accounts/password_reset_complete.html` and `assignments/help/{index,teacher,student,grading}.html` → authored | `accounts/...`, `assignments/templates/assignments/help/...` |

### Deep crawl result

A full authenticated crawl of **all 341 zero-argument URLs** (every named route
that reverses without parameters) now returns **zero HTTP 500s**. The remaining
non-200 codes are all expected: `302` (login-required POST endpoints / permission
redirects), `401` (token-auth API endpoints), `400` (AJAX endpoints needing query
params), and `405` (POST-only endpoints hit with GET).

After these fixes the dev server starts with **zero** of the previously-noisy
warnings (finance double-registration ×7 and the academics init error are gone),
and `manage.py check` is clean.

**Still outstanding:** BUG-12 (a benign "database access during app
initialization" RuntimeWarning — pre-existing, does not affect functionality).
The communications UI is now complete and verified (all pages render, message
send and announcement create POST flows work end-to-end).

The previous `QUICK_START.md` claimed "System check shows 0 issues. All features
work correctly." That is misleading: `manage.py check` passes, but **6 of the 12
wired web modules return HTTP 500 on their landing page**, and several runtime
errors fire during normal use. This document is the accurate picture.

---

## A. Module landing pages that return HTTP 500

Reproduce: log in as `admin` / `admin123`, then GET each path.

| URL | HTTP | Exception |
|-----|------|-----------|
| `/` (core dashboard) | 200 | ok |
| `/students/` | 200 | ok |
| `/academics/` | 200 | ok |
| `/exams/` | 200 | ok |
| `/teachers/` | **500** | `TemplateSyntaxError` |
| `/subjects/` | **500** | `TemplateDoesNotExist` |
| `/scheduling/` | **500** | `NoReverseMatch` |
| `/assignments/` | **500** | `TemplateSyntaxError` |
| `/finance/` | **500** | `TemplateDoesNotExist` |
| `/communications/` | **500** | `TemplateDoesNotExist` |
| `/accounts/` | 404 | no index route (needs sub-path, e.g. `/accounts/login/`) |
| `/attendance/` | 404 | no index route (needs sub-path) |

### BUG-1 — `/teachers/` — custom tag registered as filter, used as block tag
- **Symptom:** `TemplateSyntaxError: Invalid block tag on line 199: 'teacher_avatar'`
- **File:** `src/teachers/templatetags/teacher_tags.py:192` and
  `src/teachers/templates/teachers/teacher_list.html:199`
- **Root cause:** `teacher_avatar` is declared `@register.filter` but every
  template invokes it as a tag: `{% teacher_avatar teacher 32 %}`. A filter
  cannot be used with `{% ... %}` block syntax.
- **Fix:** change the decorator to `@register.simple_tag`. (Used as a tag in
  ~9 templates, so the tag form is the intended one.)

### BUG-2 — `/assignments/` — same class of error
- **Symptom:** `TemplateSyntaxError: Invalid block tag on line 261: 'get_student_submission'`
- **File:** `src/assignments/templatetags/assignment_tags.py:208` and
  `assignments/templates/assignments/assignment_dashboard.html:382`,
  `submission_list.html:263`
- **Root cause:** `get_student_submission` is `@register.filter` but used as an
  assignment tag: `{% get_student_submission assignment student as x %}`.
- **Fix:** change the decorator to `@register.simple_tag`.

### BUG-3 — `/subjects/` — base template filename mismatch
- **Symptom:** `TemplateDoesNotExist: subjects/base.html`
- **Root cause:** the file on disk is
  `src/subjects/templates/subjects/subjects_base.html` (underscore), but
  templates `{% extends "subjects/base.html" %}`.
- **Fix:** rename `subjects_base.html` → `base.html` (or fix the `extends`).

### BUG-4 — `/finance/` — dashboard template filename mismatch
- **Symptom:** `TemplateDoesNotExist: finance/dashboard.html`
- **File:** `src/finance/views.py:62` sets `template_name = "finance/dashboard.html"`
- **Root cause:** the file on disk is
  `src/finance/templates/finance/finance_dashboard.html` (underscore prefix).
  Several finance templates follow the same `finance_*.html` pattern while views
  expect `*.html`.
- **Fix:** rename to `dashboard.html` or update `template_name`. Audit the other
  `finance_*.html` files for the same mismatch.

### BUG-5 — `/communications/` — module has no templates at all
- **Symptom:** `TemplateDoesNotExist: communications/dashboard.html`
- **Root cause:** `src/communications/` has **no `templates/` directory**
  (`find src/communications -name '*.html'` → 0 files), yet `views.py` references
  ~15 templates (`communications/dashboard.html`, `announcements/list.html`,
  `messages/thread_list.html`, …). The entire module's UI is missing.
- **Fix:** the templates need to be authored; this module is not functional via
  the web UI.

### BUG-6 — `/scheduling/` — broken `{% url %}` reverse
- **Symptom:** `NoReverseMatch: Reverse for 'term_list' not found.`
- **File:** `src/scheduling/templates/scheduling/dashboard.html` (also
  `optimization.html`, `teacher_timetable.html`)
- **Root cause:** templates use `{% url 'term_list' %}`, but no URL pattern named
  `term_list` exists in any app (`grep name="term_list"` → none). It was likely
  meant to be namespaced, e.g. `academics:term_list`, but academics does not
  define that name either.
- **Fix:** add the missing `term_list` URL or correct the reference.

---

## B. Errors that fire at runtime (not caught by `manage.py check`)

### BUG-0 — login rate limiter counts page views, locks users out — ✅ FIXED
- **Symptom:** the login page returns `{"error": "Too many requests."}` (HTTP
  429) and the user cannot log in — often cannot even *see* the login form.
- **File:** `src/accounts/middleware.py` (`RateLimitMiddleware`)
- **Root cause:** `_is_rate_limited` incremented a per-IP counter on **every**
  request to `/accounts/login/`, including `GET` page loads, against a limit of
  **5 requests per 5 minutes** (`RATE_LIMITS["login"]`). Simply opening and
  refreshing the login page a few times exhausted the quota, after which all
  requests (GET and POST) 429'd until the window expired. The `is_superuser`
  bypass never helps here because the user is unauthenticated during login.
  Counter lives in Redis (db 1), so a server restart does not clear it.
- **Fix applied:** rate-limit only `POST` submissions for the `login` and
  `password_reset` limit types; `GET` page loads are no longer counted. The
  brute-force protection is preserved (6th wrong-password POST still 429s) while
  page reloads no longer lock anyone out. Verified: 8 GET reloads → all 200;
  real login → 302 to dashboard.
- **To unblock an already-locked user immediately** (without waiting 5 min):
  ```bash
  python -c "import django;django.setup();from django.core.cache import cache;cache.delete_pattern('*rate_limit*')"
  # (with DJANGO_SETTINGS_MODULE=config.settings, USE_SQLITE=True)
  ```
- **Remaining nit:** for non-API (web) requests the 429 is returned as raw JSON
  instead of an HTML error page — poor UX. Worth replacing with a rendered page
  or a redirect back to the login form with a friendly message.


### BUG-7 — `finance/models.py` defines every model twice
- **Symptom (startup):** 7 × `RuntimeWarning: Model 'finance.<x>' was already
  registered. Reloading models is not advised...` for `feecategory`,
  `feestructure`, `scholarship`, `studentscholarship`, `invoice`, `invoiceitem`,
  `payment`.
- **Root cause:** `src/finance/models.py` is **two concatenated copies**. Classes
  are defined at lines 19–440 (8 models) and again at 442–955 (13 models). The
  first block is dead code, fully shadowed by the second; the overlap of 7 model
  names triggers the warnings. Looks like a bad merge / copy-paste.
- **Fix:** delete the first duplicate block (lines ~17–440). Keep the second
  block — it is the superset (adds `SpecialFee`, `ScholarshipFeeCategory`,
  `FinancialSummary`, `FinancialAnalytics`, `FeeWaiver`). Verify migrations match
  the surviving definitions before removing.

### BUG-8 — academics custom system check is never registered
- **Symptom (startup):** `ERROR Error initializing academics app: 'method' object
  has no attribute 'tags'`
- **File:** `src/academics/apps.py:33` (`AcademicsConfig.ready`)
- **Root cause:**
  ```python
  register(Tags.models, Tags.database)(self.check_academic_structure_consistency)
  ```
  `django.core.checks.register`, given non-callable first args, returns a
  decorator that does `check.tags = tags`. Here `check` is a **bound method**,
  and Python forbids setting attributes on bound methods → `AttributeError`. The
  surrounding `except Exception` swallows it and logs the ERROR, so
  `check_academic_structure_consistency` is **never actually registered**.
- **Fix:** register a module-level function instead of a bound method, e.g.
  `@register(Tags.models, Tags.database)` on a standalone function, or
  `register(check_fn, Tags.models, Tags.database)` where `check_fn` is a plain
  function.

### BUG-9 — duplicate `CommunicationPreference` on user creation
- **Symptom:** `ERROR Failed to create communication preferences for admin:
  UNIQUE constraint failed: communications_communicationpreference.user_id`
  (fires during `create_superuser.py` and any new-user creation).
- **Root cause:** a post-save signal creates a `CommunicationPreference` for the
  new user, but it is created more than once (two signal handlers, or a
  `create()` where a row already exists) and `user_id` is unique.
- **Fix:** use `CommunicationPreference.objects.get_or_create(user=...)` and/or
  remove the duplicate signal handler.

### BUG-10 — AuditLog cache-clear on `None`
- **Symptom:** `WARNING Failed to clear cache for AuditLog: 'NoneType' object has
  no attribute 'pk'` (fires on user creation).
- **Root cause:** a cache-invalidation hook on `AuditLog` dereferences
  `instance.pk` (or a related object) that is `None` in this code path.
- **Fix:** guard for `None` before accessing `.pk`.

### BUG-11 — DRF `min_value` not a Decimal
- **Symptom:** `UserWarning: min_value should be a Decimal instance.`
- **Root cause:** a `DecimalField` serializer (finance API) passes
  `min_value=0`/`min_value=0.0` instead of `Decimal('0.00')`.
- **Fix:** wrap the bound in `Decimal(...)`.

### BUG-12 — DB access during app initialization
- **Symptom:** `RuntimeWarning: Accessing the database during app initialization
  is discouraged...`
- **Root cause:** academics `ready()` path / its custom check touches the DB
  before apps are ready. Tied to BUG-8.

### BUG-13 — typo'd template filename
- **File:** `src/finance/templates/finance/fee_waiver_form.tml`
- **Root cause:** extension is `.tml`, should be `.html`. The fee-waiver form view
  will raise `TemplateDoesNotExist` when reached.

---

## C. Documentation / setup defects

### DOC-1 — `USE_SQLITE` is read from the OS env, not `.env`
- `config/settings/base.py:248` uses `os.environ.get("USE_SQLITE")`, while every
  other setting uses python-decouple's `config()` (which reads `.env`).
  python-decouple does **not** populate `os.environ`, so putting `USE_SQLITE=True`
  only in `.env` has no effect — it must be exported in the shell
  (`export USE_SQLITE=True`). This is a real footgun and should either be made
  consistent (`config("USE_SQLITE", ...)`) or clearly documented.

### DOC-2 — `README.md` references commands/files that don't exist
- `python manage.py generate_sample_data` — does not exist. The real commands are
  per-app: `generate_sample_students`, `generate_sample_exam_data`,
  `generate_sample_scheduling_data`.
- `pip install -r requirements/development.txt` — there is no `requirements/`
  directory; only a single `requirements.txt`.
- `cp .env.example .env` — there is no `.env.example` in the repo.
- README claims Django 4.2+ / Python 3.10+; the project actually pins Django 5.2.1
  and runs on Python 3.12.

### DOC-3 — `requirements.txt` package is wrong
- It pins `django-rest-framework==0.1.0` (an abandoned stub package) **in addition
  to** the correct `djangorestframework==3.15.2`. The stub is unused dead weight
  and should be removed.

---

## D. Stub / non-functional modules (documented as "functional")

These four apps are listed in `INSTALLED_APPS` but are empty 3-line stubs
(default `models.py`/`views.py`/`admin.py`), have no URLs, and are commented out
of `config/urls.py` and `src/api/urls.py`:

| App | State |
|-----|-------|
| `src/library` | empty stub — README/QUICK_START describe full library features that do not exist |
| `src/transport` | empty stub — same |
| `src/reports` | empty stub — no models/views; reporting lives inside other apps |
| `src/analytics` | empty stub — no models/views; analytics live inside other apps |

`attendance` is wired for the web UI but its **API** is commented out in
`src/api/urls.py`.

---

## Quick reproduction recipe

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# .env needs SECRET_KEY, DEBUG, ALLOWED_HOSTS (USE_SQLITE must be a shell var)
export USE_SQLITE=True
python manage.py migrate
python create_superuser.py        # watch BUG-9 / BUG-10 fire here
python manage.py runserver 127.0.0.1:8001 --noreload
# log in as admin/admin123, then curl /teachers/ /subjects/ /scheduling/
#   /assignments/ /finance/ /communications/  → all HTTP 500
```
