"""Format and context regressions independent of receipt identities."""

import re

import pytest

from docucheck.extraction.datetime_parser import parse as parse_datetime
from docucheck.extraction.datetime_parser import times
from docucheck.extraction.money import TOKEN, parse
from docucheck.extraction.qwen import normalize


@pytest.mark.parametrize(
    "text", ["35 000", "35\u00a0000", "35\u202f000", "35.000", "35,000", "35000"]
)
def test_equivalent_money_formats(text):
    assert re.findall(TOKEN, text) == [text]
    assert parse(text) == 35000
    assert normalize("total_amount", text)[0] == 35000


@pytest.mark.parametrize("text", ["650000 650000", "35 000\n35 000", "2 35 000"])
def test_separate_numbers_are_not_concatenated(text):
    assert len(re.findall(TOKEN, text)) == 2
    assert normalize("total_amount", text)[0] is None


@pytest.mark.parametrize(
    "text,value,precision",
    [
        ("30.09.2020 08.29", "2020-09-30T08:29", "minute"),
        ("2020-09-30 08:00", "2020-09-30T08:00", "minute"),
        ("29/02/2020 00:00:00", "2020-02-29T00:00:00", "second"),
        ("31/02/2020 08:29", None, None),
        ("30.09.2020 25.70", None, None),
    ],
)
def test_datetime_calendar_and_precision(text, value, precision):
    actual, actual_precision, _ = parse_datetime(text)
    assert (actual, actual_precision) == (value, precision)


def test_decimal_price_is_not_time_without_date_context():
    assert times("Price 12.50") == []


def test_datetime_excludes_invoice_id():
    text = "Time:30.09.2020 08.29 Invoice: 19809053062020"
    assert parse_datetime(text)[0] == "2020-09-30T08:29"


@pytest.mark.parametrize("suffix", ["d", "đ", "₫", "VND", "vnd"])
def test_attached_currency_is_not_dropped(suffix):
    assert re.findall(TOKEN, "12.000" + suffix) == ["12.000"]
    assert normalize("total_amount", "12.000" + suffix)[0] == 12000
