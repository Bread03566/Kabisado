"""Grounded retrieval for offline chat: rank short passages of the student's own material.

No embeddings and no external service. Passages are scored with BM25 (rare words count more than common
ones) after light stemming, and a question is only answered when enough of its terms are actually found;
otherwise the caller says "not in your material" instead of guessing.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "by", "for", "with", "from", "as",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that", "these", "those", "there",
    "here", "he", "she", "they", "we", "you", "i", "his", "her", "their", "our", "your", "my", "him", "them",
    "us", "which", "who", "whom", "what", "when", "where", "why", "how", "also", "not", "no", "so", "such",
    "can", "could", "may", "might", "will", "would", "should", "must", "has", "have", "had", "do", "does",
    "did", "into", "than", "then", "each", "other", "some", "any", "all", "most", "more", "many", "much",
    "very", "only", "both", "even", "about", "between", "after", "before", "during", "under", "over",
    "through", "one", "two",
    # words that make a question a question but say nothing about its subject
    "tell", "explain", "describe", "mean", "define", "give", "show", "please", "found", "called", "name",
    "know", "say", "work",
    # common Filipino function words, so Tagalog questions are not matched on filler
    "ano", "ang", "mga", "bakit", "paano", "sino", "saan", "kailan", "ng", "sa", "na",
}

WINDOW = 2            # sentences per passage
MIN_COVERAGE = 0.5    # share of the question's terms that must appear in a passage
HISTORY_TURNS = 2     # earlier questions consulted for a short follow-up


def stem(word: str) -> str:
    w = word.lower()
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("es"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def tokens(text: str) -> List[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


@dataclass
class Chunk:
    topic_id: Optional[int]
    topic_title: str
    ordinal: int
    text: str
    terms: Counter = field(default_factory=Counter)

    @property
    def citation(self) -> str:
        return f"{self.topic_title} (part {self.ordinal})"


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text.strip())
    return [p.strip() for p in parts if p and len(p.strip()) > 1]


def build_chunks(topics: List[Dict[str, Any]]) -> List[Chunk]:
    chunks: List[Chunk] = []
    for topic in topics:
        sentences = _sentences(topic.get("content", ""))
        for ordinal, start in enumerate(range(0, len(sentences), WINDOW), start=1):
            text = " ".join(sentences[start:start + WINDOW])
            if len(text) < 30:
                continue
            chunks.append(Chunk(topic.get("id"), topic.get("title", "Lesson"), ordinal, text, Counter(tokens(text))))
    return chunks


def _query_terms(question: str, history: Optional[List[Dict[str, str]]]) -> List[str]:
    terms = tokens(question)
    if len(terms) <= 1 and history:  # "Where is it found?" only makes sense next to the question before it
        earlier = [m.get("content", "") for m in history if m.get("role") == "user"][-HISTORY_TURNS:]
        for text in reversed(earlier):
            carried = tokens(text)
            if carried:
                return list(dict.fromkeys(terms + carried))
    return list(dict.fromkeys(terms))


def rank(chunks: List[Chunk], question: str, history: Optional[List[Dict[str, str]]] = None,
         k: int = 3) -> List[Tuple[float, Chunk]]:
    """The best passages for the question (best first), or an empty list when the material cannot answer it."""
    terms = _query_terms(question, history)
    if not terms or not chunks:
        return []
    n = len(chunks)
    df = {t: sum(1 for c in chunks if t in c.terms) for t in terms}
    average = sum(sum(c.terms.values()) for c in chunks) / n or 1.0
    k1, b = 1.5, 0.75
    scored: List[Tuple[float, Chunk]] = []
    for chunk in chunks:
        present = [t for t in terms if chunk.terms[t] > 0]
        if len(present) / len(terms) < MIN_COVERAGE:
            continue
        length = sum(chunk.terms.values()) or 1
        score = 0.0
        for t in present:
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            tf = chunk.terms[t]
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * length / average))
        scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]
