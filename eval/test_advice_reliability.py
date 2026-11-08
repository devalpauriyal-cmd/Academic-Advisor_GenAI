"""Regression cases for evidence binding, term selection, and conflicting records."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))

import advisor
import agents
import llm
import memory
import academic_term
from schemas import AdvisorResponse, Source, Usage


def reply(answer, section='Credit rule'):
    return AdvisorResponse(answer=answer, confidence='high', grounded=True,
                           sources=[Source(source_file='Handbook.pdf', section=section)],
                           needs_clarification=False, clarifying_question=None,
                           insufficient_information=False, conflict_detected=False)


def chunk(text, section='Credit rule'):
    return {'text': text, 'source_file':'Handbook.pdf', 'section':section}


@pytest.mark.parametrize('claim,evidence', [
    ('You need 8 credits.', 'The student is in Semester 8.'),
    ('You need 8 credits.', 'The student has earned 8 credits.'),
    ('You do not need 8 credits.', 'The requirement is 8 credits.'),
    ('DATA301 is worth 4 credits.', 'COMP203 is worth 4 credits. DATA301 is worth 3 credits.'),
    ('MATH301 is worth 4 credits.', 'DATA301 Machine Learning | 4 credits | prerequisites: MATH301.'),
    ('math301 is worth 4 credits.', 'DATA301 Machine Learning | 4 credits | prerequisites: MATH301.'),
    ('You need 75% attendance.', 'The fee discount is 75%.'),
    ('The Finance minor requires 8 credits.', 'The Design minor requires 8 credits. The Finance minor requires 24 credits.'),
])
def test_unrelated_values_do_not_verify_a_claim(claim, evidence):
    draft = reply(claim)
    assert agents.verify(draft, evidence, [])
    checked = advisor.finish(draft, [chunk(evidence)])
    assert not checked.grounded and checked.confidence == 'low'


@pytest.mark.parametrize('claim,evidence', [
    ('You need 8 credits.', 'The requirement is 8 credits.'),
    ('DATA301 is worth 4 credits.', 'DATA301 Machine Learning | credits: 4 | semester: 5'),
    ('The minimum attendance is 75%.', 'The minimum attendance is 75 % of classes conducted.'),
    ('The minor requires 24 credits.', 'The minor requires 24 credits.'),
    ('The minimum CGPA is 5.0.', 'The minimum CGPA is 5.00.'),
])
def test_supported_values_are_not_rejected(claim, evidence):
    assert not agents.verify(reply(claim), evidence, [])


def test_clarifying_questions_are_not_mistaken_for_policy_claims():
    question = reply('Have you completed 8 credits?')
    question = question.model_copy(update={'needs_clarification':True, 'sources':[], 'grounded':False})
    assert not agents.verify(question, '', [])
    mixed = question.model_copy(update={'answer':'You need 99 credits. Have you completed them?'})
    assert agents.verify(mixed, '', [])
    assert not agents.verify(reply("I can't confirm the suggested 8-credit requirement."), '', [])


def test_real_sql_course_rows_bind_credits_to_the_primary_course():
    import structured
    chunks = structured.course_lookup(['DATA301'], ['2024'])
    source = Source(source_file=chunks[0]['source_file'], section=chunks[0]['section'])
    correct = reply('DATA301 is worth 4 credits.').model_copy(update={'sources':[source]})
    assert not agents.verify(correct, chunks, [])
    wrong = correct.model_copy(update={'answer':'MATH301 is worth 4 credits.'})
    assert agents.verify(wrong, chunks, [])


def test_credit_table_does_not_give_a_prerequisite_the_primary_course_credits():
    text = '| Code | Credits | Prerequisites |\n|---|---|---|\n| DATA301 | 4 | MATH301 |'
    assert not agents.verify(reply('DATA301 is worth 4 credits.'), text, [])
    assert agents.verify(reply('MATH301 is worth 4 credits.'), text, [])


def test_only_cited_sources_support_numeric_claims():
    draft = reply('DATA301 is worth 4 credits.', 'Other course')
    chunks = [chunk('COMP203 is worth 4 credits.', 'Other course'),
              chunk('DATA301 is worth 3 credits.', 'DATA301')]
    checked = advisor.finish(draft, chunks)
    assert not checked.grounded


@pytest.mark.parametrize('strategy', ['rag', 'rag_structured', 'agentic'])
def test_user_suggested_number_is_not_an_authority(monkeypatch, strategy):
    chunks = [chunk('A medical leave of absence requires supporting documents.')]
    monkeypatch.setattr(advisor, 'retrieve', lambda *_: [{**chunks[0], 'score': .9}])
    monkeypatch.setattr(advisor, 'gather_context', lambda *_: ([], [{**chunks[0], 'score': .9}]))
    monkeypatch.setattr(advisor, 'assemble_chunks', lambda *args: chunks)
    calls = []
    def model(*_):
        calls.append(1)
        return reply('You need 8 credits for medical leave.'), 'groq:test', Usage()
    monkeypatch.setattr(llm, 'call_structured', model)
    result = advisor.answer('Do I need 8 credits for a medical leave of absence?', strategy,
                            guarded=True, use_classifier=False)
    assert len(calls) == 2
    assert not result.grounded and result.confidence == 'low'
    assert not result.answer.startswith('You need 8 credits')


@pytest.mark.parametrize('query,expected', [
    ('Can I take COMP202 in an even term?', 'even'),
    ('Can I take COMP202 in an odd semester?', 'odd'),
    ('Can I take COMP202 in Semester 6?', 'even'),
    ('Can I take COMP202 in the 3rd semester?', 'odd'),
    ('Can I take COMP202 next semester?', 'even'),
])
def test_explicit_requested_term_is_used(query, expected):
    profile = {**advisor.load_profiles()['SYN-001'], 'courses_completed':[], 'courses_failed':[]}
    checks, _ = agents.eligibility_agent(['COMP202'], profile, query)
    assert checks[0]['term'] == expected


def test_summer_offering_is_not_inferred_from_curriculum_parity():
    profile = {**advisor.load_profiles()['SYN-001'], 'courses_completed':[], 'courses_failed':[]}
    checks, _ = agents.eligibility_agent(['COMP202'], profile, 'Can I take COMP202 in summer?')
    assert checks[0]['verdict'] == 'cannot_determine'


def test_next_term_follows_the_documented_current_term(monkeypatch):
    monkeypatch.setattr(academic_term, 'current_term', lambda: 'even')
    assert academic_term.resolve('Can I take COMP202 next semester?').kind == 'odd'


def test_requested_term_is_not_overridden_by_contextual_current_semester():
    assert academic_term.resolve('Can I register for COMP202? semester 5', 'Can I register for COMP202 in Semester 6?').kind == 'even'


def test_ambiguous_explicit_terms_are_not_silently_chosen():
    assert academic_term.resolve('Can I take COMP202 in the even term, Semester 5?').kind is None


def test_missing_course_is_not_positive_eligibility_evidence():
    profile = {**advisor.load_profiles()['SYN-001'], 'courses_completed':[], 'courses_failed':[]}
    checks, _ = agents.eligibility_agent(['FAKE999'], profile, 'Can I take FAKE999?')
    assert checks and checks[0]['verdict'] == 'cannot_determine'
    assert agents.verify(reply('Yes, you can take FAKE999.'), 'FAKE999 was not found.', checks)


def test_rejection_does_not_omit_a_known_failed_prerequisite():
    checks = agents.eligibility_checks('Can I register for DATA301 in an even term?', advisor.load_profiles()['SYN-001'])
    draft = reply('No, you cannot register for DATA301 in an even term. Wait for the next odd term.')
    problems = agents.verify(draft, 'DATA301 is in semester 5.', checks)
    assert any('MATH301' in problem and 'omits' in problem for problem in problems)


def test_default_mode_receives_computed_eligibility_before_drafting(monkeypatch):
    prompts = []
    def model(system, user):
        prompts.append(user)
        return llm.FALLBACK_RESPONSE, 'none', Usage()
    monkeypatch.setattr(llm, 'call_structured', model)
    advisor.answer('Can I register for DATA301 in an even term?', student_id='SYN-001',
                   guarded=True, use_classifier=False)
    assert 'COURSE ELIGIBILITY AGENT' in prompts[0] and "Failed: ['MATH301']" in prompts[0]


def test_unknown_summer_offering_does_not_support_categorical_denial():
    profile = {**advisor.load_profiles()['SYN-001'], 'courses_completed':[], 'courses_failed':[]}
    checks, _ = agents.eligibility_agent(['COMP202'], profile, 'Can I take COMP202 in summer?')
    assert agents.verify(reply('You cannot take COMP202 in summer.'), 'COMP202 is an odd-semester course.', checks)


@pytest.mark.parametrize('strategy', ['rag', 'rag_structured', 'agentic'])
@pytest.mark.parametrize('details', ["I'm in the 2023 batch.", "I'm currently in semester 3."])
def test_conflicting_record_pauses_personal_decisions(monkeypatch, strategy, details):
    monkeypatch.setattr(llm, 'call_structured', lambda *_: pytest.fail('Resolve the record conflict first'))
    history = [{'role':'user','content':details}, {'role':'assistant','content':'Noted.'}]
    result = advisor.answer('Can I register for DATA301?', strategy, 'SYN-001', history,
                            guarded=True, use_classifier=False)
    assert result.needs_clarification and 'record' in result.clarifying_question.lower()
    assert 'Use the selected record' in result.suggested_questions


def test_record_choice_resumes_the_original_question(monkeypatch):
    history = [{'role':'user','content':"I'm in the 2023 batch."}, {'role':'assistant','content':'Noted.'}]
    message = 'Can I register for DATA301?'
    first = advisor.answer(message, 'rag_structured', 'SYN-001', history, guarded=True, use_classifier=False)
    history += [{'role':'user','content':message}, {'role':'assistant',
                 'content':first.answer + ' ' + (first.clarifying_question or ''), 'needs_clarification':True}]
    prompts = []
    def model(system, user):
        prompts.append(user)
        return reply('You are not eligible: MATH301 is failed.'), 'groq:test', Usage()
    monkeypatch.setattr(llm, 'call_structured', model)
    result = advisor.answer('Use the selected record', 'rag_structured', 'SYN-001', history,
                            guarded=True, use_classifier=False)
    assert not result.needs_clarification and prompts
    assert '<student_question>\nCan I register for DATA301?' in prompts[0]
    assert 'batch: 2023' not in prompts[0].split('</stated_by_student>')[0]


def test_discarding_conflicting_record_does_not_reuse_its_grades(monkeypatch):
    monkeypatch.setattr(llm, 'call_structured', lambda *_: pytest.fail('A personal decision needs a matching record'))
    history = [{'role':'user','content':"I'm in the 2023 batch."}, {'role':'assistant','content':'Noted.'}]
    question = 'Can I register for DATA301?'
    first = advisor.answer(question, 'rag_structured', 'SYN-001', history, guarded=True, use_classifier=False)
    history += [{'role':'user','content':question}, {'role':'assistant',
                 'content':first.answer + ' ' + (first.clarifying_question or ''), 'needs_clarification':True}]
    result = advisor.answer('Continue without the selected record', 'rag_structured', 'SYN-001', history,
                            guarded=True, use_classifier=False)
    assert result.needs_clarification and 'MATH301 is failed' not in result.answer


def test_general_policy_does_not_require_resolving_personal_record():
    history = [{'role':'user','content':"I'm in the 2023 batch."}, {'role':'assistant','content':'Noted.'}]
    result = advisor.answer('What is the minimum attendance?', 'rag_structured', 'SYN-001', history,
                            guarded=True, use_classifier=False)
    assert not result.needs_clarification and '75%' in result.answer


def test_later_correction_reopens_a_resolved_record_conflict():
    history = [{'role':'user','content':"I'm in the 2023 batch."}, {'role':'assistant','content':'Noted.'}]
    message = 'Can I register for DATA301?'
    first = advisor.answer(message, 'rag_structured', 'SYN-001', history, guarded=True, use_classifier=False)
    history += [{'role':'user','content':message}, {'role':'assistant',
                 'content':first.answer + ' ' + first.clarifying_question, 'needs_clarification':True},
                {'role':'user','content':'Use the selected record'}, {'role':'assistant','content':'Using the record.'},
                {'role':'user','content':"Actually, I'm in the 2023 batch."}, {'role':'assistant','content':'Noted.'}]
    result = advisor.answer(message, 'rag_structured', 'SYN-001', history, guarded=True, use_classifier=False)
    assert result.needs_clarification and 'record' in result.clarifying_question
