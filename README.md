# Digital Minimalist Lab - 30-Day Cohort Platform

A self-hostable Django web application for running structured 30-day digital declutter cohorts.

## Table of Contents

- [Philosophy](#philosophy)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start-local-development)
- [Deployment](#deployment-flyio)
- [Admin Tasks](#admin-tasks)
- [Privacy & GDPR](#privacy--gdpr-compliance)
- [Open Source & Self-Hosting](#open-source--self-hosting)
- [Development](#development)
- [Contributing](#contributing)
- [Support & Community](#support--community)
- [License](#license)

---

## Philosophy

**Digital agency > Digital addiction.**  
**Reflection > Optimization.**  
**Structure > Hustle.**

This platform provides accountability and structure for the 30-day digital declutter, without gamification or attention economy manipulation.

---

## Features

- **Entry & Exit Surveys**: Establish baseline and measure progress
- **Daily 5-Step Reflection**: Mood, digital satisfaction, screen time, proud moments, and daily reflection
- **Weekly Intentions**: Goal setting every 7 days with catch-up logic
- **Privacy-First Design**: GDPR-compliant, EU data residency, hard account deletion
- **Calm UX**: Minimal, intentional design with Tailwind CSS
- **HTMX Interactivity**: Lightweight, no heavy JavaScript
- **Optional Payments**: Stripe integration (bypassable for self-hosting)
- **Email Reminders**: Opt-in daily and weekly reminders
- **Data Export**: Users can export all their data (JSON format)

---

## Tech Stack

- **Framework**: Django 5.x
- **Database**: PostgreSQL (via Docker Compose locally, Fly.io in production)
- **Styling**: Tailwind CSS (CDN)
- **Interactivity**: HTMX
- **Charts**: Chart.js (for data view)
- **Auth**: Django-allauth (email only)
- **Payments**: Stripe Checkout (optional)
- **Deployment**: Fly.io (recommended) with EU data residency

---

## Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Git

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd 30-day-cohorts-webapp
   ```

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   ```
   
   The `.env.example` file contains all required environment variables with default values suitable for local development. Edit `.env` if you need to customize settings.

3. **Start services with Docker Compose**:
   ```bash
   docker-compose up -d
   ```
   
   Wait for services to be healthy (database healthcheck completes).

5. **Run migrations** (creates all database tables):
   ```bash
   docker-compose exec web python manage.py migrate
   ```
   
   This creates all Django tables including django-allauth's `django_site` table.

6. **Set up the default site** (required for django-allauth):
   ```bash
   docker-compose exec web python manage.py setup_site
   ```
   
   This configures the default Site object that django-allauth needs.

7. **Create a superuser** (optional, for admin access):
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

8. **Access the application**:
   - App: http://localhost:8000
   - Admin: http://localhost:8000/admin
   - Sign up: http://localhost:8000/accounts/signup/

### Local Development With uv

1. **Install uv**:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Set up PostgreSQL** (must be running locally)

4. **Create `.env` file** with database settings:
   ```bash
   # Update DB_HOST to 'localhost' if running Postgres locally
   DB_HOST=localhost
   ```

5. **Run migrations** (creates all database tables):
   ```bash
   uv run python manage.py migrate
   ```

6. **Set up the default site** (required for django-allauth):
   ```bash
   uv run python manage.py setup_site
   ```

7. **Create superuser** (optional):
   ```bash
   uv run python manage.py createsuperuser
   ```

8. **Run development server**:
   ```bash
   uv run python manage.py runserver
   ```

### Local Development Without uv (pip)

If you prefer using pip:

1. **Install dependencies**:
   ```bash
   pip install -e .
   ```

2. Follow steps 3-7 from above (without `uv run` prefix)

### Troubleshooting

**Error: `relation "django_site" does not exist`**
- This means migrations haven't been run yet. Run:
  ```bash
  docker-compose exec web python manage.py migrate
  docker-compose exec web python manage.py setup_site
  ```

**Error: `env file .env not found`**
- Create the `.env` file (see step 2 above)

**Error: Database connection refused**
- Make sure `docker-compose up -d` has completed and database is healthy
- Check logs: `docker-compose logs db`
- Wait a few seconds for Postgres to fully start

**Hot reloading not working**
- Ensure volume mount is in place: `volumes: - .:/app` in docker-compose.yml
- Django's StatReloader should detect changes automatically
- Check logs: `docker-compose logs -f web`

---

## Deployment (Fly.io)

### Why Fly.io?

- Multi-region support (EU + US)
- Easy Postgres addon
- Scheduled tasks for email reminders
- Cost-effective (~$9-12/month for 500 users)
- GDPR-compliant EU data residency

### Deployment Steps

1. **Install Fly CLI**:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login to Fly**:
   ```bash
   fly auth login
   ```

3. **Create Postgres in Frankfurt (EU)**:
   ```bash
   fly postgres create --region fra --name digital-minimalist-db
   ```

4. **Deploy app to Frankfurt**:
   ```bash
   fly launch --region fra
   ```

5. **Add US region** (optional, for lower latency):
   ```bash
   fly regions add iad
   ```

6. **Set environment variables**:
   ```bash
   fly secrets set SECRET_KEY=your-secret-key
   fly secrets set STRIPE_ENABLED=False  # or True with Stripe keys
   ```

7. **Run migrations**:
   ```bash
   fly ssh console -C "python manage.py migrate"
   ```

8. **Set up the default site** (required for django-allauth):
   ```bash
   fly ssh console -C "python manage.py setup_site"
   ```

9. **Create superuser**:
   ```bash
   fly ssh console -C "python manage.py createsuperuser"
   ```

### Cloudflare CDN (Optional)

For global static asset caching:
1. Point DNS to Cloudflare
2. Configure caching rules (static assets only, no HTML)
3. Use Fly.io as origin server

---

## Admin Tasks

### Create a Cohort

Via Django admin:
1. Go to http://your-domain.com/admin
2. Navigate to Cohorts → Add Cohort
3. Set name, start_date, end_date, price (in cents), and is_active

Via management command (TODO):
```bash
python manage.py create_cohort "Cohort 1" 2024-12-01 2024-12-31
```

### Export Cohort Data

1. Go to http://your-domain.com/admin-tools/
2. Select cohort
3. Download CSV with all user data (anonymized)

### Send Email Reminders

**Daily reminders**:
```bash
python manage.py send_daily_reminders
```

**Weekly reminders**:
```bash
python manage.py send_weekly_reminders
```

**Automate with cron** (add to crontab):
```
0 9 * * * cd /path/to/app && python manage.py send_daily_reminders
0 9 * * 0 cd /path/to/app && python manage.py send_weekly_reminders
```

**Or use Fly.io scheduled tasks** (TODO: add to fly.toml).

---

## Privacy & GDPR Compliance

### Data Storage
- **Location**: EU (Frankfurt) for GDPR compliance
- **Encryption**: TLS in transit, encrypted at rest (Postgres)
- **Retention**: Data kept until user deletion (hard delete)

### User Rights
- **Export**: Users can export all their data as JSON
- **Delete**: Hard account deletion (cascade removes all data)
- **Opt-out**: Email reminders are opt-in only

### Privacy Policy
- Available at `/accounts/privacy/`
- Includes data collection, usage, storage, and user rights

---

## Open Source & Self-Hosting

### License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

**What this means:**
- ✅ You can use, modify, and distribute this software
- ✅ You can self-host it for free
- ✅ You must share any modifications you make (if you host it publicly)
- ✅ If you modify and run this as a service, you must share the source code

**Full license text:** See [LICENSE](LICENSE) file or [GNU AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html)

**Commercial licensing:** If you need to use this software in a way that doesn't comply with AGPL (e.g., proprietary modifications without sharing source), commercial licenses may be available. Contact the project maintainer.

### Support Policy

- **Self-hosting = self-responsibility**: We provide the code, you manage your instance
- **Paid cohorts**: Get official support and guidance
- **Community**: Contribute via issues and pull requests

---

## TODOs

### High Priority
- [ ] Email templates (HTML + text versions)
- [ ] Fly.toml with scheduled tasks for email reminders
- [ ] Rate limiting middleware
- [ ] Accessibility audit (ARIA labels, keyboard navigation)

### Medium Priority
- [ ] Protocol content (populate `/accounts/protocol/`)
- [ ] Resources content (populate `/accounts/resources/`)
- [ ] Management command to create cohorts
- [ ] Better error handling and logging
- [ ] Monitoring/logging setup (Sentry integration?)

### Low Priority
- [ ] Dark mode support
- [ ] PWA manifest for mobile
- [ ] Cohort comparison analytics
- [ ] Anonymous aggregate trends

---

## Development

### Project Structure

```
30-day-cohorts-webapp/
├── accounts/          # User profiles, settings, GDPR features
├── cohorts/           # Cohort management, homepage
├── surveys/           # Entry and exit surveys
├── checkins/          # Daily check-ins and weekly reflections
├── dashboard/         # Data visualization (hidden by default)
├── payments/          # Stripe integration
├── admin_tools/       # Staff-only management views
├── templates/         # Django templates
├── static/            # Static files (CSS, JS, images)
├── config/            # Django settings
├── manage.py          # Django management script
└── docker-compose.yml # Local development environment
```

### Running Tests

Tests are planned but not yet implemented. When available:

```bash
# With Docker
docker-compose exec web python manage.py test

# Without Docker
python manage.py test
```

### Code Quality

- **Linting**: Follow PEP 8
- **Formatting**: Use Black (when configured)
- **Type checking**: Optional but appreciated
- **Templates**: Keep minimal and semantic

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed coding standards.

---

## Contributing

Contributions are welcome! We appreciate your help in making this platform better.

**Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.**

Quick summary:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes following our coding standards
4. Test your changes locally
5. Submit a pull request with a clear description

**Key principles:**
- Code follows Django best practices
- Templates maintain calm, minimal aesthetic
- No gamification or attention manipulation features
- All contributions are licensed under AGPL-3.0

---

## Support & Community

- **Bug Reports**: Use [GitHub Issues](https://github.com/your-username/30-day-cohorts-webapp/issues) for bug reports
- **Questions**: Use [GitHub Discussions](https://github.com/your-username/30-day-cohorts-webapp/discussions) for questions
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- **Email**: Contact the project maintainer for other inquiries

---

## Acknowledgments

Built for the Digital Minimalist Lab community. Inspired by Cal Newport's "Digital Minimalism" and the need for structured, intentional technology use.

---

## Note on Data Privacy

**Account deletion is permanent (hard delete).**  
This is intentional. We believe in user data control and privacy. If you delete your account, all your data is permanently removed from our database. This is a feature, not a bug.


