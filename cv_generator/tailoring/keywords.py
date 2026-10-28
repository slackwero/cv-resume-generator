"""Matches a job posting against the content of a CV.

It uses no language model and no external service: it extracts the posting's terms
by frequency and shape, and checks which of them appear in the CV.

The difficulty is not finding words but discarding the filler. A job ad is full of
"we are looking for", "experience" and "team", which say nothing about the job;
those lists live in i18n/<language>.json together with everything else that
depends on the language.
"""

import re
from collections import Counter

from pydantic import BaseModel, Field

from cv_generator.models.cv import CVContent
from cv_generator.rendering.i18n import available_languages, load_language
from cv_generator.text import normalize

# A term can carry inner symbols: CI/CD, Node.js, .NET, C#
TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9]*(?:[./+#-][A-Za-zÀ-ÿ0-9]+)*")

# Two different breaks, which used to be mixed up into one:
#  - a bigram must not cross any pause, not even a comma.
PAUSE_PATTERN = re.compile(r"[.,;:!?()\n]+")
#  - a sentence does not end at a comma. Treating it as the end of a sentence made each
#    tool in "SonarQube, Trivy, Checkov" look capitalized by grammar, and they were
#    discarded as filler.
SENTENCE_PATTERN = re.compile(r"[.;:!?()\n]+")

MIN_LENGTH = 2
DEFAULT_MAXIMUM = 40

TECH_SYMBOLS = "./+#-"
# A common word that repeats is a signal too: the posting insists on it.
REPEATS_THAT_KEEP = 2


class Term(BaseModel):
    """A relevant term from the posting, with the number of times it appears in it."""

    term: str
    frequency: int


class CoverageAnalysis(BaseModel):
    """What the posting asks for, and which of it appears in the CV."""

    covered_terms: list[Term] = Field(default_factory=list)
    missing: list[Term] = Field(default_factory=list)
    covered_percent: int = 0


def _stopwords() -> set[str]:
    """Filler to discard, gathered from all the installed languages.

    They are merged instead of detecting the posting's language because a technical ad
    often mixes both, and discarding too much here is cheap.
    """
    return {normalize(word) for language in available_languages() for word in load_language(language).stopwords}


def _is_candidate(token: str, discardable: set[str]) -> bool:
    return len(token) >= MIN_LENGTH and normalize(token) not in discardable


def _occurrences(text: str) -> list[tuple[str, bool]]:
    """Every occurrence of every word, with whether it opens its sentence.

    Telling them apart matters: "Tools" at the start of a bullet is capitalized by
    grammar, while "Datadog" in the middle of a sentence is capitalized because it is a
    proper name. Without that distinction, the analysis fills up with filler.
    """
    appearances: list[tuple[str, bool]] = []

    for fragment in SENTENCE_PATTERN.split(text):
        for index, token in enumerate(TOKEN_PATTERN.findall(fragment)):
            appearances.append((token, index == 0))

    return appearances


def _looks_relevant(token: str, times: int, always_opens_sentence: bool) -> bool:
    """Decides whether a word says something about the job or is filler from the ad.

    No rule is enough alone, but together they separate "Kubernetes" from "platform" well.
    """
    if any(symbol in token for symbol in TECH_SYMBOLS):
        return True  # CI/CD, Node.js
    if token.isupper():
        return True  # AWS, SAST, CKA
    if token[1:] != token[1:].lower():
        return True  # SonarQube, GitLab, JavaScript
    if token[0].isupper() and not always_opens_sentence:
        return True  # Kubernetes, Datadog, Rust
    return times >= REPEATS_THAT_KEEP


def _only_open_sentences(text: str) -> set[str]:
    """Words that, across the whole posting, only appear at the start of a sentence.

    Their capital letter is explained by their position, not by being a proper name:
    "Pipelines" at the start of a bullet is the common word, not a technology.
    """
    positions: dict[str, list[bool]] = {}
    for token, opens in _occurrences(text):
        positions.setdefault(token, []).append(opens)
    return {token for token, open_count in positions.items() if all(open_count)}


def _count_unigrams(text: str, discardable: set[str]) -> Counter[str]:
    """Counts the words that say something about the job."""
    appearances = [(token, opens) for token, opens in _occurrences(text) if _is_candidate(token, discardable)]
    times = Counter(token for token, _ in appearances)
    only_at_start = {token: all(opens for other_one, opens in appearances if other_one == token) for token in times}

    return Counter(
        {token: count for token, count in times.items() if _looks_relevant(token, count, only_at_start[token])}
    )


def _count_bigrams(text: str, discardable: set[str]) -> Counter[str]:
    """Counts pairs of adjacent capitalized words: "Cloud Run", "Power BI".

    The first word has to be capitalized because of what it is, not because it opens the
    sentence. Without that check, "Pipelines CI/CD" slipped in as a compound term: it
    never appears that way in a CV, so it stayed forever among the missing terms
    dragging the percentage down, and it also took out the standalone "CI/CD", which is
    a real term that can be covered.
    """
    bigrams: Counter[str] = Counter()
    grammatical = _only_open_sentences(text)

    for fragment in PAUSE_PATTERN.split(text):
        tokens = TOKEN_PATTERN.findall(fragment)
        for first, second_one in zip(tokens, tokens[1:], strict=False):
            capitalized = first[0].isupper() and second_one[0].isupper()
            if (
                capitalized
                and first not in grammatical
                and _is_candidate(first, discardable)
                and _is_candidate(second_one, discardable)
            ):
                bigrams[f"{first} {second_one}"] += 1

    return bigrams


def extract_terms(text: str, maximum: int = DEFAULT_MAXIMUM) -> list[Term]:
    """Returns the most relevant terms of a posting, from the most repeated to the least.

    When two adjacent words form a compound term, the compound is preferred: "Cloud
    Run" is what matters, not "Cloud" and "Run" separately.
    """
    if not text.strip():
        return []

    discardable = _stopwords()
    bigrams = _count_bigrams(text, discardable)
    unigrams = _count_unigrams(text, discardable)

    bigram_parts = {normalize(word) for bigram in bigrams for word in bigram.split()}
    loose = Counter({token: times for token, times in unigrams.items() if normalize(token) not in bigram_parts})

    combined = (bigrams + loose).most_common(maximum)
    return [Term(term=term, frequency=times) for term, times in combined]


def _cv_text(content: CVContent) -> str:
    """All the CV text where a posting term can appear."""
    parts: list[str] = [content.personal.profession, content.profile or ""]

    for experience in content.experiences:
        parts += [experience.role, experience.company, experience.location or ""]
        parts += [achievement.text for achievement in experience.achievements]

    parts += [skill.name for skill in content.skills]
    parts += [language.language for language in content.languages]
    parts += [course.name for course in content.courses]
    parts += [f"{e.title} {e.institution}" for e in content.education]

    return normalize(" ".join(part for part in parts if part))


def _appears(cv_text: str, word: str) -> bool:
    """Looks for a whole word.

    The boundaries are checked by hand instead of with \\b because a term can contain
    symbols (CI/CD). Without this, "Java" would count as covered because the CV
    mentions "JavaScript".
    """
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(normalize(word))}(?![a-z0-9])")
    return bool(pattern.search(cv_text))


def _mentions(cv_text: str, term: str) -> bool:
    """Whether the CV demonstrates this term, as a phrase or split up.

    A compound also counts as covered when its words appear separately. The posting asks
    for "DevSecOps Engineer" and the CV says "Platform Engineer - DevSecOps": it
    demonstrates it just the same, and requiring the literal phrase left the term among
    the missing ones forever, dragging the percentage down with nothing the user could do.
    """
    if _appears(cv_text, term):
        return True

    words = term.split()
    return len(words) > 1 and all(_appears(cv_text, word) for word in words)


def mentioned_terms(text: str, terms: list[str]) -> list[str]:
    """Of a list of terms, the ones that appear in this text.

    It uses the same matching as the coverage, so the interface cannot say that an
    achievement contributes a term that the analysis later does not count as covered.
    """
    normalized = normalize(text)
    return [term for term in terms if _mentions(normalized, term)]


def analyze_coverage(posting: str, content: CVContent, maximum: int = DEFAULT_MAXIMUM) -> CoverageAnalysis:
    """Compares what the posting asks for with what the CV says."""
    terms = extract_terms(posting, maximum)
    if not terms:
        return CoverageAnalysis()

    cv_text = _cv_text(content)
    covered_terms = [t for t in terms if _mentions(cv_text, t.term)]
    missing = [t for t in terms if not _mentions(cv_text, t.term)]

    return CoverageAnalysis(
        covered_terms=covered_terms,
        missing=missing,
        covered_percent=round(100 * len(covered_terms) / len(terms)),
    )
