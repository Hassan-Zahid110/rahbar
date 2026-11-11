from app.retrieval.stub import StubRetriever

def test_stub_keyword_routing_attendance():
    retriever = StubRetriever()
    passages = retriever.retrieve("What is the attendance requirement?", k=3)
    assert len(passages) == 3
    assert passages[0].source == "academic-rules-2026.md"
    assert "attendance" in passages[0].section.lower()

def test_stub_keyword_routing_warning():
    retriever = StubRetriever()
    passages = retriever.retrieve("When does academic warning apply?", k=3)
    assert len(passages) == 3
    assert passages[0].source == "academic-rules-2026.md"
    assert "warning" in passages[0].section.lower()
