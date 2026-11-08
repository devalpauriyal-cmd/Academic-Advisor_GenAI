"""Conservative numeric claim checks over cited passages and confirmed record fields.

A matching number is insufficient: units, named courses/minors and earned/required
credit roles must agree. Prompts and user questions are never evidence for policy.
This checks explicit numeric facts, not arbitrary natural-language entailment.
"""
import re
from dataclasses import dataclass
from decimal import Decimal

NUMBER = r'\d+(?:\.\d+)?'
CODE_RE = re.compile(r'\b[A-Z]{3,4}\d{3}\b', re.I)
MINORS = r'law|design|psychology|economics|finance|marketing|start-?up'
PATTERNS = {
    'credits': re.compile(rf'(?<![\w.])({NUMBER})\s*[- ]?\s*(?:credits?\b|cr\b)|\bcredits?\s*[:=]?\s*({NUMBER})(?![\d.])', re.I),
    'percent': re.compile(rf'(?<![\w.])({NUMBER})\s*%'),
    'cgpa': re.compile(rf'\bcgpa\s*(?:of|is|:|=|>=|at least)?\s*({NUMBER})\b|\b({NUMBER})\s+cgpa\b', re.I),
}


@dataclass(frozen=True)
class Fact:
    kind: str
    value: str
    subjects: frozenset[str]
    role: str | None
    text: str
    negative: bool = False


def _subjects(text: str) -> frozenset[str]:
    subjects = {code.upper() for code in CODE_RE.findall(text)}
    subjects.update('minor:' + name.lower() for name in re.findall(rf'\b({MINORS})\b', text, re.I))
    if re.search(r'\b(attendance|classes conducted)\b', text, re.I):
        subjects.add('attendance')
    if re.search(r'\bdiscount\b', text, re.I):
        subjects.add('discount')
    return frozenset(subjects)


def _role(text: str, kind: str) -> str | None:
    if kind == 'credits':
        if re.search(r'\b(remaining|remain|still need|more credits|credits left)\b', text, re.I):
            return 'remaining'
        if re.search(r'\b(earned|completed|passed|have earned|have completed)\b', text, re.I):
            return 'earned'
        if re.search(r'\b(need|needs|required|requirement|requires?|minimum|must)\b', text, re.I):
            return 'required'
        if CODE_RE.search(text):
            return 'course'
    if kind == 'cgpa' and re.search(r'\b(minimum|at least|threshold|required)\b', text, re.I):
        return 'required'
    return None


def facts(text: str, context: str = '') -> list[Fact]:
    output = []
    # A one-course source header can label following batch rows, but a multi-course passage cannot.
    inherited = _subjects(context)
    header = text.split('\n', 1)[0]
    if len(CODE_RE.findall(header)) == 1 and '\n' in text:
        inherited |= frozenset(code.upper() for code in CODE_RE.findall(header))
    table_headers = []
    for line in re.split(r'(?<=[.!?])\s+|\n|;', text):
        original = line
        if line.strip().startswith('|'):
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if any(cell.lower() == 'credits' for cell in cells):
                table_headers = [cell.lower() for cell in cells]
            elif table_headers and len(cells) == len(table_headers) and 'credits' in table_headers:
                value = cells[table_headers.index('credits')]
                if re.fullmatch(NUMBER, value):
                    line = ' | '.join(cells[:table_headers.index('credits') + 1]) + f' | {value} credits'
        subjects = _subjects(line) | inherited
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                value = next(group for group in match.groups() if group is not None)
                bound = subjects
                if kind == 'credits':
                    before = [code.upper() for code in CODE_RE.findall(line[:match.start()])]
                    parent = {subject for subject in inherited if CODE_RE.fullmatch(subject)}
                    # Codes listed as prerequisites after the credit value do not own that value.
                    codes = set(before) if len(set(before)) == 1 or re.search(r'\beach\b', line, re.I) else parent
                    if not codes and not before:
                        after = re.match(r'\s+(?:for|in)\s+([A-Z]{3,4}\d{3})\b', line[match.end():], re.I)
                        if after:
                            codes = {after.group(1).upper()}
                    bound = frozenset(subject for subject in subjects if not CODE_RE.fullmatch(subject)) | frozenset(codes)
                role = _role(line[:match.end()], kind)
                if role is None and kind == 'credits' and any(CODE_RE.fullmatch(subject) for subject in bound):
                    role = 'course'
                negative = kind == 'credits' and bool(re.search(r"\b(?:do not|does not|don't|doesn't|never) (?:need|require)\b"
                                                                  r"|\bnot required\b|\bno (?:credit )?requirement\b", line, re.I))
                output.append(Fact(kind, str(Decimal(value).normalize()), bound, role, match.group(), negative))
        for code in CODE_RE.findall(original):
            output.append(Fact('code', code.upper(), frozenset(), None, code))
    return output


def claims(text: str) -> list[Fact]:
    return [fact for sentence in re.split(r'(?<=[.!?])\s+|\n', text)
            if not (sentence.strip().endswith('?') and re.match(r'\s*(?:what|which|how|have|has|did|do|does|can|could|are|is)\b', sentence, re.I))
            and not re.search(r"\b(?:i|we) (?:cannot|can't|could not|couldn't) (?:confirm|verify|determine|establish)\b", sentence, re.I)
            for fact in facts(sentence)]


def supported(claim: Fact, candidates: list[Fact]) -> bool:
    return any(claim.kind == item.kind and claim.value == item.value
               and claim.negative == item.negative
               and claim.subjects <= item.subjects
               and (claim.role is None or claim.role == item.role)
               for item in candidates)


def sources_for(claim: Fact, chunks: list[dict]) -> list[dict]:
    return [chunk for chunk in chunks if supported(claim, facts(chunk['text'], chunk.get('section', '')))]


def problems(result, evidence: str | list[dict], profile: dict | None = None) -> list[str]:
    if isinstance(evidence, str):
        candidates = facts(evidence)
    else:
        cited = {(source.source_file, source.section) for source in result.sources}
        candidates = [fact for chunk in evidence if (chunk['source_file'], chunk['section']) in cited
                      for fact in facts(chunk['text'], chunk.get('section', ''))]
    if profile:
        earned = profile.get('completed_credits')
        if earned is not None:
            candidates += facts(f'You have earned {earned} credits.')
        if profile.get('cgpa') is not None:
            candidates += facts(f'Your CGPA is {profile["cgpa"]}.')
        for course in (profile.get('courses_completed') or []) + (profile.get('courses_failed') or []):
            candidates += facts(f'{course["code"]} credits: {course["credits"]}.')
    return list(dict.fromkeys(f"'{claim.text}' is not supported with the same unit, subject and meaning in the cited evidence"
                             for claim in claims(result.answer) if not supported(claim, candidates)))
