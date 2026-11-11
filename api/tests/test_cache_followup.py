from app.services.cache import is_followup


def test_followup_detection():
    assert is_followup("And what about fees?")
    assert is_followup("Also, what about repeating a course?")
    assert not is_followup("What is the minimum attendance required for final exams?")
