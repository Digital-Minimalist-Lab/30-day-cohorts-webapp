

# Admin Guide

## The Env file and initial setup

The env file should have the following variables to validate incoming traffic:
```
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

We also need to set up django sites:
```
TODO
```

## Creating a Superuser

```
python manage.py createsuperuser
```

## Adding a Cohort

There are two options to add cohorts:

1. Use the Django admin to create a cohort
2. Use the `import_cohort_design` management command

```bash
python manage.py import_cohort_design cohort_designs/30day_digital_declutter.json
```

After importing a cohort there are a few extra steps needed to manage it:
- Setup dates
- Set the onboarding survey
- Make sure pricing is accurate
- Ensure the cohort imported properly with all the surveys
