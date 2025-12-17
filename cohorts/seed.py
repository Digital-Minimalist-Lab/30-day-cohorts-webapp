from django.utils.text import slugify
from surveys.models import Survey, Question

SURVEYS_TO_CREATE = {
    "Entry Survey": {
        "purpose": "ENTRY",
        "description": "This survey establishes your baseline. Be honest with yourself—this is for your reflection, not judgment.",
        "questions": [
            # Section: Current State
            {"key": "mood_1to5", "text": "How do you feel right now? (1=low, 5=high)", "type": "integer", "section": "Current State"},
            {"key": "baseline_screentime_min", "text": "Average daily smartphone usage (minutes)", "type": "integer", "section": "Current State"},
            # Section: Intentions
            {"key": "intention_text", "text": "Why are you interested in participating?", "type": "textarea", "section": "Your Intentions"},
            {"key": "challenge_text", "text": "What would you like to reclaim?", "type": "textarea", "is_required": False, "section": "Your Intentions"},
        ]
    },
    "Exit Survey": {
        "purpose": "EXIT",
        "description": "You've completed the 30-day journey. Reflect on your experience—what changed, what you learned, and what comes next.",
        "questions": [
            # Section: Current State
            {"key": "mood_1to5", "text": "How do you feel now? (1=low, 5=high)", "type": "integer", "section": "Current State"},
            {"key": "final_screentime_min", "text": "Current daily screen time (minutes)", "type": "integer", "section": "Current State"},
            # Section: Reflection
            {"key": "wins_text", "text": "What were your wins?", "type": "textarea", "section": "Reflection"},
            {"key": "insight_text", "text": "What insights did you gain?", "type": "textarea", "section": "Reflection"},
        ]
    },
    "Daily Check-in": {
        "purpose": "DAILY_CHECKIN",
        "description": "<b>5-step daily reflection</b>: Rate your mood and digital satisfaction, note your screen time, celebrate a proud moment, acknowledge any slips, and reflect on your day.",
        "questions": [
            # Section: Quick Ratings
            {"key": "mood_1to5", "text": "How do you feel today? (1-5)", "type": "integer", "section": "Quick Ratings"},
            {"key": "digital_satisfaction_1to5", "text": "Satisfaction with your digital use today (1-5)", "type": "integer", "section": "Quick Ratings"},
            {"key": "screentime_min", "text": "Screen time in minutes (estimated or actual)", "type": "integer", "section": "Quick Ratings"},
            # Section: Daily Reflection
            {"key": "proud_moment_text", "text": "One thing you're proud of doing that replaced scrolling", "type": "textarea", "section": "Daily Reflection"},
            {"key": "digital_slip_text", "text": "If you slipped into digital use in any way, how?", "type": "textarea", "is_required": False, "section": "Daily Reflection"},
            {"key": "reflection_text", "text": "1-2 sentences about how today went", "type": "textarea", "section": "Daily Reflection"},
        ]
    },
    "Weekly Reflection": {
        "purpose": "WEEKLY_REFLECTION",
        "description": "Weekly reflection and goal setting.",
        "questions": [
            {"key": "goal_text", "text": "What's your intention for this week?", "type": "textarea", "section": "Goals"},
            {"key": "reflection_text", "text": "Optional reflection on last week", "type": "textarea", "is_required": False, "section": "Looking Back"},
        ]
    }
}


def seed_surveys(apps=None, update=False):
    """
    Seeds the database with surveys and questions from SURVEYS_TO_CREATE.
    Can be used in migrations or management commands.
    """

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
                "section": q_data.get("section", ""),
                "order": i,
                "is_required": q_data.get("is_required", True),
                "choices": q_data.get("choices"),
            }
            if update:
                Question.objects.update_or_create(survey=survey, key=q_data["key"], defaults=question_defaults)
            else:
                Question.objects.get_or_create(survey=survey, key=q_data["key"], defaults=question_defaults)
        
        yield survey, created