"""
Conversation memory: what the student has told the advisor in this chat, read from their own turns only.

The browser sends the history with each request and the server keeps nothing, so the facts are rebuilt every time.
Later statements replace earlier ones, which is what makes a correction work. Assistant turns are never read:
a claim the model made must not become a "fact" the student stated.

    facts = memory.from_history(history, message)
    memory.recall_kind(message)              -> "needs" | "summary" | "topic" | "unclear" | "noted" | None
    memory.contextual_query(message, history, facts)   -> what to retrieve for a follow-up
"""
import re
import identity
from dataclasses import dataclass, field

MINOR_NAMES = r"law|design|psychology|economics|finance|marketing|start-?up|entrepreneurship"
QUESTION_START = r"(what|which|who|how|when|where|why|can|could|may|should|is|are|am|do|does|did|will|would|have|has)\b"
COMMAND_START = r"(list|show|tell|give|explain|summari[sz]e|compare|describe)\b"
SELF_STATEMENT = (r"\b(i am|i'm|im|i was|i joined|i study|i've|i have|i haven't|i completed|i earned|i passed|"
                  r"i declared|i didn't|my (batch|semester|sem|programme|program)|as an?)\b")
NEEDS_RE = re.compile(
    r"\bwhat (information|info|details?|else) do you (still )?(need|require)\b"
    r"|\bwhat do you (still )?(need|require)\b"
    r"|\bwhat else (should|can|must) i (tell|share|provide)\b"
    r"|\banything (else )?you (still )?need\b"
    r"|\bwhat (information|info|details?) are you (still )?missing\b"
    r"|\bwhat(?:'s| is) (still )?(unknown|missing) about me\b", re.I)
TOPIC_RE = re.compile(
    r"\bwhat (was|am) i asking (you )?(for advice )?about\b"
    r"|\bwhat did i ask (you )?(for advice )?about\b"
    r"|\bwhat (were|are) we (discussing|talking about)\b"
    r"|\bwhat (have|had) we been (discussing|talking about)\b"
    r"|\bwhat (was|is) (my|our|the) (original )?(question|topic)\b"
    r"|\bremind me (of|about) (my|our|the) (original )?(question|topic)\b", re.I)
SUMMARY_RE = re.compile(
    r"\b(summari[sz]e|recap)\b.*\b(know|told|said|conversation|chat|so far|about me)\b"
    r"|what (do|did) you (know|remember|have)\b.*\bme\b|stored about me"
    r"|what (have|did) i (tell|told|say|said|mention|mentioned)\b"
    r"|(which|what) (batch|semester|sem|programme|program|minor)\b.*\b(did|have) i\b.*\b(tell|told|say|said|mention|mentioned|give|gave)\b"
    r"|\bdo you remember\b|^what(?:'s| is) my (batch|semester|sem|programme|program)\b", re.I)
CORRECTION_RE = re.compile(r"\b(correction|actually|sorry|i meant|i mean|mistake|not \d)\b", re.I)
FOLLOW_UP_RE = re.compile(r"\b(does that|would that|will that|that change|your advice|your answer|what you said|in that case"
                          r"|then what|same question|still (true|apply|the case))\b", re.I)
NEW_QUESTION_RE = re.compile(r"\b(what|which|how|when|where|who|why|can|could|is|are|do|does|should|list|tell)\b", re.I)
# "how many credits is it?", "what if I was sick?": meaningless without the earlier turns
REFERS_BACK_RE = re.compile(r"\b(it|its|that|this|those|these|them|they)\b", re.I)
NOT_REFERRING_RE = re.compile(r"\b(this|that) (semester|sem|term|year)\b|\bis it (possible|true|mandatory|compulsory|allowed)\b", re.I)
LEANS_ON_TOPIC_RE = re.compile(r"^(what if|why\b|how so\b|how come\b|who (decides|approves|signs|do i|should i)\b|how long\b|how do i apply\b)", re.I)
SICK_RE = re.compile(r"\b(sick|ill|unwell|fever|hospital\w*|medical)\b", re.I)
OWN_SUBJECT_RE = re.compile(rf"\b[A-Z]{{3,4}}\d{{3}}\b|\b({MINOR_NAMES})\b", re.I)
FILLER_RE = re.compile(r"\b(can|could|may|should|do|does|did|will|would|is|are|i|me|my|we|take|took|register|enrol+|for|in|on|to|the|a|an"
                       r"|what|what's|whats|how|about|tell|more|mean|means|work|works|it|its|that|this|those|these|them|they)\b", re.I)


@dataclass
class Facts:
    programme: str | None = None
    batch: str | None = None
    semester: int | None = None
    minor: str | None = None
    minor_declared: bool | None = None
    minor_credits: int | None = None
    corrected: dict = field(default_factory=dict)  # field -> the value it replaced
    topic: str | None = None                       # the last real question, kept through corrections and recalls
    thread: list = field(default_factory=list)     # follow-ups asked since that question ("attendance?", "what if...")

    def known(self) -> bool:
        return any(value is not None for value in (self.programme, self.batch, self.semester, self.minor,
                                                   self.minor_declared, self.minor_credits))


def _set(facts: Facts, name: str, value, correcting: bool):
    old = getattr(facts, name)
    if old is not None and old != value and correcting:
        facts.corrected[name] = old
    setattr(facts, name, value)


def _is_statement(sentence: str) -> bool:
    """"BTech, 2024 batch, semester 5." tells us about the student. "Which courses are in semester 5?" does not."""
    s = _normalise(sentence).strip().lower()
    if re.match(QUESTION_START, s) or re.match(COMMAND_START, s):
        return False
    if re.search(SELF_STATEMENT, s):
        return True
    if s.endswith("?"):
        return False
    return not re.search(r"\b(courses?|subjects?|credits?)\b", s)


def _normalise(message: str) -> str:
    """Treat typographic apostrophes and B.Tech as their plain-text equivalents."""
    text = message.replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\bb\.\s*tech\b", "BTech", text, flags=re.I)


def _absorb(facts: Facts, message: str, asked_batch: bool, asked_minor: bool = False):
    for sentence in re.findall(r"[^.?!\n]+[.?!]?", _normalise(message)):
        if not _is_statement(sentence):
            continue
        low = sentence.lower()
        correcting = bool(CORRECTION_RE.search(low))
        # the value being withdrawn ("not 5", "not semester 5") must not be read as the new one
        kept = re.sub(r"\bnot\s+(?:in\s+)?(?:(?:semester|sem|batch)\s*)?\d+(?:st|nd|rd|th)?(?:\s*(?:semester|sem|batch))?", " ", low)
        if re.search(r"\bb\.?\s?tech\b", kept):
            _set(facts, "programme", "B.Tech", correcting)
        year = re.search(r"\b(20\d\d)\s*(?:batch|admission)\b|\b(?:batch|admitted|joined)\s*(?:of|in|is|:)?\s*(20\d\d)\b", kept)
        if not year and asked_batch and re.fullmatch(r"\W*(20\d\d)\W*(batch)?\W*", kept.strip()):
            year = re.search(r"(20\d\d)", kept)
        if year:
            _set(facts, "batch", next(g for g in year.groups() if g) if year.groups() else year.group(), correcting)
        sem = re.search(r"\b(?:semester|sem)\s*(?:is|:|=)?\s*(\d)\b|\b(\d)(?:st|nd|rd|th)\s*(?:semester|sem)\b", kept)
        if sem:
            _set(facts, "semester", int(next(g for g in sem.groups() if g)), correcting)
        minors = re.findall(rf"\b({MINOR_NAMES})\b", kept)
        preference = re.search(r"\b(i(?:'m| am| was)? (interested in|considering)|i (want|prefer|choose)|i'd like)\b", kept)
        bare_minor = asked_minor and re.fullmatch(rf"\W*({MINOR_NAMES})(?:\s+minor)?\W*", kept.strip())
        minor_context = "minor" in kept or asked_minor or bool(facts.topic and re.search(r"\bminors?\b", facts.topic, re.I))
        if len(minors) == 1 and (bare_minor or (preference and minor_context) or
                                ("minor" in kept and re.search(SELF_STATEMENT, low))):
            _set(facts, "minor", minors[0].capitalize(), correcting)
        declared = re.search(r"\bi (have not|haven't|did not|didn't|have|already)?\s*declared\s+"
                             r"(?:(?:a|my|the)\s+)?(?:(?:" + MINOR_NAMES + r")\s+)?minor\b", kept)
        if declared:
            _set(facts, "minor_declared", declared.group(1) not in ("have not", "haven't", "did not", "didn't"), correcting)
        credits = re.search(r"\bi(?:'ve| have)? (?:already )?(?:completed|earned|passed)\s+(\d+)\s+"
                            r"(?:(?:minor(?:/open)?|open/minor)\s+credits|credits\s+(?:towards?|for|in)\s+"
                            r"(?:(?:my|a|the)\s+)?minor)\b", kept)
        if credits:
            _set(facts, "minor_credits", int(credits.group(1)), correcting)


def _names_nothing(message: str) -> bool:
    """"can i take it?" has no subject of its own once the filler words are gone."""
    return not re.sub(r"\W+", "", FILLER_RE.sub(" ", message))


def _only_states_facts(message: str) -> bool:
    """"I am in the 2024 batch": details and no question."""
    probe = Facts()
    _absorb(probe, message, False)
    return probe.known() and "?" not in message and all(_is_statement(x) for x in re.findall(r"[^.?!\n]+", message))


def recall_kind(message: str, facts: "Facts | None" = None, history: list[dict] | None = None) -> str | None:
    message = _normalise(message)
    if SUMMARY_RE.search(message):
        return "summary"
    if TOPIC_RE.search(message):
        return "topic"
    if NEEDS_RE.search(message):
        return "needs"
    if facts is None or facts.topic or (history and history[-1].get("needs_clarification")):
        return None
    # Nothing earlier to lean on: ask, or acknowledge, rather than search the documents for "it".
    if REFERS_BACK_RE.search(message) and _names_nothing(message):
        return "unclear"
    if _only_states_facts(message):
        return "noted"
    return None


def is_follow_up(message: str, history: list[dict]) -> bool:
    m = message.strip()
    if not history:
        return False
    if history[-1].get("needs_clarification") or FOLLOW_UP_RE.search(m) or CORRECTION_RE.search(m):
        return True
    # A generic request for the courses continues a user-named minor/curriculum, not a retrieved example.
    if re.fullmatch(r"(?:which|what)(?: are)? (?:the )?(?:courses|subjects)(?: are there| are available| are offered)?\s*[?.!]*", m, re.I):
        previous = next((turn['content'] for turn in reversed(history) if turn['role'] == 'user'
                         and not recall_kind(turn['content']) and not _only_states_facts(turn['content'])), '')
        if re.search(r"\b(minors?|courses?|subjects?|curriculum)\b", previous, re.I):
            return True
    if re.match(r"(what|how) about\b|and\b|for\b|in\b|only\b", m, re.I) or LEANS_ON_TOPIC_RE.match(m):
        return True
    if len(m.split()) <= 10 and REFERS_BACK_RE.search(m) and not NOT_REFERRING_RE.search(m) and not OWN_SUBJECT_RE.search(m):
        return True
    return len(m.split()) <= 6 and not NEW_QUESTION_RE.search(m)


def from_history(history: list[dict], message: str | None = None) -> Facts:
    facts = Facts()
    turns = list(history) + ([{"role": "user", "content": message}] if message else [])
    last_assistant = ""
    seen: list[dict] = []
    for turn in turns:
        if turn["role"] != "user":
            last_assistant = turn["content"]
            seen.append(turn)
            continue
        text = turn["content"]
        _absorb(facts, text, bool(re.search(r"\bbatch\b", last_assistant, re.I)),
                bool(re.search(r"\bminor\b", last_assistant, re.I)))
        if not identity.response(text) and not recall_kind(text) and not CORRECTION_RE.search(text) and not _only_states_facts(text) \
                and not (not facts.topic and _names_nothing(text)):
            follow_up = is_follow_up(text, seen)
            asks = "?" in text or not _is_statement(text)
            if not follow_up or not facts.topic or (OWN_SUBJECT_RE.search(text) and asks):
                facts.topic, facts.thread = text, []  # "what about the Law minor?" moves the conversation on
            elif asks and turn is not turns[-1]:
                facts.thread.append(text)
        seen.append(turn)
    return facts


def _without_stated_values(text: str) -> str:
    """Drop batch, semester and programme from an old question: the current values are added back separately."""
    text = re.sub(r"\b(20\d\d)\s*batch\b|\bbatch\s*(of\s*)?20\d\d\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?:semester|sem)\s*\d\b|\b\d(?:st|nd|rd|th)\s*(?:semester|sem)\b", " ", text, flags=re.I)
    text = re.sub(r"\bb\.?\s?tech\b", " ", text, flags=re.I)
    return re.sub(r"^[\s,.]+|\s+(?=[,.])", "", re.sub(r"\s+", " ", text)).strip()


def contextual_query(message: str, history: list[dict], facts: Facts) -> str:
    """A follow-up is searched as the original question plus the student's current details."""
    if not is_follow_up(message, history):
        return message
    if SICK_RE.search(message):  # the handbook's words, not the student's, and whatever was discussed before
        return f"{message} medical leave of absence attendance relaxation medical exigencies"
    # Only what carries meaning goes into the search: "does that change your advice?" would just attract noise.
    kept = [x for x in re.findall(r"[^.?!\n]+[.?!]?", message) if not FOLLOW_UP_RE.search(x)]
    withdrawn = re.sub(r"\bnot\s+(?:(?:semester|sem|batch)\s*)?\d+(?:st|nd|rd|th)?|\b(correction|actually|sorry|i meant)\b\W*",
                       " ", " ".join(kept), flags=re.I)
    parts = [_without_stated_values(facts.topic or "")]
    if facts.topic != message:
        parts += [_without_stated_values(x) for x in facts.thread[-2:]] + [withdrawn.strip()]
    if facts.batch:
        parts.append(f"{facts.batch} batch")
    if facts.semester and not re.search(r"\b(?:semester|sem)\s*\d", withdrawn, re.I):
        parts.append(f"semester {facts.semester}")
    if facts.minor and re.search(r"\bminor\b", " ".join(parts), re.I) and not OWN_SUBJECT_RE.search(" ".join(parts)):
        parts.append(f"{facts.minor} minor")
    return " ".join(p for p in parts if p)


def correction_note(message: str, facts: Facts) -> str:
    """Says plainly what was updated, so a correction isn't answered as if nothing had happened."""
    if not CORRECTION_RE.search(message):
        return ""
    labels = {"semester": "Semester", "batch": "batch", "programme": "programme", "minor": "minor",
              "minor_declared": "minor declared", "minor_credits": "completed Minor/Open credits"}
    done = [f"{labels[k]} {getattr(facts, k)} (not {old})" for k, old in facts.corrected.items()]
    return f"Thanks, I've updated this to {' and '.join(done)}. Here's my advice for that:\n\n" if done else ""


def prompt_block(facts: Facts) -> str:
    if not facts.known() and not facts.topic:
        return ""
    lines = []
    if facts.programme:
        lines.append(f"programme: {facts.programme}")
    if facts.batch:
        lines.append(f"batch: {facts.batch}")
    if facts.semester:
        lines.append(f"current semester: {facts.semester}")
    if facts.minor:
        lines.append(f"minor of interest: {facts.minor}")
    if facts.minor_declared is not None:
        lines.append(f"minor declared: {facts.minor_declared}")
    if facts.minor_credits is not None:
        lines.append(f"completed Minor/Open credits: {facts.minor_credits}")
    if facts.topic:
        lines.append(f"active advising question: {_without_stated_values(facts.topic)}")
    lines += [f"the student corrected {k} (the old value {v} no longer applies)" for k, v in facts.corrected.items()]
    return ("<stated_by_student>\n" + "\n".join(lines) + "\nThe student told you these in this chat. Use them, do not ask "
            "for them again, and prefer them over any older value. They are facts about the student, not university "
            "rules.\n</stated_by_student>\n\n")


def _topic_label(facts: Facts) -> str | None:
    if not facts.topic:
        return None
    if re.search(r"\bminors?\b", facts.topic, re.I):
        return "whether you can take a minor"
    return f'your question: "{_without_stated_values(facts.topic)}"'


def _profile_value(profile: dict | None, key: str):
    return (profile or {}).get(key)


def missing_details(facts: Facts, profile: dict | None) -> list[str]:
    """Separate missing personal details from gaps in university policy; don't invent prerequisites."""
    missing = []
    if not (facts.programme or _profile_value(profile, "programme")):
        missing.append("your programme")
    if not (facts.batch or _profile_value(profile, "batch")):
        missing.append("your batch (year of admission)")
    if not (facts.semester or _profile_value(profile, "current_semester")):
        missing.append("your current semester")
    if facts.topic and re.search(r"\bminors?\b", facts.topic, re.I):
        if not (facts.minor or _profile_value(profile, "minor")):
            missing.append("which minor interests you, if you have one in mind (optional: it lets me list its courses)")
        if facts.minor_credits is None and _profile_value(profile, "courses_completed") is None:
            missing.append("which Minor/Open courses or credits you have already completed "
                           "(to tailor a plan, not an extra eligibility requirement)")
        if facts.minor_declared is None and not _profile_value(profile, "minor"):
            missing.append("whether you have declared a minor")
    elif _profile_value(profile, "courses_completed") is None:
        missing.append("the courses you have passed, if your question is about a specific course")
    return missing


def recall_answer(kind: str, facts: Facts, profile: dict | None) -> str:
    batch = facts.batch or _profile_value(profile, "batch")
    semester = facts.semester or _profile_value(profile, "current_semester")
    topic = _topic_label(facts)
    if kind == "topic":
        if not topic:
            return "You haven't asked an academic advising question in this chat yet. What would you like help with?"
        details = ", ".join(x for x in (facts.programme, f"{batch} batch" if batch else None,
                                       f"semester {semester}" if semester else None) if x)
        return f"You were asking about {topic}." + (f" Your current details are: {details}." if details else "")
    if kind == "unclear":
        return ("I'm not sure what \"it\" refers to yet. Which course, minor or rule do you mean? "
                "A course code or name is enough, for example DATA301 or the Law minor.")
    if kind == "noted":
        known = ", ".join(x for x in (facts.programme, f"{batch} batch" if batch else None,
                                      f"semester {semester}" if semester else None) if x)
        return f"Noted: {known}. What would you like to know about your courses, credits or regulations?"
    if kind == "needs":
        missing = missing_details(facts, profile)
        have = [x for x in (facts.programme, f"{batch} batch" if batch else None,
                            f"semester {semester}" if semester else None) if x]
        opening = f"I already have: {', '.join(have)}." if have else "I don't have any details about you yet."
        ask = "\n".join(f"- {m}" for m in missing) if missing else "Nothing else: I have what I need."
        return f"{opening}\n\nTo advise you{' on ' + topic if topic else ''}, I still need:\n{ask}"
    lines = []
    if facts.programme or _profile_value(profile, "programme"):
        lines.append(f"- Programme: {facts.programme or profile['programme']}")
    if batch:
        lines.append(f"- Batch: {batch}" + _corrected_note(facts, "batch"))
    if semester:
        lines.append(f"- Current semester: {semester}" + _corrected_note(facts, "semester"))
    if facts.minor:
        lines.append(f"- Minor of interest: {facts.minor}" + _corrected_note(facts, "minor"))
    if facts.minor_declared is not None:
        lines.append("- Minor declared: " + ("yes" if facts.minor_declared else "no"))
    if facts.minor_credits is not None:
        lines.append(f"- Completed Minor/Open credits: {facts.minor_credits}" + _corrected_note(facts, "minor_credits"))
    if profile and profile.get("cgpa") is not None:
        lines.append(f"- From your selected record: CGPA {profile['cgpa']}, {profile.get('completed_credits')} credits earned")
    if topic:
        lines.append(f"- We were discussing {topic}")
    if not lines:
        return ("You haven't told me anything about yourself in this chat yet. If you share your batch and current "
                "semester, I can give you advice that fits your programme.")
    missing = missing_details(facts, profile)
    if missing:
        lines.append("- Still unknown or not yet confirmed: " + "; ".join(missing))
    return "Here's what I know from this conversation:\n" + "\n".join(lines) + \
        "\n\nI only keep this for this chat. Tell me if anything has changed."


def _corrected_note(facts: Facts, name: str) -> str:
    return f" (you corrected this from {facts.corrected[name]})" if name in facts.corrected else ""
