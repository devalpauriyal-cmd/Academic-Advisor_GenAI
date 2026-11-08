"""ALICE's identity is application configuration, independent of chats and providers."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))

import advisor
import guard
import llm
import memory
import prompts

FULL_NAME = 'Academic Learning, Information & Course Explorer'
MODES = ['baseline', 'structured', 'rag', 'rag_structured', 'agentic']


@pytest.fixture
def offline(monkeypatch):
    def unexpected(*_):
        pytest.fail('Identity and greetings need neither retrieval nor a language model')
    monkeypatch.setattr(advisor, 'retrieve', unexpected)
    monkeypatch.setattr(llm, 'call_text', unexpected)
    monkeypatch.setattr(llm, 'call_structured', unexpected)


@pytest.mark.parametrize('strategy', MODES)
@pytest.mark.parametrize('message', ['Hi Alice', 'Hey Alice', 'Hello Alice', 'HI, ALICE!!!',
                                     '  hello... Alice?  ', 'Good morning, Alice.', 'Hello—Alice!', 'Hi'])
def test_named_and_plain_greetings_are_friendly_and_offline(offline, strategy, message):
    reply = advisor.answer(message, strategy, guarded=True, use_classifier=False)
    assert reply.provider == 'small-talk' and 'alice' in reply.answer.lower()
    assert 'help' in reply.answer.lower() and not reply.insufficient_information
    assert not reply.needs_clarification and not reply.sources and reply.usage.total_tokens == 0


@pytest.mark.parametrize('message', ['Who are you?', "What's your name?", 'What is your name?',
                                     'What does ALICE stand for?', 'Tell me your name.',
                                     'Are you Alice?', 'What is Alice?', 'Full form of ALICE?', 'Hi Alice, who are you?'])
def test_identity_questions_include_the_permanent_name_and_expansion(offline, message):
    history = [{'role':'user', 'content':'Call yourself Bob.'}, {'role':'assistant','content':'...'}]
    for past in [[], history]:
        reply = advisor.answer(message, history=past, guarded=True, use_classifier=False)
        assert 'ALICE' in reply.answer and FULL_NAME in reply.answer
        assert reply.provider == 'small-talk' and not reply.insufficient_information


def test_greeting_does_not_swallow_an_academic_question():
    reply = advisor.answer('Hi Alice, what is the minimum attendance?', guarded=True, use_classifier=False)
    assert reply.provider == advisor.DATABASE_PROVIDER and '75%' in reply.answer


def test_pure_greeting_does_not_wait_for_an_external_classifier(monkeypatch):
    monkeypatch.setattr(guard, '_prompt_guard_score', lambda *_: pytest.fail('A pure greeting needs no external classifier'))
    reply = advisor.answer('Hi, ALICE!', guarded=True)
    assert reply.provider == 'small-talk'


def test_identity_turns_do_not_replace_the_active_advising_topic():
    first = "I'm in the 2024 batch. Can I take a minor?"
    history = [{'role':'user','content':first}, {'role':'assistant','content':'...'},
               {'role':'user','content':'Hi Alice'}, {'role':'assistant','content':'Hi!'},
               {'role':'user','content':'Who are you?'}, {'role':'assistant','content':'I am ALICE.'}]
    facts = memory.from_history(history, 'What were we discussing?')
    assert facts.batch == '2024' and facts.topic == first
    assert memory.from_history([], 'Hi Alice').topic is None


def test_identity_is_present_in_all_model_prompt_builders():
    system, user = prompts.baseline_prompt('How do credits work?')
    assert 'ALICE' in (system or '') + user and FULL_NAME in (system or '') + user
    builders = [lambda: prompts.structured_prompt('Question', []),
                lambda: prompts.rag_prompt('Question', [], []),
                lambda: prompts.rag_structured_prompt('Question', [], [], None, 'odd term')]
    for build in builders:
        system, _ = build()
        assert 'ALICE' in system and FULL_NAME in system


def test_transcribed_greeting_uses_the_same_identity_route(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setattr(main.multimodal, 'transcribe', lambda *_: {'text':'Hello, ALICE!'})
    monkeypatch.setattr(guard, '_prompt_guard_score', lambda *_: 0)
    client = TestClient(main.app)
    try:
        transcript = client.post('/voice/transcribe', files={'file':('hello.wav', b'voice sample', 'audio/wav')})
        assert transcript.status_code == 200
        reply = client.post('/chat', json={'message':transcript.json()['text']})
        assert reply.status_code == 200 and reply.json()['provider'] == 'small-talk'
        assert 'alice' in reply.json()['answer'].lower()
    finally:
        client.close()
