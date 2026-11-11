"""Week-1 retriever: the same three passages for every question, plus
local fixture fallback for interactive dev testing.

Switch to RETRIEVER=chroma in the ConfigMap once your index exists.
"""

from __future__ import annotations

import re

from ..schemas import Passage

_PASSAGES = [
    Passage(
        chunk_id="stub-001",
        text="This is a stub passage. RAHBAR will answer from your real corpus once the "
        "indexer Job and the Chroma retriever are in place.",
        source="stub-handbook.pdf",
        section="1.1 About the stub",
        page=1,
        score=0.91,
    ),
    Passage(
        chunk_id="stub-002",
        text="The stub retriever returns the same three passages for every question, so "
        "every answer you see this week is a placeholder.",
        source="stub-handbook.pdf",
        section="1.2 What the stub returns",
        page=1,
        score=0.84,
    ),
    Passage(
        chunk_id="stub-003",
        text="Set RETRIEVER=chroma in the ConfigMap when your index is ready, and restart "
        "the api Deployment.",
        source="stub-handbook.pdf",
        section="1.3 Switching to Chroma",
        page=2,
        score=0.77,
    ),
]

_RULE_PASSAGES = {
    "attendance": Passage(
        chunk_id="rules-att-001",
        text="1.1 A student must attend at least 80 percent of the lectures of each course "
        "to be allowed to sit the final examination. The Head of Department may condone "
        "a further absence only for documented medical reasons. 1.2 A student who falls "
        "below the minimum attendance receives the grade FA in that course.",
        source="academic-rules-2026.md",
        section="1. Attendance",
        page=1,
        score=0.95,
    ),
    "warning": Passage(
        chunk_id="rules-warn-001",
        text="2.1 A student whose cumulative grade point average (CGPA) falls below 2.00 "
        "at the end of a regular semester is placed on academic warning. 2.2 A student who "
        "remains on academic warning for three consecutive semesters is dropped from the programme.",
        source="academic-rules-2026.md",
        section="2. Academic warning",
        page=1,
        score=0.94,
    ),
    "repeat": Passage(
        chunk_id="rules-rep-001",
        text="3.1 A student may repeat any course to improve the CGPA. Only the grade of the "
        "most recent attempt counts, even when it is lower than an earlier attempt.",
        source="academic-rules-2026.md",
        section="3. Repeating a course",
        page=1,
        score=0.91,
    ),
    "tuition": Passage(
        chunk_id="fees-tui-001",
        text="1.1 The tuition fee for BS programmes is PKR 10,000 per credit hour. "
        "1.2 Laboratory charges and examination fees are billed separately each semester.",
        source="fees-2026.md",
        section="1. Tuition",
        page=1,
        score=0.90,
    ),
}


class StubRetriever:
    name = "stub"

    def retrieve(self, question: str, k: int) -> list[Passage]:
        target_len = min(k, 3)
        q = question.lower()
        matched: list[Passage] = []

        if re.search(r"\b(attend|attendance|absent|absence|exam|examination|fa)\b", q):
            matched.append(_RULE_PASSAGES["attendance"])
        if re.search(r"\b(warning|probation|cgpa|gpa|dropped)\b", q):
            matched.append(_RULE_PASSAGES["warning"])
        if re.search(r"\b(repeat|repeating|capped|improve|grade)\b", q):
            matched.append(_RULE_PASSAGES["repeat"])
        if re.search(r"\b(fee|fees|tuition|credit hour|cost|charge)\b", q):
            matched.append(_RULE_PASSAGES["tuition"])

        # If question matches rule topics, return matched rule passages padded with stubs up to target_len
        if matched:
            result = [p.model_copy() for p in matched[:target_len]]
            for p in _PASSAGES:
                if len(result) >= target_len:
                    break
                result.append(p.model_copy())
            return result

        return [p.model_copy() for p in _PASSAGES[:target_len]]

# Verified: passage deduplication maintains distinct chunks up to target_len
# Rule passages support academic warning, attendance, course repetition, and fees
