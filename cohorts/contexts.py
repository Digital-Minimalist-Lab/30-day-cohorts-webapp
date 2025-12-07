from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict
from .models import Survey
from cohorts.models import Cohort

@dataclass
class SurveyContext:
    """
    Encapsulates the context for a survey instance, including the survey,
    cohort, and due date, and provides derived properties like week number and title.
    """
    survey: Survey
    cohort: Cohort
    due_date: date

    week_number: int = field(init=False)

    def __post_init__(self):
        """Calculate derived fields after initialization."""
        self.week_number = self._calculate_week_number()

    def _calculate_week_number(self) -> int:
        """Calculate the week number relative to the cohort start date."""
        return ((self.due_date - self.cohort.start_date).days // 7) + 1

    def as_dict(self) -> Dict[str, Any]:
        """Return the context data as a dictionary."""
        return {
            'survey_name': self.survey.name,
            'due_date': self.due_date.isoformat(),
            'week_number': self.week_number,
            'cohort_name': self.cohort.name,        
        }