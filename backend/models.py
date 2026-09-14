"""Domain types shared between the API and the worker.

AdverseEvent mirrors db.AdverseEventRecord field-for-field, minus `id` and
`narrative` (the agent's output, not its input) — build one from a row with
AdverseEvent.model_validate(record).
"""

from datetime import date

from pydantic import BaseModel, ConfigDict

# Field name -> human-readable label, in the order they should read in a prompt.
_FACT_LABELS: dict[str, str] = {
    "study_id": "Study",
    "domain": "Domain",
    "subject_id": "Subject",
    "sequence": "Sequence",
    "sponsor_id": "Sponsor ID",
    "reported_term": "Reported term",
    "modified_term": "Modified term",
    "term": "Preferred term",
    "body_system": "Body system",
    "system_organ_class": "System organ class",
    "location": "Location",
    "severity": "Severity",
    "serious": "Serious",
    "category": "Category",
    "subcategory": "Subcategory",
    "onset_date": "Onset",
    "end_date": "End date",
    "ongoing": "Ongoing",
    "relationship": "Relationship to treatment",
    "action_taken": "Action taken",
    "outcome": "Outcome",
    "caused_death": "Caused death",
    "hospitalization": "Required hospitalization",
    "congenital_anomaly": "Congenital anomaly",
}


class AdverseEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    study_id: str
    domain: str
    subject_id: str
    sequence: int
    sponsor_id: str
    reported_term: str
    modified_term: str | None = None
    term: str
    body_system: str
    system_organ_class: str
    location: str | None = None
    severity: str
    serious: str
    category: str | None = None
    subcategory: str | None = None
    onset_date: date
    end_date: date | None = None
    ongoing: str
    relationship: str
    action_taken: str
    outcome: str
    caused_death: str
    hospitalization: str
    congenital_anomaly: str

    def to_prompt_facts(self) -> str:
        return "\n".join(
            f"{label}: {value}"
            for field, label in _FACT_LABELS.items()
            if (value := getattr(self, field)) is not None
        )


# Ready-made instance for quick manual testing, so you don't have to hand-type
# every required field just to try the agent out.
SAMPLE_ADVERSE_EVENT = AdverseEvent(
    study_id="AGENT-AE-001",
    domain="AE",
    subject_id="AE-0001",
    sequence=1,
    sponsor_id="AE-0001",
    reported_term="headache",
    modified_term="Headache",
    term="HEADACHE",
    body_system="Nervous system disorders",
    system_organ_class="Nervous system disorders",
    location="Head",
    severity="MILD",
    serious="N",
    category="NON-TREATMENT EMERGENT",
    onset_date=date(2026, 1, 2),
    end_date=date(2026, 1, 4),
    ongoing="N",
    relationship="NOT RELATED",
    action_taken="NONE",
    outcome="RECOVERED/RESOLVED",
    caused_death="N",
    hospitalization="N",
    congenital_anomaly="N",
)
