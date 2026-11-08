"""Regression coverage for natural conversation follow-ups, including the reported chat."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import advisor
import llm
import memory

FIRST = "I’m a BTech student from the 2024 batch, currently in semester 5. Can I take a minor?"
TURNS = [FIRST, "Which batch and semester did I tell you?",
         "What details do you still need from me?",
         "Correction: I’m in semester 3, not 5. Does that change your advice?",
         "What was I asking for advice about?",
         "Summarise what you know about me, including anything still unknown."]


def history(*messages):
    return [turn for message in messages for turn in
            ({"role": "user", "content": message}, {"role": "assistant", "content": "..."})]


@pytest.mark.parametrize("strategy", ["rag_structured", "agentic"])
def test_reported_conversation_works_without_a_language_model(monkeypatch, strategy):
    monkeypatch.setattr(llm, "call_structured", lambda *_: pytest.fail("This conversation needs no model"))
    turns, replies = [], []
    for message in TURNS:
        reply = advisor.answer(message, strategy, history=turns, guarded=True, use_classifier=False)
        replies.append(reply)
        turns += [{"role": "user", "content": message},
                  {"role": "assistant", "content": reply.answer,
                   "needs_clarification": reply.needs_clarification}]
    assert all(not r.insufficient_information and r.usage.total_tokens == 0 for r in replies)
    assert "2024" in replies[2].answer and "which minor" in replies[2].answer.lower()
    assert "Semester 3 (not 5)" in replies[3].answer and "Finance" in replies[3].answer
    assert "earlier semesters" not in replies[3].answer
    assert "minor" in replies[4].answer.lower() and "2024" in replies[4].answer
    assert "Current semester: 3" in replies[5].answer
    assert "corrected this from 5" in replies[5].answer
    assert "minor" in replies[5].answer.lower() and "unknown" in replies[5].answer.lower()
    assert "completed" in replies[5].answer.lower()


@pytest.mark.parametrize("message", [
    "What details do you still need from me?", "What else should I tell you?",
    "Is there anything else you need?", "What information are you missing about me?",
    "What do you still need to know?",
    "What was I asking for advice about?", "What were we discussing?",
    "Remind me of my original question.", "What did I ask you about?",
])
@pytest.mark.parametrize("strategy", ["structured", "rag", "rag_structured", "agentic"])
def test_meta_questions_preserve_the_goal_and_bypass_retrieval(monkeypatch, message, strategy):
    def unexpected(*_):
        pytest.fail("Conversation recall must not use retrieval or a model")
    monkeypatch.setattr(advisor, "retrieve", unexpected)
    monkeypatch.setattr(llm, "call_structured", unexpected)
    prior = history(FIRST)
    reply = advisor.answer(message, strategy, history=prior, guarded=True, use_classifier=False)
    assert reply.provider == advisor.MEMORY_PROVIDER
    assert "minor" in memory.from_history(prior, message).topic.lower()
    assert not reply.insufficient_information


def test_smart_apostrophes_and_dotted_programme_are_understood():
    facts = memory.from_history([], "I’m a B.Tech student, batch 2024, semester 5. Can I take a minor?")
    assert (facts.programme, facts.batch, facts.semester) == ("B.Tech", "2024", 5)


def test_summary_does_not_invent_unknown_progress():
    facts = memory.from_history(history(*TURNS[:-1]), TURNS[-1])
    answer = memory.recall_answer("summary", facts, None)
    assert "unknown" in answer.lower() and "completed" in answer.lower()
    assert "minor" in answer.lower() and "What was I asking" not in answer


def test_real_topic_switch_is_retained():
    facts = memory.from_history(history(FIRST, "What is the minimum attendance?"), "What were we discussing?")
    assert "attendance" in facts.topic.lower() and "minor" not in facts.topic.lower()


def test_answers_to_requested_minor_details_are_remembered():
    prior = history(FIRST, "What details do you still need from me?")
    prior[-1]["content"] = "Which minor interests you?"
    prior += history("Finance", "I haven't declared a minor. I have completed 8 Minor/Open credits.")
    facts = memory.from_history(prior, "What do you still need to know?")
    assert facts.minor == "Finance" and facts.minor_credits == 8 and facts.minor_declared is False
    assert memory.missing_details(facts, None) == []
    summary = memory.recall_answer("summary", facts, None)
    assert "Finance" in summary and "Completed Minor/Open credits: 8" in summary
    assert "Minor declared: no" in summary
    assert "Finance minor" in memory.contextual_query("How many credits does it have?", prior, facts)


def test_minor_preference_correction_does_not_become_a_declaration():
    facts = memory.from_history(history(FIRST, "I'm interested in Finance."),
                                "Actually, I'm interested in the Law minor.")
    assert facts.minor == "Law" and facts.corrected["minor"] == "Finance"
    assert facts.minor_declared is None and "minor" in facts.topic.lower()


@pytest.mark.parametrize("message", ["Have I completed 8 minor credits?", "I haven't completed 8 minor credits."])
def test_unconfirmed_minor_progress_is_not_stored(message):
    assert memory.from_history(history(FIRST), message).minor_credits is None


@pytest.mark.parametrize("strategy", ["rag", "rag_structured", "agentic"])
def test_model_outage_is_not_presented_as_missing_university_policy(monkeypatch, strategy):
    monkeypatch.setattr(llm, "call_structured", lambda *_: (llm.FALLBACK_RESPONSE, "none", llm.Usage()))
    reply = advisor.answer("What is the rule for a medical leave of absence?", strategy,
                           guarded=True, use_classifier=False)
    assert reply.service_unavailable
    assert "could not reach" in reply.answer
    assert advisor.CONTACT_HINT not in reply.answer
