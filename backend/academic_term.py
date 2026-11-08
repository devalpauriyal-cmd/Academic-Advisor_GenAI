"""Resolve the term requested by the student, using the documented current-term context."""
import re
from dataclasses import dataclass

from config import PROCESSED_DIR


@dataclass(frozen=True)
class Term:
    kind: str | None
    reason: str = ''


def current_term() -> str | None:
    text = (PROCESSED_DIR / 'term_context.md').read_text(encoding='utf-8')
    match = re.search(r'current term[^\n]*?is the (ODD|EVEN) semester', text, re.I)
    return match.group(1).lower() if match else None


def _explicit(text: str) -> Term | None:
    text = text.replace('\u2019', "'")
    if re.search(r'\bsummer\b', text, re.I):
        return Term('summer', 'Summer offerings are not specified by the normal semester spread.')
    parities = set(re.findall(r'\b(odd|even)[ -]+(?:term|semester|sem)\b', text, re.I))
    parities = {value.lower() for value in parities}
    numbers = []
    for match in re.finditer(r'\bsem(?:ester)?\s*(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)\s+semester\b', text, re.I):
        prefix = text[max(0, match.start() - 35):match.start()]
        if re.search(r"\b(?:i'm|i am|currently|my current)\b[^.?!]{0,25}$", prefix, re.I):
            continue  # a stated current semester is not the requested future term
        numbers.append(int(next(group for group in match.groups() if group)))
    if any(number not in range(1, 9) for number in numbers):
        return Term(None, 'The requested B.Tech semester must be between 1 and 8.')
    number_parities = {'odd' if number % 2 else 'even' for number in numbers}
    if len(parities | number_parities) > 1:
        return Term(None, 'The request names both odd and even terms. Please choose one term for this check.')
    if parities or number_parities:
        return Term(next(iter(parities or number_parities)))
    if re.search(r'\bnext (?:semester|term|sem)\b', text, re.I):
        current = current_term()
        return Term('even' if current == 'odd' else 'odd' if current == 'even' else None,
                    'Next term is derived from the supplied current-term context.')
    if re.search(r'\b(?:this|current) (?:semester|term|sem)\b', text, re.I):
        return Term(current_term())
    return None


def resolve(query: str, message: str | None = None) -> Term:
    if message is not None:
        explicit = _explicit(message)
        if explicit:
            return explicit
    return _explicit(query) or Term(current_term(), 'Using the current term from the supplied term context.')
