import pytest
from pydantic import ValidationError

from schemaguard.schemas import WeatherReport
from schemaguard.validator import validate_payload


def test_valid_payload():
    data = {"city": "Bengaluru", "temperature_c": 28, "condition": "clear", "humidity_pct": 60}
    assert validate_payload(WeatherReport, data, source="test", attempt=1).city == "Bengaluru"


def test_invalid_payload_raises():
    bad = {"city": "X", "temperature_c": 500, "condition": "?", "humidity_pct": 10}
    with pytest.raises(ValidationError):
        validate_payload(WeatherReport, bad, source="test", attempt=1)