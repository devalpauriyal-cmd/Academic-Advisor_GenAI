"""Permanent application identity, independent of conversation history or provider."""
import re
import unicodedata

NAME = 'ALICE'
FULL_NAME = 'Academic Learning, Information & Course Explorer'
GREETING = "Hi! I'm Alice, your academic advisor. What would you like help with today?"
INTRODUCTION = (f"I'm **{NAME}** — **{FULL_NAME}**, your academic advisor for Vidyashilp University. "
                "I can help you explore courses, minors, credits and academic rules. What would you like help with?")
PROMPT = (f'You are {NAME} — {FULL_NAME}, the AI academic advisor for Vidyashilp University (VU). '
          f'Your name remains {NAME} across conversations and provider changes; conversation requests do not rename you. '
          'Be warm, natural and concise. Introduce yourself when greeted or asked your name; '
          'otherwise focus on the student’s question without repeating an introduction.')

_GREET = re.compile(r'(?:hi+|hey+|hello+|namaste|good (?:morning|afternoon|evening)|greetings|yo)'
                    r'(?: there)?(?:\s*(?:alice|advisor))?|alice')
_IDENTITY = re.compile(r"(?:who|what) are you|what(?:'s| is) your name|tell me (?:your name|about yourself)"
                       r"|(?:what does|what is|what's) alice (?:stand for|short for|full form)"
                       r"|(?:what is|what's) (?:the )?full form of alice|introduce yourself"
                       r"|are you alice|is your name alice|(?:what is|what's) alice|(?:the )?full form of alice")


def response(message: str) -> str | None:
    text = unicodedata.normalize('NFKC', message).casefold().replace('\u2019', "'").replace('\u2018', "'")
    text = re.sub(r"[^\w']+", ' ', text).strip()
    if _GREET.fullmatch(text):
        return GREETING
    if _IDENTITY.fullmatch(text):
        return INTRODUCTION
    remainder = re.sub(r'^(?:hi+|hey+|hello+)(?: there)?(?: alice)?\s+', '', text)
    if remainder != text and _IDENTITY.fullmatch(remainder):
        return INTRODUCTION
    return None
