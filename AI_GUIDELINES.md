# AI Agent Guidelines

This document provides the essential guidelines for AI agents contributing to this project. Adherence to these principles is mandatory to ensure code quality, data privacy, security, and alignment with our project philosophy.

## Table of Contents

- [Project Philosophy](#project-philosophy)
- [Data Privacy & GDPR Compliance](#data-privacy--gdpr-compliance)
- [Security Best Practices](#security-best-practices)
- [Code Architecture & Design Principles](#code-architecture--design-principles)
- [Django Best Practices](#django-best-practices)
- [Database Design](#database-design)
- [User Experience Guidelines](#user-experience-guidelines)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Common Patterns](#common-patterns)
- [Recommended Project Structure](#recommended-project-structure)
- [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Project Philosophy

### Core Principles

**Digital agency > Digital addiction**  
**Reflection > Optimization**  
**Structure > Hustle**

This platform is intentionally designed to help users reflect and grow, not to maximize engagement or screen time.

### What We Build

✅ **DO:**
- Build calm, minimal interfaces
- Provide structure and accountability
- Support user reflection and growth
- Respect user autonomy and privacy
- Use opt-in patterns for all communications
- Enable user control over their data

❌ **DON'T:**
- Add gamification (streaks, badges, points, leaderboards)
- Use attention economy manipulation tactics
- Create addictive UI patterns
- Send excessive notifications or emails
- Hide user data or make deletion difficult
- Optimize for engagement metrics

### Design Implications

Every feature must align with these principles. When in doubt, choose the option that:
1. Gives users more control
2. Respects their time and attention
3. Supports reflection over reactivity
4. Prioritizes privacy over convenience

---

## Data Privacy & GDPR Compliance

### Fundamental Privacy Requirements

**Privacy is not optional.** All code must respect and protect user data.

### Hard Delete Policy

- **Account deletion is permanent and complete** - this is intentional
- When a user is deleted, ALL related data must be cascade-deleted
- Use `on_delete=models.CASCADE` for all user-related foreign keys
- Never soft-delete user data (no `is_deleted` flags for personal data)

**Example:**
```python
class DailyCheckin(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,  # ✅ Cascade delete
        related_name='daily_checkins'
    )
```

**Anti-pattern:**
```python
class DailyCheckin(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL)  # ❌ Leaves orphaned data
    is_deleted = models.BooleanField(default=False)  # ❌ Soft delete not allowed
```

### User Data Rights

**Every user has these rights:**

1. **Right to Export** - Complete data export in JSON format
   - Must include ALL user data across all apps
   - Must be machine-readable (JSON)
   - Must use ISO date formats
   - See `accounts/views.py:export_user_data()` for reference

2. **Right to Delete** - Permanent account deletion
   - Must require explicit confirmation (`confirm='DELETE'`)
   - Must cascade delete all related data
   - Must log out user after deletion
   - See `accounts/views.py:delete_account()` for reference

3. **Right to Opt-In** - No data collected without consent
   - Email preferences default to `False`
   - Users must explicitly enable reminders
   - No pre-checked boxes

### Data Minimization

**Only collect what you need:**
- Don't collect data "just in case"
- Don't track user behavior beyond what's necessary
- Don't store IP addresses, user agents, or analytics unless essential
- Don't integrate third-party tracking or analytics

### Sensitive Data Handling

**Personal reflection data is highly sensitive:**
- Treat `DailyCheckin.reflection_text` as confidential
- Treat `WeeklyReflection.goal_text` as confidential
- Treat survey responses as confidential
- Never expose personal data in logs
- Never include personal data in error messages

**Safe logging:**
```python
# ✅ Good - no personal data
logger.info(f"User {user.id} completed daily check-in for {cohort.id}")

# ❌ Bad - logs personal data
logger.info(f"User {user.email} wrote: {checkin.reflection_text}")
```

### Privacy by Design Checklist

When adding any new feature, ask:
- [ ] What personal data does this collect?
- [ ] Is this data necessary?
- [ ] Can the user export this data?
- [ ] Will this data be deleted when account is deleted?
- [ ] Does the user consent to this collection?
- [ ] Is this data encrypted in transit (HTTPS)?
- [ ] Are we using proper Django security middleware?

---

## Security Best Practices

### Authentication & Authorization

**Every protected view MUST use `@login_required`:**

```python
from django.contrib.auth.decorators import login_required

@login_required
def daily_checkin(request, cohort_id):
    # View logic
    pass
```

**Always verify user authorization:**

```python
# ✅ Good - verify enrollment before allowing access
enrollment = Enrollment.objects.filter(
    user=request.user, 
    cohort=cohort
).first()

if not enrollment:
    messages.error(request, 'You must be enrolled in this cohort.')
    return redirect('cohorts:cohort_list')
```

**Never trust user input:**

```python
# ✅ Good - use get_object_or_404
cohort = get_object_or_404(Cohort, id=cohort_id)

# ❌ Bad - doesn't handle missing objects
cohort = Cohort.objects.get(id=cohort_id)  # Raises error
```

### Input Validation

**Always validate ALL user input:**

1. **Use Django Forms** - Never manually parse POST data
   ```python
   # ✅ Good
   if request.method == 'POST':
       form = DailyCheckinForm(request.POST)
       if form.is_valid():
           checkin = form.save(commit=False)
           # ... additional logic
   ```

2. **Use Model Validators** - Enforce constraints at the model level
   ```python
   from django.core.validators import MinValueValidator, MaxValueValidator
   
   mood_1to5 = models.IntegerField(
       validators=[MinValueValidator(1), MaxValueValidator(5)]
   )
   ```

3. **Sanitize Text Input** - Django templates auto-escape by default (keep it that way)

### CSRF Protection

**Never disable CSRF protection:**

```django
<!-- ✅ Good - always include csrf_token -->
<form method="post">
    {% csrf_token %}
    {{ form.as_p }}
</form>
```

### SQL Injection Prevention

**Always use Django ORM - never raw SQL:**

```python
# ✅ Good - parameterized queries via ORM
checkins = DailyCheckin.objects.filter(
    user=request.user,
    cohort=cohort
)

# ❌ Bad - raw SQL opens SQL injection risk
cursor.execute(f"SELECT * FROM checkins WHERE user_id = {user.id}")
```

### Password & Secrets Management

- **Never commit secrets** - use environment variables
- **Never log secrets** - sanitize logs
- **Use Django's password validators** - already configured
- **Rotate SECRET_KEY** in production

### Rate Limiting

**TODO: Implement rate limiting middleware**

When implementing, protect these endpoints:
- Login/signup
- Password reset
- Form submissions
- Data exports

---

## Code Architecture & Design Principles

### Single Responsibility Principle (SRP)

**Each function/class should do ONE thing well:**

```python
# ✅ Good - single responsibility
def get_user_today(user):
    """Get today's date in user's timezone."""
    from accounts.models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()

# ❌ Bad - multiple responsibilities
def process_checkin(request, cohort_id):
    # Gets date, validates enrollment, creates checkin, sends email
    # ... 200 lines of code doing 5 different things
```

### Function Design

**Keep functions focused and readable:**

- **Length**: Max 50 lines (prefer 20-30)
- **Parameters**: Max 4 parameters
- **Return**: Single, predictable return type
- **Docstrings**: Include for public functions

**Example:**
```python
def get_user_today(user):
    """
    Get today's date in user's timezone.
    
    Args:
        user: Django User instance with associated UserProfile
        
    Returns:
        datetime.date: Today's date in user's timezone
    """
    from accounts.models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()
```

### Defensive Programming

**Always assume things might not exist:**

```python
# ✅ Good - defensive, handles missing profile
profile, created = UserProfile.objects.get_or_create(user=request.user)

# ❌ Bad - assumes profile exists
profile = request.user.profile  # May raise exception
```

**Check enrollment before operations:**

```python
# ✅ Good - verify first
enrollment = Enrollment.objects.filter(
    user=request.user, 
    cohort=cohort
).first()

if not enrollment:
    messages.error(request, 'You must be enrolled in this cohort.')
    return redirect('cohorts:cohort_list')
```

### DRY (Don't Repeat Yourself)

**Extract common patterns into reusable functions:**

```python
# ✅ Good - reusable function
def get_user_today(user):
    """Get today's date in user's timezone."""
    from accounts.models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()

# Used in multiple views
today = get_user_today(request.user)
```

### Separation of Concerns

**Organize code by responsibility:**

- **Models** - Data structure and business logic
- **Views** - Request handling and response
- **Forms** - Input validation
- **Templates** - Presentation
- **Signals** - Side effects and hooks

### Type Hints

**Use type hints for all function signatures:**

```python
from typing import Optional
from datetime import date
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.models import AbstractUser

@login_required
def view_name(request: HttpRequest, id: int) -> HttpResponse:
    """View function with type hints."""
    return render(request, 'template.html')

def helper(user: AbstractUser, obj: Model) -> Optional[Model]:
    """Helper with optional return type."""
    return Model.objects.filter(user=user).first()
```

**Guidelines:**
- Type annotate all function parameters and return types
- Use `Optional[T]` for values that can be None
- Use `AbstractUser` instead of `User` for compatibility
- Import types from `typing` module
- Use `HttpRequest` and `HttpResponse` for Django views
- Use `forms.ModelForm` (without generic syntax for compatibility)
- Run `pyright` to verify types

---

## Django Best Practices

### Models

**Follow these patterns for models:**

```python
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class DailyCheckin(models.Model):
    """
    Daily check-in with 5-step reflection.
    
    Tracks mood, digital satisfaction, screen time, proud moments,
    and daily reflections for cohort participants.
    """
    # Foreign keys with CASCADE delete
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='daily_checkins'
    )
    cohort = models.ForeignKey(
        'cohorts.Cohort', 
        on_delete=models.CASCADE,
        related_name='daily_checkins'
    )
    
    # Fields with validation
    mood_1to5 = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How do you feel today? (1-5)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'cohort', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', 'cohort', 'date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.cohort.name} - {self.date}"
```

**Key points:**
- Always use `on_delete=models.CASCADE` for user-related FKs
- Add `help_text` for clarity in admin
- Use `related_name` for reverse lookups
- Add validators at the model level
- Include timestamps (`created_at`, `updated_at`)
- Use `Meta` for constraints, ordering, and indexes
- Write descriptive `__str__` methods

### Views

**View structure pattern:**

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def view_name(request, id):
    """Short description of what this view does."""
    
    # 1. Get objects (with 404 handling)
    object = get_object_or_404(Model, id=id)
    
    # 2. Verify authorization
    if not user_has_access(request.user, object):
        messages.error(request, 'You do not have access.')
        return redirect('app:view_name')
    
    # 3. Handle POST
    if request.method == 'POST':
        form = Form(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            messages.success(request, 'Success message')
            return redirect('app:view_name')
    else:
        form = Form()
    
    # 4. Render template
    return render(request, 'app/template.html', {
        'form': form,
        'object': object,
    })
```

### URLs

**Use namespaced URLs:**

```python
# app/urls.py
app_name = 'checkins'

urlpatterns = [
    path('daily/<int:cohort_id>/', daily_checkin, name='daily_checkin'),
]

# In templates and views
reverse('checkins:daily_checkin', args=[cohort.id])
```

### Forms

**Use Django Forms for all input:**

```python
from django import forms
from .models import DailyCheckin

class DailyCheckinForm(forms.ModelForm):
    class Meta:
        model = DailyCheckin
        fields = [
            'mood_1to5',
            'digital_satisfaction_1to5',
            'screentime_min',
            'proud_moment_text',
            'digital_slip_text',
            'reflection_text',
        ]
        widgets = {
            'reflection_text': forms.Textarea(attrs={'rows': 4}),
        }
```

### Signals

**Use signals for side effects:**

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created."""
    if created:
        UserProfile.objects.create(user=instance)
```

**When to use signals:**
- Creating related objects (e.g., UserProfile on User creation)
- Cascading updates
- Sending notifications
- Logging events

**When NOT to use signals:**
- Complex business logic (use services/managers)
- Operations that might fail (handle explicitly)

---

## Database Design

### Foreign Keys

**Always specify `on_delete` behavior:**

```python
# ✅ Good - explicit cascade for user data
user = models.ForeignKey(User, on_delete=models.CASCADE)

# ✅ Good - protect for reference data
cohort = models.ForeignKey(Cohort, on_delete=models.PROTECT)

# ❌ Bad - implicit behavior
user = models.ForeignKey(User)
```

**When to use each:**
- `CASCADE` - User data that should be deleted with user
- `PROTECT` - Prevent deletion if references exist
- `SET_NULL` - Rarely (conflicts with GDPR hard delete)
- `SET_DEFAULT` - Rarely used

### Unique Constraints

**Prevent duplicate data:**

```python
class Meta:
    unique_together = ['user', 'cohort', 'date']  # One check-in per day
```

### Indexes

**Add indexes for frequently queried fields:**

```python
class Meta:
    indexes = [
        models.Index(fields=['user', 'cohort', 'date']),
    ]
```

**Index when:**
- Filtering frequently (WHERE clauses)
- Joining tables (foreign keys)
- Ordering results (ORDER BY)

### Timestamps

**Always include audit timestamps:**

```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

---

## User Experience Guidelines

### Calm, Minimal Design

**UI principles:**
- Clean, uncluttered layouts
- Generous whitespace
- Clear typography hierarchy
- Minimal animations (if any)
- No popups or modals (unless critical)

### Messaging

**Use Django messages framework:**

```python
from django.contrib import messages

# Success
messages.success(request, 'Daily check-in completed!')

# Info
messages.info(request, 'You have already completed today\'s check-in.')

# Error
messages.error(request, 'You must be enrolled in this cohort.')

# Warning
messages.warning(request, 'Your session is about to expire.')
```

### Accessibility

**Ensure accessible HTML:**
- Semantic HTML elements (`<nav>`, `<main>`, `<article>`)
- Proper heading hierarchy (`<h1>` → `<h2>` → `<h3>`)
- ARIA labels where needed
- Keyboard navigation support
- Sufficient color contrast

### Email Communication

**Email guidelines:**
- Opt-in only (default to `False`)
- Clear unsubscribe links
- HTML + text versions
- Respectful tone
- No urgency tactics ("Last chance!", "Don't miss out!")

---

## Testing & Quality Assurance

### Writing Tests is Mandatory

**All new functionality, bug fixes, or changes must include tests.** This is not optional. Contributions without tests will be rejected.

### What to Test

Focus on testing the most critical paths:
- **Authentication & Authorization**: Can a user access data they shouldn't?
- **Data Privacy**: Does deleting a user cascade correctly? Can a user export their data?
- **Business Logic**: Does the feature work as expected under normal conditions?
- **Input Validation**: Does the application handle invalid or malicious input gracefully?
- **Edge Cases**: What happens with empty inputs, zero values, or unexpected state?

### Test Structure Example

Use Django's `TestCase` to write clear, isolated tests.

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from .models import DailyCheckin
from cohorts.models import Cohort, Enrollment

User = get_user_model()

class DailyCheckinTestCase(TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.cohort = Cohort.objects.create(
            name='Test Cohort',
            start_date='2024-01-01',
            end_date='2024-01-30'
        )
        Enrollment.objects.create(user=self.user, cohort=self.cohort)

    def test_user_can_create_daily_checkin(self):
        """Ensures a user can create a valid daily check-in."""
        checkin_count = DailyCheckin.objects.count()
        response = self.client.post(
            reverse('checkins:daily_checkin', args=[self.cohort.id]),
            {'mood_1to5': 4, 'reflection_text': 'A good day.'}
        )
        self.assertEqual(DailyCheckin.objects.count(), checkin_count + 1)
        self.assertRedirects(response, expected_url_or_pattern)

    def test_user_cannot_create_duplicate_checkin(self):
        """Ensures a user cannot submit more than one check-in per day."""
        # Create the first check-in successfully
        DailyCheckin.objects.create(user=self.user, cohort=self.cohort, date='2024-01-01', mood_1to5=4)
        
        # Attempting to create a second one for the same day should fail at the database level
        with self.assertRaises(IntegrityError):
            DailyCheckin.objects.create(user=self.user, cohort=self.cohort, date='2024-01-01', mood_1to5=3)
```

---

## Common Patterns

### Pattern: Centralized Utility Functions

To avoid code duplication (DRY principle), place shared helper functions in a central `utils.py` file within a relevant app (e.g., `cohorts/utils.py`).

**`cohorts/utils.py`:**
```python
import pytz
from django.utils import timezone
from accounts.models import UserProfile

def get_user_today(user):
    """
    Get today's date in the user's timezone.
    
    Handles creating a UserProfile if it doesn't exist.
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    user_tz = pytz.timezone(profile.timezone)
    return timezone.now().astimezone(user_tz).date()
```

### Pattern: Enrollment Verification Decorator

Instead of repeating enrollment checks in every view, use a decorator. This is cleaner and less error-prone.

**`cohorts/decorators.py`:**
```python
from functools import wraps
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import Cohort, Enrollment

def user_is_enrolled(view_func):
    @wraps(view_func)
    def _wrapped_view(request, cohort_id, *args, **kwargs):
        cohort = get_object_or_404(Cohort, id=cohort_id)
        is_enrolled = Enrollment.objects.filter(user=request.user, cohort=cohort).exists()
        
        if not is_enrolled:
            messages.error(request, "You are not enrolled in this cohort.")
            return redirect('cohorts:cohort_list')
            
        return view_func(request, cohort_id, *args, **kwargs)
    return _wrapped_view
```

**Usage in `checkins/views.py`:**
```python
from cohorts.decorators import user_is_enrolled

@login_required
@user_is_enrolled
def daily_checkin(request, cohort_id):
    # No need to check enrollment here, the decorator handles it.
    cohort = get_object_or_404(Cohort, id=cohort_id)
    # ... view logic ...
```

### Pattern: Prevent Duplicate Daily Submissions

```python
# Check if already completed
existing = Model.objects.filter(
    user=request.user,
    cohort=cohort,
    date=today
).first()

if existing:
    messages.info(request, 'You have already completed this.')
    return redirect('app:view_name')
```

### Pattern: Form with User Assignment

```python
if request.method == 'POST':
    form = Form(request.POST)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.cohort = cohort
        instance.date = today
        instance.save()
        messages.success(request, 'Success!')
        return redirect('app:view_name')
```

---

## Recommended Project Structure

For clarity and maintainability, follow this structure for shared code:

```
core/
├── utils.py         # Global, project-wide utilities
└── management/

cohorts/
├── utils.py         # Utilities specific to cohorts/enrollment
└── decorators.py    # Authorization decorators like @user_is_enrolled

```

---

## Anti-Patterns to Avoid

### ❌ Soft Deletes for User Data

```python
# ❌ BAD - conflicts with GDPR
class DailyCheckin(models.Model):
    is_deleted = models.BooleanField(default=False)
    
    def delete(self):
        self.is_deleted = True
        self.save()
```

### ❌ Exposing Personal Data

```python
# ❌ BAD - logs personal reflections
logger.info(f"Reflection: {checkin.reflection_text}")

# ❌ BAD - exposes personal data in error message
raise ValueError(f"Invalid reflection from {user.email}: {text}")
```

### ❌ Missing Authorization Checks

```python
# ❌ BAD - no enrollment check
@login_required
def daily_checkin(request, cohort_id):
    cohort = get_object_or_404(Cohort, id=cohort_id)
    # Anyone logged in can submit for any cohort!
```

### ❌ Raw SQL Queries

```python
# ❌ BAD - SQL injection risk
cursor.execute(f"SELECT * FROM checkins WHERE user_id = {user_id}")
```

### ❌ Disabling CSRF

```python
# ❌ BAD - removes CSRF protection
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def my_view(request):
    pass
```

### ❌ God Functions

```python
# ❌ BAD - does too many things
def process_everything(request, cohort_id):
    # 300 lines of code doing 10 different things
    pass
```

### ❌ Hardcoded Secrets

```python
# ❌ BAD - secret in code
STRIPE_SECRET_KEY = 'sk_live_abc123...'

# ✅ GOOD - use environment variables
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
```

### ❌ Gamification Elements

```python
# ❌ BAD - goes against project philosophy
class UserProfile(models.Model):
    streak_days = models.IntegerField(default=0)
    total_points = models.IntegerField(default=0)
    badges = models.JSONField(default=list)
```

---

## Questions?

When in doubt:
1. Check existing code for patterns
2. Refer to `CONTRIBUTING.md` for contribution guidelines
3. Refer to `README.md` for project overview
4. Prioritize user privacy and autonomy
5. Choose the simpler, clearer solution

**Remember**: This platform exists to help users reclaim their attention and autonomy. Every line of code should serve that mission.
