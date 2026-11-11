from app.routes.metrics import FALLBACKS, ABSTENTIONS

def test_metrics_counters_exist():
    assert FALLBACKS is not None
    assert ABSTENTIONS is not None
