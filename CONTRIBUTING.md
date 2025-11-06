# Contributing to Digital Minimalist Lab

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

This project is committed to fostering a welcoming and inclusive community. By participating, you agree to:

- Be respectful and considerate
- Focus on constructive feedback
- Respect different viewpoints and experiences
- Accept responsibility for your actions and words

## Philosophy

This platform is designed with intentionality:

- **Digital agency > Digital addiction**
- **Reflection > Optimization**
- **Structure > Hustle**

**We explicitly avoid:**
- Gamification (no streaks, badges, points)
- Attention economy manipulation
- Addictive UI patterns
- Excessive notifications or emails

All contributions should align with these principles.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the bug report template** if available
3. **Include:**
   - Clear description of the issue
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment details (OS, Python version, Docker, etc.)
   - Relevant logs or error messages

### Suggesting Features

1. **Open a discussion** or issue to discuss first
2. **Explain:**
   - The problem you're solving
   - How it aligns with the project philosophy
   - Potential implementation approach
3. **Wait for feedback** before implementing

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following the coding standards below
4. **Test your changes** locally
5. **Commit with clear messages**:
   ```bash
   git commit -m "Add: brief description of change"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request** with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots if UI changes

## Development Setup

See [README.md](README.md) for detailed setup instructions.

Quick start:
```bash
# Clone your fork
git clone https://github.com/your-username/30-day-cohorts-webapp.git
cd 30-day-cohorts-webapp

# Create .env file
cp .env.example .env

# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py setup_site

# Run tests (when available)
docker-compose exec web python manage.py test
```

## Coding Standards

### Python

- **Style**: Follow PEP 8
- **Formatting**: Use Ruff (`ruff format`)
- **Linting**: Use Ruff (`ruff check`)
- **Line length**: 100 characters
- **Type hints**: Required for all new code
- **Type checking**: Run `pyright` before committing
- **Docstrings**: Use Google-style docstrings for public functions/classes

Example:
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

### Django Best Practices

- **Models**: Use descriptive names, add `help_text` for admin
- **Views**: Keep logic minimal, use forms for validation
- **Templates**: Maintain calm, minimal aesthetic
- **URLs**: Use namespaced URLs (`app_name`)
- **Security**: Always use `@login_required` for protected views, validate all input

### Templates (HTML)

- **Minimal design**: No unnecessary animations or effects
- **Semantic HTML**: Use proper heading hierarchy, ARIA labels
- **Tailwind CSS**: Use utility classes, keep custom CSS minimal
- **HTMX**: Prefer HTMX over custom JavaScript
- **Accessibility**: Ensure keyboard navigation, screen reader support

Example:
```html
<div class="max-w-2xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-semibold mb-4">Settings</h1>
    <form method="post" class="space-y-4">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded">
            Save Changes
        </button>
    </form>
</div>
```

### Git Commit Messages

Use clear, descriptive commit messages:

**Good:**
- `Add: timezone support for daily check-ins`
- `Fix: profile creation signal handler edge case`
- `Update: README with deployment instructions`

**Avoid:**
- `fix stuff`
- `WIP`
- `update`

## Testing

When tests are added:

- Write tests for new features
- Ensure existing tests pass
- Aim for meaningful coverage (not 100% for its own sake)
- Test edge cases and error conditions

```bash
# Run all tests
docker-compose exec web python manage.py test

# Run specific app tests
docker-compose exec web python manage.py test accounts

# Run with coverage (when configured)
docker-compose exec web coverage run --source='.' manage.py test
docker-compose exec web coverage report
```

## Code Quality Tools

Run these commands before committing:

```bash
# Auto-fix formatting and linting issues
make lint-fix

# Or check without modifying files (CI-friendly)
make lint

# Individual commands
make format      # Format code only
make type-check  # Type check only
```

**Using Docker:**

```bash
# Run checks in Docker container
docker-compose exec web make lint
docker-compose exec web make lint-fix
```

**Direct commands (if not using make):**

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check . --fix

# Type check
uv run pyright
```

## Code Review Process

1. **Automated checks** must pass (linting, tests)
2. **Maintainer review** - at least one maintainer reviews
3. **Address feedback** - respond to comments and make changes
4. **Merge** - maintainer merges when approved

### What Reviewers Look For

- Code quality and style
- Alignment with project philosophy
- Security considerations
- Performance implications
- Test coverage
- Documentation updates

## Areas for Contribution

### High Priority

- Email templates (HTML + text versions)
- Rate limiting middleware
- Accessibility improvements
- Test coverage
- Documentation improvements

### Medium Priority

- Protocol content (populate `/accounts/protocol/`)
- Resources content (populate `/accounts/resources/`)
- Management command to create cohorts
- Better error handling and logging
- Monitoring/logging setup

### Low Priority

- Dark mode support
- PWA manifest for mobile
- Cohort comparison analytics
- Anonymous aggregate trends

## Questions?

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and discussions
- **Email**: Contact the project maintainer

## License

By contributing, you agree that your contributions will be licensed under the same AGPL-3.0 license that covers the project.

---

Thank you for contributing! 🎉

