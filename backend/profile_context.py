"""Resolve disagreements with selected records without moving grades between batches."""
import re
from dataclasses import dataclass, replace

import clarification
import memory
import structured
from schemas import AdvisorResponse

USE_RECORD = 'Use the selected record'
WITHOUT_RECORD = 'Continue without the selected record'
QUESTION = 'Should I use the selected record, or continue without the selected record for personal eligibility checks?'


@dataclass
class Resolution:
    profile: dict | None
    facts: memory.Facts
    message: str
    clarification: AdvisorResponse | None = None


def needs_record(query: str) -> bool:
    return bool(re.search(r'\b(i|my|me)\b', query, re.I) and re.search(
        r'\beligib\w*\b|\b(?:can|may|could|should) i (?:register|take|enrol\w*|progress|graduate)\b'
        r'|\bam i (?:allowed|able)\b|\b(?:credits? (?:left|remaining)|credits? do i (?:need|have))\b', query, re.I))


def reconcile(profile: dict | None, facts: memory.Facts, message: str, history: list[dict], query: str) -> Resolution:
    if not profile:
        return Resolution(profile, facts, message)
    choice, snapshot, pending = None, None, False
    prefix = []
    resume = None
    for index, turn in enumerate([*history, {'role':'user', 'content':message}]):
        if turn['role'] == 'assistant':
            pending = bool(turn.get('needs_clarification') and QUESTION in turn['content'])
        else:
            if pending and turn['content'].strip() in (USE_RECORD, WITHOUT_RECORD):
                choice = turn['content'].strip()
                at_choice = memory.from_history(prefix)
                snapshot = (at_choice.batch, at_choice.semester)
                if index == len(history):
                    resume = next((item['content'] for item in reversed(prefix) if item['role'] == 'user'), None)
            elif choice == USE_RECORD:
                new = memory.from_history([turn])
                if (new.batch and new.batch != profile.get('batch')) or \
                        (new.semester and new.semester != profile.get('current_semester')):
                    choice = None
            pending = False
        prefix.append(turn)
    if choice == USE_RECORD and snapshot != (facts.batch, facts.semester):
        choice = None  # a later personal correction needs a new reconciliation
    if choice == WITHOUT_RECORD:
        return Resolution(None, facts, resume or message)
    if choice == USE_RECORD:
        corrected = {key:value for key,value in facts.corrected.items() if key not in ('batch', 'semester')}
        aligned = replace(facts, batch=profile.get('batch'), semester=profile.get('current_semester'), corrected=corrected)
        return Resolution(profile, aligned, resume or message)
    mismatches = []
    if facts.batch and profile.get('batch') and facts.batch != profile['batch']:
        mismatches.append(f"the record has batch {profile['batch']}, but you said {facts.batch}")
    if facts.semester and profile.get('current_semester') and facts.semester != profile['current_semester']:
        mismatches.append(f"the record has semester {profile['current_semester']}, but you said {facts.semester}")
    if mismatches and needs_record(query):
        answer = "I need to resolve a mismatch before using your grades: " + '; '.join(mismatches) + ". " \
                 "I won't apply grades from this record to different student details."
        return Resolution(profile, facts, message, clarification._ask(answer, QUESTION))
    return Resolution(profile, facts, message)


def missing_record(query: str, profile: dict | None):
    if not needs_record(query) or not structured.mentioned_codes(query):
        return None
    if profile and profile.get('courses_completed') is not None:
        return None
    return clarification._ask(
        "I can explain the course requirements, but I don't have a matching confirmed course record to decide "
        "whether you meet them.",
        "Can you select a matching profile or upload and confirm your transcript using the attachment button?")
