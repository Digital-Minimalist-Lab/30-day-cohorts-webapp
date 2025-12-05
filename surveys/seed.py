from django.utils.text import slugify


SURVEYS_TO_CREATE = {
    "Entry Survey": {
        "purpose": "ENTRY",
        "description": "This survey establishes your baseline. Be honest with yourself—this is for your reflection, not judgment.",
        "questions": [
            {"key": "mood_1to5", "text": "How do you feel right now? (1=low, 5=high)", "type": "integer"},
            {"key": "baseline_screentime_min", "text": "Average daily smartphone usage (minutes)", "type": "integer"},
            {"key": "intention_text", "text": "Why are you interested in participating?", "type": "textarea"},
            {"key": "challenge_text", "text": "What would you like to reclaim?", "type": "textarea", "is_required": False},
        ]
    },
    "Exit Survey": {
        "purpose": "EXIT",
        "description": "You've completed the 30-day journey. Reflect on your experience—what changed, what you learned, and what comes next.",
        "questions": [
            {"key": "mood_1to5", "text": "How do you feel now? (1=low, 5=high)", "type": "integer"},
            {"key": "final_screentime_min", "text": "Current daily screen time (minutes)", "type": "integer"},
            {"key": "wins_text", "text": "What were your wins?", "type": "textarea"},
            {"key": "insight_text", "text": "What insights did you gain?", "type": "textarea"},
        ]
    },
    "Daily Check-in": {
        "purpose": "DAILY_CHECKIN",
        "description": "<b>5-step daily reflection</b>: Rate your mood and digital satisfaction, note your screen time, celebrate a proud moment, acknowledge any slips, and reflect on your day.",
        "questions": [
            {"key": "mood_1to5", "text": "How do you feel today? (1-5)", "type": "integer"},
            {"key": "digital_satisfaction_1to5", "text": "Satisfaction with your digital use today (1-5)", "type": "integer"},
            {"key": "screentime_min", "text": "Screen time in minutes (estimated or actual)", "type": "integer"},
            {"key": "proud_moment_text", "text": "One thing you're proud of doing that replaced scrolling", "type": "textarea"},
            {"key": "digital_slip_text", "text": "If you slipped into digital use in any way, how?", "type": "textarea", "is_required": False},
            {"key": "reflection_text", "text": "1-2 sentences about how today went", "type": "textarea"},
        ]
    },
    "Weekly Reflection": {
        "purpose": "WEEKLY_REFLECTION",
        "description": "Weekly reflection and goal setting.",
        "questions": [
            {"key": "goal_text", "text": "What's your intention for this week?", "type": "textarea"},
            {"key": "reflection_text", "text": "Optional reflection on last week", "type": "textarea", "is_required": False},
        ]
    }
}


def seed_surveys(apps=None, update=False):
    """
    Seeds the database with surveys and questions from SURVEYS_TO_CREATE.
    Can be used in migrations or management commands.
    """
    if apps:
        Survey = apps.get_model('surveys', 'Survey')
        Question = apps.get_model('surveys', 'Question')
    else:
        from .models import Survey, Question

    for survey_name, survey_data in SURVEYS_TO_CREATE.items():
        survey_defaults = {
            "name": survey_name,
            "description": survey_data.get("description", ""),
            "purpose": survey_data.get("purpose", "GENERIC")
        }
        if update:
            survey, created = Survey.objects.update_or_create(slug=slugify(survey_name), defaults=survey_defaults)
        else:
            survey, created = Survey.objects.get_or_create(slug=slugify(survey_name), defaults=survey_defaults)

        for i, q_data in enumerate(survey_data["questions"]):
            question_defaults = {
                "text": q_data["text"],
                "question_type": q_data["type"],
                "order": i,
                "is_required": q_data.get("is_required", True)
            }
            if update:
                Question.objects.update_or_create(survey=survey, key=q_data["key"], defaults=question_defaults)
            else:
                Question.objects.get_or_create(survey=survey, key=q_data["key"], defaults=question_defaults)
        
        yield survey, created