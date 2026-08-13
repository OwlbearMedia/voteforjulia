"""Shared hostile-and-real input corpus for anything that transforms user text.

## Why this exists

On PR #138 the confirmation greeting shipped with a filter built on
`str.isalpha()`, which is false for a Unicode combining mark. It deleted them:
decomposed "José" became "Jose", and "अनुराधा" became "अनरध", which is not a
spelling of anything. The tests passed, and the deletion check passed — removing
the filter failed them correctly. The blind spot was that the test inputs came
from the same head as the implementation, and Python source literals are NFC by
default, so the one input that would have caught it was the one not written.

A corpus fixes the part that discipline could not: the inputs stop being
whatever the author thought of. Any future filter over names, addresses or
messages gets the accumulated cases for free.

## Using it

Register the transformer in `TEXT_TRANSFORMERS` and it inherits every property
below. That is the whole interface — one line buys normalisation-invariance and
idempotence coverage across every script in `REAL_NAMES`.

Add to the corpus whenever real input breaks something, rather than adding a
case to one caller's test file. The next filter will face the same input.
"""

from __future__ import annotations

import unicodedata

import pytest

from api.services.email_service import _safe_greeting

# Names a supporter could plausibly type, chosen to cover the ways text stops
# being "letters and spaces". Each is a case some naive implementation mangles.
REAL_NAMES = [
    pytest.param("Alex", id="ascii"),
    pytest.param("José", id="latin-precomposed"),
    pytest.param(unicodedata.normalize("NFD", "José"), id="latin-decomposed"),
    pytest.param(unicodedata.normalize("NFD", "Ólafsdóttir"), id="latin-decomposed-long"),
    pytest.param("Mary-Anne", id="hyphenated"),
    pytest.param("O'Brien", id="apostrophe"),
    pytest.param("Ngozi Adichie", id="two-part"),
    # Vowels here are combining marks (categories Mc/Mn), not letters, so a
    # letters-only filter silently rewrites the name rather than rejecting it.
    pytest.param("अनुराधा", id="devanagari"),
    pytest.param("সুমিত", id="bengali"),
    pytest.param("பிரியா", id="tamil"),
    pytest.param("मुहम्मद", id="devanagari-conjunct"),
    # Arabic harakat are marks too, and the script is right-to-left.
    pytest.param("مُحَمَّد", id="arabic-harakat"),
    pytest.param("李雷", id="han"),
    pytest.param("김민준", id="hangul"),
    pytest.param("Ελένη", id="greek"),
    pytest.param("Дмитрий", id="cyrillic"),
]

# Text that must never reach a greeting line or any other rendered position:
# the actionable payloads someone would try to smuggle through a name field.
HOSTILE_TEXT = [
    pytest.param("CALL 555-0142 NOW", id="phone-number"),
    pytest.param("https://evil.example", id="url"),
    pytest.param("evil.example", id="bare-domain"),
    pytest.param("info@evil.example", id="email-address"),
    pytest.param("12345", id="digits-only"),
    pytest.param("!!!", id="punctuation-only"),
    pytest.param("́́́", id="combining-marks-only"),
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
    pytest.param("A" * 500, id="very-long"),
]

# Every transformer that takes text from a stranger and renders it somewhere.
# Adding one here is how it inherits the properties below.
TEXT_TRANSFORMERS = [
    pytest.param(lambda value: _safe_greeting(value, "there"), id="safe_greeting"),
]


@pytest.mark.parametrize("transform", TEXT_TRANSFORMERS)
@pytest.mark.parametrize("name", REAL_NAMES)
def test_output_does_not_depend_on_unicode_normalisation(transform, name):
    """The property that would have caught the `isalpha()` bug outright.

    Composed and decomposed spellings of the same name are the same name, and a
    browser may send either — the form does not normalise, and macOS filesystems
    and some IMEs hand over NFD. A transformer whose output differs between them
    is deleting marks, which is a rewrite rather than a rejection and is
    therefore invisible to any test that only checks for a non-empty result.

    Stated as a property rather than a list of scripts, so it holds for the ones
    nobody thought to enumerate.
    """
    composed = transform(unicodedata.normalize("NFC", name))
    decomposed = transform(unicodedata.normalize("NFD", name))

    assert unicodedata.normalize("NFC", composed) == unicodedata.normalize("NFC", decomposed)


@pytest.mark.parametrize("transform", TEXT_TRANSFORMERS)
@pytest.mark.parametrize("name", REAL_NAMES)
def test_a_real_name_survives_with_its_characters_intact(transform, name):
    """No letter **or mark** is dropped from a name a supporter could have.

    Marks are half the point. An earlier draft of this property compared only
    category `L` and passed the very bug the corpus was written for: dropping
    Devanagari vowel signs leaves every letter in place, so "अनुराधा" becomes
    "अनरध" without losing a single `L`. Normalisation-invariance does not catch
    it either, because those marks have no precomposed form to normalise to.

    Weaker than equality on purpose — a transformer may legitimately truncate or
    collapse whitespace — but it fails the moment characters go missing from a
    name short enough that nothing should have been removed.
    """
    kept = frozenset("LM")

    def significant(value: str) -> list[str]:
        return [
            ch for ch in unicodedata.normalize("NFC", value) if unicodedata.category(ch)[0] in kept
        ]

    assert significant(transform(name)) == significant(name)


@pytest.mark.parametrize("transform", TEXT_TRANSFORMERS)
@pytest.mark.parametrize("value", REAL_NAMES + HOSTILE_TEXT)
def test_transforming_twice_changes_nothing(transform, value):
    """Idempotence. A sanitiser that keeps changing its own output is unfinished.

    Cheap to assert and it catches a whole family of mistakes: truncation that
    lands mid-sequence, a strip that only removes one leading character, a
    fallback that is itself rejected on the next pass.
    """
    once = transform(value)

    assert transform(once) == once


@pytest.mark.parametrize("transform", TEXT_TRANSFORMERS)
@pytest.mark.parametrize("value", HOSTILE_TEXT)
def test_output_never_begins_with_an_orphaned_mark(transform, value):
    """A combining mark with nothing to attach to renders as a stray glyph.

    The realistic route to one is truncation landing inside a sequence, so the
    hostile list carries the long input that provokes it.
    """
    output = transform(value)

    assert not output or not unicodedata.category(output[0]).startswith("M")
