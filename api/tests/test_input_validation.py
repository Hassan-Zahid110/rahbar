import pytest
from app.schemas import AskRequest

def test_valid_input_string():
    req = AskRequest(question="Valid question about syllabus?")
    assert req.question == "Valid question about syllabus?"

def test_invalid_short_input():
    with pytest.raises(Exception):
        AskRequest(question="hi")
