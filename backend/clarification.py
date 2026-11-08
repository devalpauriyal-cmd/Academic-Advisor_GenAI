"""Clarify an open academic goal before treating it as a request for university policy.

These replies make no claims about available programmes or admission requirements.
Specific questions continue through retrieval and the normal grounding checks.
"""
import re
from typing import TYPE_CHECKING

from schemas import AdvisorResponse

if TYPE_CHECKING:
    from memory import Facts

PROGRAMME_QUESTION = "Which programme or subject would you like to study?"
INTEREST_QUESTION = "What subjects do you enjoy or want to learn more about?"
HELP_QUESTION = "Would you like help with admission eligibility, the application process, fees, or the curriculum?"
STUDENT_QUESTION = "Are you exploring admission, or do you need help with your studies as a current student?"

STUDY_GOAL_RE = re.compile(
    r"\bi (?:want|wish|hope|plan|intend|would like)\s+(?:to\s+)?(?:study|pursue|join|enrol\w*|apply)\b"
    r"|\bi'd like to (?:study|join|enrol\w*|apply)\b"
    r"|\bi (?:am|'m) interested in (?:studying|joining|enrol\w*|applying)\b"
    r"|\bi'm interested in (?:studying|joining|enrol\w*|applying)\b"
    r"|\bi (?:want|need|seek) admission\b", re.I)
UNIVERSITY_RE = re.compile(r"\b(vidya\s*shilp|vu|university|here)\b", re.I)
STATED_INTEREST_RE = re.compile(
    r"\b(?:study|pursue)\s+(?!at\b|in\b|here\b).{1,80}?\s+(?:at|in)\s+"
    r"(?:vidya\s*shilp(?: university)?|vu|(?:the )?university)\b", re.I)
GENERAL_HELP_RE = re.compile(
    r"(?:i (?:need|want|would like)|i'd like) (?:some )?(?:help|advice|guidance)"
    r"(?: (?:with|about|for|on) (?:my )?(?:studies|academics|academic choices|education))?[.! ]*", re.I)
SPECIFIC_RE = re.compile(
    r"\b(eligib\w*|cutoffs?|fees?|tuition|scholarships?|deadlines?|documents?|requirements?|"
    r"curriculum|syllabus|attendance|credits?|prerequisites?|minors?|application process|how (?:do|can|to) .*apply)\b"
    r"|\b[A-Z]{3,4}\d{3}\b", re.I)
QUESTION_RE = re.compile(r"^(what|which|who|how|when|where|why|can|could|may|should|is|are|am|do|does|did|will|would|have|has)\b"
                         r"|^(list|show|tell|explain|summari[sz]e|compare)\b", re.I)
UNSURE_RE = re.compile(r"^(?:i(?:'m| am) )?(?:not sure|unsure|undecided|don't know|do not know)(?: yet)?[.!? ]*$", re.I)


def is_study_goal(message: str) -> bool:
    text = message.replace("\u2019", "'")
    return bool(STUDY_GOAL_RE.search(text) and UNIVERSITY_RE.search(text))


def _ask(answer: str, question: str) -> AdvisorResponse:
    return AdvisorResponse(answer=answer, confidence="high", grounded=False, sources=[],
                           needs_clarification=True, clarifying_question=question,
                           insufficient_information=False, conflict_detected=False)


def opening(message: str, history: list[dict], facts: "Facts") -> AdvisorResponse | None:
    """Ask one useful question; never turn a clear policy question into an intake form."""
    text = message.replace("\u2019", "'").strip()
    if SPECIFIC_RE.search(text):
        return None
    if is_study_goal(text):
        question = HELP_QUESTION if facts.programme or STATED_INTEREST_RE.search(text) else PROGRAMME_QUESTION
        return _ask("I can help you explore studying at Vidyashilp University. Let's narrow down what you need.", question)
    if GENERAL_HELP_RE.fullmatch(text):
        return _ask("I can help you work through your academic options. Let's start with your goal.", STUDENT_QUESTION)

    last = history[-1] if history else {}
    if last.get("role") != "assistant" or not last.get("needs_clarification"):
        return None
    previous = last.get("content", "")
    if PROGRAMME_QUESTION in previous or INTEREST_QUESTION in previous:
        if UNSURE_RE.fullmatch(text):
            question = HELP_QUESTION if INTEREST_QUESTION in previous else INTEREST_QUESTION
            return _ask("That's okay; you don't need to have chosen a programme yet.", question)
        if not QUESTION_RE.search(text) and "?" not in text and len(text.split()) <= 20:
            return _ask("Thanks. I can help you narrow down what to check for that area of study.", HELP_QUESTION)
    if STUDENT_QUESTION in previous and re.search(r"\b(admission|apply|prospective|joining)\b", text, re.I):
        return _ask("I can help you explore admission information in the supplied documents.",
                    HELP_QUESTION if facts.programme else PROGRAMME_QUESTION)
    return None
