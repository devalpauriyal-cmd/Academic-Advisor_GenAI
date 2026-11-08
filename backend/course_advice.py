"""Resolve course-list scope from user turns before enumerating the database.

Similarity search is useful for rules, not for a complete course catalogue. Assistant
answers never supply a minor, batch or semester to this request planner.
"""
import re
from dataclasses import dataclass, field

import clarification
import memory
import structured
from schemas import AdvisorResponse

SCOPE_QUESTION = "Do you mean degree programmes, courses in a B.Tech semester, all semester courses, or courses in a minor?"
BATCH_QUESTION = "Which batch (year of admission) should I use for the course list?"
SEMESTER_QUESTION = "Which semester would you like to see?"
MINOR_QUESTION = "Which minor would you like the course list for?"
QUESTIONS = {SCOPE_QUESTION: "scope", BATCH_QUESTION: "batch", SEMESTER_QUESTION: "semester", MINOR_QUESTION: "minor"}
LIST_RE = re.compile(r"\b(courses|subjects)\b|\bcourse (?:list|catalog(?:ue)?)\b", re.I)
LIST_VERB_RE = re.compile(r"\b(which|what|list|show|give|available|offered|offer)\b|\bhow many (courses|subjects)\b", re.I)
NO_VISUAL_RE = re.compile(r"\b(text only|no (?:infographics?|charts?|visuals?|diagrams?)|without (?:an? )?(?:infographics?|charts?|visuals?|diagrams?))\b", re.I)


@dataclass
class Request:
    kind: str | None = None
    batch: str | None = None
    semester: int | None = None
    minor: str | None = None
    no_visual: bool = False
    overview: bool = False


@dataclass
class Advice:
    clarification: AdvisorResponse | None = None
    chunks: list[dict] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _ask(answer: str, question: str, choices: list[str]) -> Advice:
    return Advice(clarification=clarification._ask(answer, question), suggestions=choices)


def _minor(text: str) -> str | None:
    return next((name for key, name in structured.MINOR_NAMES.items()
                 if re.search(rf"\b{re.escape(key)}\b", text, re.I)), None)


def _scope(text: str) -> str | None:
    if re.search(r"\bdegree programmes?\b|\bdegree programs?\b", text, re.I):
        return "programmes"
    if re.search(r"\bminor\b|\bminors\b", text, re.I):
        return "minor"
    if re.search(r"\ball (?:the )?semesters?\b|\b(?:full|entire|complete) (?:curriculum|course list)\b|\bcurriculum\b", text, re.I) or _overview(text):
        return "curriculum"
    if re.search(r"\bsem(?:ester)?\b|\b\d(?:st|nd|rd|th) semester\b", text, re.I):
        return "semester"
    return None


def _overview(text: str) -> bool:
    return bool(re.search(r"\bcourse structure\b|\bcurriculum (?:overview|structure)\b|\b(?:explain|overview of) (?:the |my )?curriculum\b"
                          r"|\bcredits? (?:distribution|breakdown)\b|\bcredits? (?:are )?(?:distributed|split)\b", text, re.I))


def _is_list(text: str) -> bool:
    if structured.CODE_RE.search(text) or re.search(r"\b(?:can|could|may|should|am) i\b|\beligib\w*\b|\bprerequisites?\b", text, re.I):
        return False
    if _overview(text):
        return True
    return bool((LIST_RE.search(text) or _scope(text) == "programmes") and
                (LIST_VERB_RE.search(text) or len(text.split()) <= 4))


def _update(request: Request, text: str, pending: str | None):
    kind = _scope(text)
    if kind and kind != request.kind:
        request.kind, request.semester, request.minor = kind, None, None
    request.overview = _overview(text) if kind else request.overview
    batch = re.search(r"\b(20\d\d)\b", text)
    if batch:
        request.batch = batch.group(1)
        if not request.kind:
            request.kind = "curriculum"
    sem = re.search(r"\bsem(?:ester)?\s*(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th) semester\b", text, re.I)
    if sem:
        request.semester = int(next(group for group in sem.groups() if group))
    elif pending == "semester" and re.fullmatch(r"\s*\d{1,2}\s*[.!]?\s*", text):
        request.semester = int(re.search(r"\d+", text).group())
    minor = _minor(text)
    if minor and (request.kind == "minor" or pending == "minor"):
        request.kind, request.minor = "minor", minor
    request.no_visual = request.no_visual or bool(NO_VISUAL_RE.search(text))


def plan(message: str, history: list[dict], facts: memory.Facts, profile: dict | None) -> Advice | None:
    """Replay the request and short answers, preserving scope through our own clarification questions."""
    if memory.recall_kind(message) or structured.CODE_RE.search(message):
        return None
    if _is_list(message) and re.search(r"\b(?:b\.?\s?(?:ba|sc|des|com|ca)|m\.?\s?(?:ba|tech|sc|des|com|ca)|ph\.?d)\b", message, re.I):
        return _ask("The supplied curricula describe B.Tech and its minors. I don't have a course catalogue for that "
                    "degree programme, so I shouldn't substitute B.Tech subjects for it.",
                    "Would you like to explore B.Tech semester courses or minor courses?", ["Semester courses", "Minor courses"])
    # Explicit cross-batch comparisons retain the existing multi-batch SQL route.
    if re.search(r"\ball batches\b", message, re.I) or len(set(re.findall(r"\b20\d\d\b", message))) > 1:
        return None
    if any(re.search(pattern, message, re.I) for pattern, _, label in structured.BASKET_ALIASES if label != "Minor/Open"):
        return None
    request, pending, requested = None, None, False
    for turn in [*history, {"role": "user", "content": message}]:
        text = turn["content"]
        if turn["role"] == "assistant":
            pending = next((stage for question, stage in QUESTIONS.items() if question in text), None) \
                if turn.get("needs_clarification") else None
            continue
        requested = False
        listing = _is_list(text)
        answering = pending and (listing or not clarification.QUESTION_RE.search(text.strip()))
        if listing or answering:
            request = request or Request()
            _update(request, text, pending)
            requested = True
        elif _minor(text) and re.search(r"\bminor\b", text, re.I):
            request = Request(kind="minor", minor=_minor(text), batch=request.batch if request else None)
            _update(request, text, None)
        elif request and memory.CORRECTION_RE.search(text):
            updated = memory.from_history([{'role':'user', 'content':text}])
            if updated.batch:
                request.batch = updated.batch
            if updated.semester is not None and request.kind == 'semester':
                request.semester = updated.semester
            requested = True
        elif not memory.recall_kind(text) and (clarification.QUESTION_RE.search(text.strip()) or clarification.is_study_goal(text)):
            request = None  # a new subject ends the previous course-list scope
        pending = None
    if not requested or request is None:
        return None
    if not request.kind:
        return _ask("I can help you find the right courses. Let me check what you mean first.", SCOPE_QUESTION,
                    ["Degree programmes", "Semester courses", "All semester courses", "Minor courses"])
    if request.kind == "programmes":
        return _ask("The supplied files cover B.Tech curricula and minors; they are not a complete admissions programme catalogue. "
                    "I can help you explore the B.Tech course structure or a subject you're interested in.",
                    "Would you like to explore B.Tech semester courses or minor courses?", ["Semester courses", "Minor courses"])
    request.batch = request.batch or facts.batch or (profile or {}).get("batch")
    with structured._db() as con:
        batches = [row[0] for row in con.execute("SELECT DISTINCT batch FROM courses WHERE kind='programme' ORDER BY batch")]
    if request.batch not in batches:
        intro = "Course lists differ by admission year, so I don't want to mix different batches."
        if request.batch:
            intro = f"The supplied course lists cover {', '.join(batches)}; I don't have a curriculum for {request.batch}."
        return _ask(intro, BATCH_QUESTION, [batch + " batch" for batch in batches])
    if request.kind == "minor" and not request.minor:
        return _ask(f"I'll use the {request.batch} batch. Let's choose the minor you want to explore.", MINOR_QUESTION,
                    [name + " minor" for name in structured.offered_minors(request.batch)])
    if request.kind == "semester":
        request.semester = request.semester if request.semester is not None else facts.semester or (profile or {}).get("current_semester")
        if request.semester not in range(1, 9):
            return _ask(f"I'll use the {request.batch} batch. You can choose a semester from 1 to 8.", SEMESTER_QUESTION,
                        [f"Semester {sem}" for sem in range(1, 9)])
        chunks = structured.semester_list(request.batch, request.semester)
    elif request.kind == "minor":
        chunks = structured.minor_direct(request.minor, [request.batch], show_all=True)
    else:
        chunks = structured.batch_overview(request.batch) if request.overview else structured.curriculum_courses(request.batch)
    if not chunks:
        return _ask("I couldn't find course rows for that selection in the supplied files.", SCOPE_QUESTION,
                    ["Semester courses", "All semester courses", "Minor courses"])
    params = {"minor": request.minor} if request.kind == "minor" else \
        {"semester": request.semester} if request.kind == "semester" else {}
    rows = structured.visual_rows(request.batch, **params)
    attachments = []
    if not request.no_visual and rows and (len(rows) >= 4 or len({r['semester'] for r in rows}) >= 2):
        sems = {row['semester'] for row in rows}
        title = f"{request.minor} minor" if request.minor else f"Semester {request.semester}" if request.semester else "Course structure"
        attachments = [{"type": "infographic", "batch": request.batch, **params,
                        "title": f"{title} · {request.batch} batch", "min_width": max(720, len(sems) * 170 + 60),
                        "caption": "Course map added to show how these courses and credits fit together. "
                                   "Built from the supplied course data; undecided slots remain labelled.", "automatic": True}]
    suggestions = [f"List courses for all semesters of the {request.batch} batch",
                   f"Show available minors for the {request.batch} batch"]
    if request.kind == "curriculum":
        suggestions[0] = f"Show courses in Semester 1 for the {request.batch} batch"
    return Advice(chunks=chunks, attachments=attachments, suggestions=suggestions)
