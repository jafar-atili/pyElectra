"""Tests for the Electra API helpers."""

import re

from electrasmart.api.utils import generate_imei


def test_generate_imei_uses_the_expected_prefix_and_range() -> None:
    for _ in range(50):
        imei = generate_imei()

        assert re.fullmatch(r"2b950000\d{8}", imei)
        assert 10**7 <= int(imei.removeprefix("2b950000")) <= 10**8 - 1


def test_generate_imei_asks_for_an_eight_digit_number(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    def _randint(low: int, high: int) -> int:
        calls.append((low, high))
        return 12345678

    monkeypatch.setattr("electrasmart.api.utils.randint", _randint)

    assert generate_imei() == "2b95000012345678"
    assert calls == [(10**7, 10**8 - 1)]
