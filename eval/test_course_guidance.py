"""Course discovery must clarify scope, enumerate exact rows, and choose relevant visuals."""
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import advisor
import llm
import memory
import multimodal
import structured


def append(history, message, reply):
    return history + [{"role": "user", "content": message},
                      {"role": "assistant", "content": reply.answer + " " + (reply.clarifying_question or ""),
                       "needs_clarification": reply.needs_clarification}]


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(llm, "call_structured", lambda *_: pytest.fail("Course lists must not be sampled by a model"))


@pytest.mark.parametrize("strategy", ["structured", "rag", "rag_structured", "agentic"])
@pytest.mark.parametrize("message", ["which courses are there ?", "What courses do you offer?", "Show me the courses", "Which subjects are available?"])
def test_vague_course_request_asks_scope_before_retrieval(no_model, monkeypatch, strategy, message):
    monkeypatch.setattr(advisor, "retrieve", lambda *_: pytest.fail("Clarify before retrieving"))
    reply = advisor.answer(message, strategy, guarded=True, use_classifier=False)
    assert reply.needs_clarification and not reply.insufficient_information
    assert not reply.sources and not reply.attachments
    assert "semester" in reply.clarifying_question.lower() and "minor" in reply.clarifying_question.lower()
    assert reply.suggested_questions


@pytest.mark.parametrize("strategy", ["rag", "rag_structured", "agentic"])
def test_course_discovery_advances_one_question_at_a_time(no_model, strategy):
    history = []
    for message, expected in [("Which courses are there?", "minor"), ("Semester courses", "batch"),
                              ("2024 batch", "semester")]:
        reply = advisor.answer(message, strategy, history=history, guarded=True, use_classifier=False)
        assert reply.needs_clarification and expected in reply.clarifying_question.lower()
        history = append(history, message, reply)
    reply = advisor.answer("Semester 3", strategy, history=history, guarded=True, use_classifier=False)
    assert not reply.needs_clarification and reply.provider == advisor.DATABASE_PROVIDER
    with structured._db() as con:
        codes = [row[0] for row in con.execute("SELECT course_code FROM courses WHERE kind='programme' AND batch='2024' AND semester=3 AND code_status!='choice_slot'")]
    assert all(code in reply.answer for code in codes)
    assert reply.attachments and reply.attachments[0]['semester'] == 3
    assert reply.attachments[0]['batch'] == '2024' and reply.suggested_questions


def test_minor_follow_up_uses_user_topic_and_never_combines_batches(no_model):
    history = [{"role": "user", "content": "Tell me about the Design minor"},
               {"role": "assistant", "content": "There are Design courses in several batches."}]
    ask = advisor.answer("Which courses are there?", history=history, guarded=True, use_classifier=False)
    assert ask.needs_clarification and "batch" in ask.clarifying_question.lower()
    history = append(history, "Which courses are there?", ask)
    reply = advisor.answer("2024", history=history, guarded=True, use_classifier=False)
    assert not reply.needs_clarification and "CDES217" in reply.answer and "CDES227" in reply.answer
    assert "CDES504" not in reply.answer and "CDES203" not in reply.answer
    assert "8 more credits" in reply.answer
    assert reply.attachments[0]['minor'] == 'Design'


def test_assistant_design_claims_do_not_define_user_scope(no_model):
    history = [{"role":"user", "content":"I want to study at Vidyashilp University"},
               {"role":"assistant", "content":"Here are Design minor courses: CDES504, CDES203."}]
    reply = advisor.answer("Which courses are there?", history=history, guarded=True, use_classifier=False)
    assert reply.needs_clarification and "minor" in reply.clarifying_question.lower()
    assert "Design" not in reply.answer


def test_full_curriculum_has_all_named_courses_and_an_automatic_map(no_model):
    reply = advisor.answer("List courses for all semesters of the 2024 batch", guarded=True, use_classifier=False)
    with structured._db() as con:
        codes = [row[0] for row in con.execute("SELECT course_code FROM courses WHERE kind='programme' AND batch='2024' AND code_status NOT IN ('choice_slot','placeholder')")]
    assert not reply.needs_clarification and all(code in reply.answer for code in codes)
    assert reply.attachments and reply.attachments[0]['batch'] == '2024'


@pytest.mark.parametrize('message', ['Show the course structure for the 2024 batch',
                                     'Explain the curriculum for the 2024 batch',
                                     'How are credits distributed for the 2024 batch?'])
def test_structure_and_credit_overviews_get_a_map_without_a_graphic_request(no_model, message):
    reply = advisor.answer(message, guarded=True, use_classifier=False)
    assert reply.attachments and reply.attachments[0]['automatic']
    assert 'Basket' in reply.answer and not reply.needs_clarification


def test_course_list_spelling_does_not_fall_back_to_semantic_samples(no_model):
    reply = advisor.answer('Show the course list', guarded=True, use_classifier=False)
    assert reply.needs_clarification and reply.suggested_questions


def test_other_degree_requests_do_not_receive_btech_subjects(no_model):
    reply = advisor.answer('List BBA courses for the 2024 batch', guarded=True, use_classifier=False)
    assert reply.needs_clarification and not reply.attachments and 'UCOR205' not in reply.answer
    assert 'catalogue' in reply.answer


def test_course_request_scope_follows_personal_corrections(no_model):
    first = 'List courses in Semester 5 for the 2024 batch'
    reply = advisor.answer(first, guarded=True, use_classifier=False)
    history = append([], first, reply)
    correction = "Correction: I'm in the 2023 batch, semester 3. Does that change the courses?"
    corrected = advisor.answer(correction, history=history, guarded=True, use_classifier=False)
    assert '2023 batch' in corrected.answer and 'Semester 3' in corrected.answer
    history = append(history, correction, corrected)
    follow_up = advisor.answer('Which courses are there?', history=history, guarded=True, use_classifier=False)
    assert '2023 batch' in follow_up.answer and 'Semester 3' in follow_up.answer


def test_current_profile_supplies_details_without_being_dropped(no_model):
    reply = advisor.answer("Which courses are in my current semester?", student_id="SYN-001", guarded=True, use_classifier=False)
    assert not reply.needs_clarification and "2024" in reply.answer and "Semester 5" in reply.answer


def test_unrelated_topic_does_not_keep_an_old_minor(no_model):
    history = [{"role":"user", "content":"Tell me about the Design minor"},
               {"role":"assistant", "content":"..."},
               {"role":"user", "content":"What is the attendance rule?"},
               {"role":"assistant", "content":"75%"}]
    reply = advisor.answer("Which courses are there?", history=history, guarded=True, use_classifier=False)
    assert reply.needs_clarification and "semester" in reply.clarifying_question.lower()


def test_topic_recall_retains_the_minor_after_a_generic_course_follow_up():
    history = [{"role":"user", "content":"Tell me about the Design minor"},
               {"role":"assistant", "content":"..."}]
    facts = memory.from_history(history, "Which courses are there?")
    assert "Design minor" in facts.topic


def test_text_only_request_does_not_get_an_automatic_chart(no_model):
    reply = advisor.answer("List the Finance minor courses for the 2024 batch, text only, no infographic", guarded=True, use_classifier=False)
    assert not reply.needs_clarification and not reply.attachments and "MGMT208" in reply.answer


def test_attendance_and_recall_do_not_get_irrelevant_curriculum_maps(no_model):
    reply = advisor.answer("What is the minimum attendance?", guarded=True, use_classifier=False)
    assert not reply.attachments
    recall = advisor.answer("Summarise what you know about me", guarded=True, use_classifier=False)
    assert not recall.attachments


def test_scoped_minor_svg_includes_unknown_credits_without_assigning_a_semester():
    svg = multimodal.infographic_svg("2024", minor="Design")
    ElementTree.fromstring(svg)
    assert "Design minor" in svg and "CDES217" in svg and "CDES504" not in svg
    assert "8 credits" in svg and "not yet scheduled" in svg


def test_scoped_semester_svg_does_not_include_other_semesters():
    svg = multimodal.infographic_svg("2024", semester=3)
    ElementTree.fromstring(svg)
    assert "Semester 3" in svg and "Semester 8" not in svg


def test_unavailable_minor_has_no_misleading_visual():
    assert multimodal.infographic_svg("2024", minor="Economics") is None
