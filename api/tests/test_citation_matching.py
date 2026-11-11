from app.schemas import Citation, Passage
from app.services.grounding import filter_and_verify_citations

def test_citation_matching_with_subclause_number():
    passages = [
        Passage(chunk_id="p1", text="2.1 A student with CGPA < 2.00 is warned.", source="rules.md", section="2. Academic warning", page=1, score=0.9)
    ]
    citations = [
        Citation(source="rules.md", section="2.1", page=1)
    ]
    valid, invalid = filter_and_verify_citations(citations, passages)
    assert len(valid) == 1
    assert valid[0].section == "2. Academic warning"
    assert len(invalid) == 0
