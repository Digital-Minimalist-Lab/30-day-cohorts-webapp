# AI Agent Guidelines

Guidelines for AI agents contributing to this Django web application for running structured 30-day digital declutter cohorts.

---

## Project Overview

**Purpose**: Help users reclaim their time and attention through structured 30-day digital declutter programs with daily reflections and surveys.

**Tech Stack**:
- Django 5.x with PostgreSQL
- Pico CSS (classless/semantic styling)
- HTMX for interactivity
- Chart.js for data visualization
- Django-allauth (email-only, passwordless via magic link)
- Stripe (optional payments)
- Django Q2 for background tasks and email queuing

**Core Apps**:
- `accounts/` - User profiles, settings, GDPR features
- `cohorts/` - Cohort management, enrollment, dashboard, task scheduling
- `surveys/` - Survey definitions and dynamic form generation
- `core/` - Landing page, static content
- `payments/` - Stripe integration

---

## How It Works

### The 30-Day Program

Users join **cohorts** (time-bound groups) that run for 30 days. Each cohort has:
- **Entry survey**: Baseline assessment before starting
- **Daily check-ins**: Brief reflections (~2 min) on mood, screen time, and wins
- **Weekly reflections**: Deeper reflection on progress and intentions
- **Exit survey**: Final assessment to measure change

### User Journey

1. **Sign up** → Create account (email-only, passwordless via magic link)
2. **Join cohort** → Complete entry survey → Pay (if applicable) → Enrollment confirmed
3. **Daily participation** → Dashboard shows today's pending tasks
4. **Complete program** → Exit survey → See progress

### Key Domain Concepts

- **Cohort**: A 30-day program instance with start/end dates and enrolled users
- **Enrollment**: User's membership in a cohort (status: pending → paid/free)
- **TaskScheduler**: Defines when surveys appear (ONCE, DAILY, or WEEKLY frequency)
- **Survey**: A form with questions (entry survey, daily check-in, weekly reflection)
- **UserSurveyResponse**: User's completed submission for a specific task instance

### Task Scheduling System

Tasks are generated dynamically based on `TaskScheduler` configurations:

- **ONCE**: Single occurrence (e.g., entry survey on day 1, exit survey on day 30)
- **DAILY**: Every day during the cohort (e.g., daily check-in)
- **WEEKLY**: Once per week on a specific day (e.g., weekly reflection on Sundays)

The dashboard calls `get_user_tasks(user, cohort, today)` to show pending tasks.

---

## Core Philosophy

**Digital agency > Digital addiction**
**Reflection > Optimization**
**Structure > Hustle**

### Do
- Build calm, minimal interfaces
- Support user reflection and growth
- Respect user autonomy and privacy
- Use opt-in patterns for all communications

### Don't
- Add gamification (streaks, badges, points, leaderboards)
- Use attention economy manipulation tactics
- Create addictive UI patterns
- Optimize for engagement metrics

---

## Frontend Patterns

### 1. Semantic HTML First

Use proper HTML elements for structure—avoid div-soup:

```html
<!-- ✅ Good -->
<header>
    <h1>Page Title</h1>
</header>
<main class="container">
    <section>
        <h2>Section Title</h2>
        <article>...</article>
    </section>
</main>
<footer>...</footer>

<!-- ❌ Bad -->
<div class="header">
    <div class="title">Page Title</div>
</div>
```

**Heading hierarchy**: Always maintain proper hierarchy (`h1` → `h2` → `h3`). Never skip levels.

### 2. Pico CSS Framework

Pico CSS is our primary styling framework. **Prefer classless/semantic patterns over custom classes.**

```html
<!-- ✅ Good - Pico styles buttons automatically -->
<button type="submit">Save</button>
<button type="submit" class="secondary">Cancel</button>
<a href="/dashboard" role="button">Continue</a>

<!-- ❌ Bad - unnecessary custom class -->
<button class="btn-primary" type="submit">Save</button>
```

**Add classes only when needed** for specific styling beyond Pico's defaults (e.g., `.card`, `.hero`).

### 3. Template Inheritance

```
base_nocontent.html     # Root: HTML head, Pico CSS, HTMX, toast notifications
    └── base.html       # Adds nav + main container
        └── page.html   # Individual pages
```

**Standard page structure**:
```django
{% extends 'base.html' %}

{% block title %}Page Title - Intentional Tech{% endblock %}

{% block content %}
<header>
    <h1>Page Title</h1>
</header>

<section>
    <h2>Section</h2>
    <p>Content...</p>
</section>
{% endblock %}
```

### 4. CSS Styling Hierarchy

Follow this priority order—avoid adding classes unless necessary:

1. **Semantic HTML first** - Let Pico CSS style elements automatically
2. **Pico's built-in modifiers** - Use `role="button"`, `class="secondary"`, `class="contrast"`
3. **BEM component classes** - Create new clases only when needed. This should be rare unless there is a new component.
4. **Avoid utility classes** - Don't create or use `.mb-2`, `.text-center`, `.flex`, etc.

Custom styles live in `static/base.css`:
- Use **BEM naming** for components. Dashes (`-`) for modifiers, underscores (`_`) for children
- Use **Pico CSS variables** for theming: `--pico-primary`, `--pico-border-color`
- Keep custom CSS minimal—prefer Pico's defaults

---

## Django Patterns

### 1. Views

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def view_name(request, id):
    """Short description."""
    # 1. Get objects (with 404 handling)
    obj = get_object_or_404(Model, id=id)

    # 2. Handle POST
    if request.method == 'POST':
        form = Form(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            messages.success(request, 'Success!')
            return redirect('app:view_name')
    else:
        form = Form()

    # 3. Render template
    return render(request, 'app/template.html', {'form': form, 'obj': obj})
```

### 2. Models

```python
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Example(models.Model):
    """Model docstring."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='examples')
    value = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'date']
        ordering = ['-created_at']
```

**Key points**:
- `on_delete=models.CASCADE` for user data (GDPR compliance)
- Always include `created_at` and `updated_at`
- Use validators at model level
- Add `related_name` for reverse lookups

### 3. URLs (Namespaced)

```python
# app/urls.py
app_name = 'cohorts'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
]

# In templates
{% url 'cohorts:dashboard' %}
```

### 4. Forms

Always use Django forms—never manually parse POST data:

```python
class ExampleForm(forms.ModelForm):
    class Meta:
        model = Example
        fields = ['field1', 'field2']
        widgets = {'field2': forms.Textarea(attrs={'rows': 4})}
```

### 5. Decorators

Use `@enrollment_required` for cohort-protected views:

```python
from django.contrib.auth.decorators import login_required
from cohorts.decorators import enrollment_required

@login_required
@enrollment_required
def daily_checkin(request, cohort_id, context):
    cohort = context['cohort']
    enrollment = context['enrollment']
    # ...
```

### 6. Template Overrides

We prefer **template-based customization** over database configuration for UI variations. This follows the django-allauth pattern where you override templates by creating files with specific names.

**Template resolution order**:
```
templates/
  account/
    login.html                        # Overrides allauth's default login
    signup.html                       # Overrides allauth's default signup
  emails/
    task_reminder.html                # Custom email template
  surveys/
    views/
      default/
        survey_form.html              # Default survey template
      exit-survey_survey_form.html    # Override for "exit-survey" slug
```

**Naming convention for survey overrides**: `{survey-slug}_survey_form.html`

**Benefits**:
- No database entries needed for simple UI changes
- Version controlled with code
- Easy to see what's customized
- Follows Django's template resolution order

**When to use**:
- Customizing allauth authentication pages
- Survey-specific layouts (by slug)
- Email templates
- Any UI that varies by type/slug but not by user input

---

## Privacy & Security

### GDPR Requirements

1. **Hard delete only** - No soft deletes for user data
2. **Cascade delete** - Use `on_delete=models.CASCADE` for all user FKs
3. **Data export** - Users can export all their data as JSON
4. **Opt-in defaults** - Email preferences default to `False`

### Safe Logging

```python
# ✅ Good
logger.info(f"User {user.id} completed check-in for cohort {cohort.id}")

# ❌ Bad - exposes personal data
logger.info(f"User {user.email} wrote: {checkin.reflection_text}")
```

### Security Checklist

- Always use `@login_required` for protected views
- Always use `{% csrf_token %}` in forms
- Always use `get_object_or_404()` for lookups
- Never use raw SQL queries
- Never commit secrets to code

---

## Testing

### Tests Are Mandatory

All new features, bug fixes, and changes **must include tests**. PRs without tests will not be merged.

### What to Test

1. **Views**: Authentication, authorization, form handling, redirects
2. **Models**: Validation, constraints, cascade deletes (GDPR compliance)
3. **Business logic**: Task generation, enrollment flow, survey submissions
4. **Edge cases**: Empty inputs, invalid data, duplicate submissions, missing objects

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test cohorts

# Run specific test class
python manage.py test cohorts.test_onboarding.OnboardingFlowTests
```

### Test Pattern

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from cohorts.models import Cohort, Enrollment

User = get_user_model()

class ExampleTestCase(TestCase):
    def setUp(self):
        """Create test fixtures."""
        self.user = User.objects.create_user(email='test@example.com', password='testpass')
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date='2024-01-01',
            end_date='2024-01-30'
        )

    def test_authenticated_user_can_access_view(self):
        """Test that logged-in users can access the page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('cohorts:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_user_redirected(self):
        """Test that anonymous users are redirected to login."""
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(response, '/accounts/login/?next=/accounts/profile/')
```

---

## Common Pitfalls

### Timezone Handling

Always use `get_user_today()` for user-facing dates—never `date.today()`:

```python
from cohorts.utils import get_user_today

# ✅ Good - respects user's timezone
today = get_user_today(request.user)

# ❌ Bad - uses server timezone
today = date.today()
```

### UserProfile Access

Never assume profile exists—always use `get_or_create`:

```python
from accounts.models import UserProfile

# ✅ Good - handles missing profile
profile, _ = UserProfile.objects.get_or_create(user=request.user)

# ❌ Bad - may raise exception
profile = request.user.userprofile
```

### Enrollment Checks

Always verify enrollment before allowing cohort actions:

```python
# Use the decorator for views
@login_required
@enrollment_required
def cohort_view(request, cohort_id, context):
    cohort = context['cohort']  # Provided by decorator
    ...

# Or check manually
enrollment = Enrollment.objects.filter(user=request.user, cohort=cohort).first()
if not enrollment or enrollment.status == 'pending':
    messages.error(request, "You are not enrolled in this cohort.")
    return redirect('cohorts:dashboard')
```

---

## Background Tasks & Email

### Django Q2

Background tasks (email sending) use Django Q2 with database backend:

- Emails are automatically queued via `django_q2_email_backend`
- Run the worker: `python manage.py qcluster`

### Email Reminders

Daily task reminders are sent via management command:

```bash
# Send reminders (runs hourly, sends at 10am user's local time)
python manage.py send_task_reminders

# Dry run (preview without sending)
python manage.py send_task_reminders --dry-run
```

User preferences control email delivery:
- `email_daily_reminder`: Controls task reminder emails
- All preferences default to `False` (opt-in only)

---

## Quick Reference

### File Locations
- Templates: `templates/{app_name}/`
- Static CSS: `static/base.css`
- Views: `{app}/views.py` or `{app}/views/`
- Utils: `{app}/utils.py`
- Decorators: `cohorts/decorators.py`

### Common Imports
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from cohorts.decorators import enrollment_required
```

### Django Messages
```python
messages.success(request, 'Action completed!')
messages.error(request, 'Something went wrong.')
messages.info(request, 'For your information.')
messages.warning(request, 'Please be aware.')
```

---

## AI Agent Notes

AI agents working on this project should maintain `ai/NOTES.md` to record useful context and discoveries.

### What to Document

- Non-obvious patterns discovered in the codebase
- Common debugging solutions
- Quirks or edge cases encountered
- Useful context that isn't appropriate for code comments
- Temporary notes about ongoing work or investigations

### Format

Use markdown with dated entries or clear section headers:

```markdown
## 2024-01-15: Task Scheduler Edge Cases

Discovered that TaskScheduler with WEEKLY frequency and is_cumulative=False
only shows the most recent week's task, not all past weeks. This is intentional
to avoid overwhelming users with backlog.

## Common Issues

### UserProfile Missing
Always use `UserProfile.objects.get_or_create(user=user)` - profiles are created
via signal but may not exist for users created in tests or migrations.
```

### When to Update

Update `ai/NOTES.md` whenever you discover something that would be helpful for future AI agents (or developers) to know. This creates a living document that accumulates institutional knowledge.
