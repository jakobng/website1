"""Tests for country standardization module."""
import pytest
from app.countries import resolve, display_name, all_countries, resolve_or_keep


def test_resolve_by_name():
    assert resolve("France") == "FR"
    assert resolve("United Kingdom") == "GB"
    assert resolve("Germany") == "DE"


def test_resolve_by_alias():
    assert resolve("UK") == "GB"
    assert resolve("Holland") == "NL"
    assert resolve("Korea") == "KR"
    assert resolve("Czechia") == "CZ"


def test_resolve_by_code():
    assert resolve("FR") == "FR"
    assert resolve("gb") == "GB"


def test_resolve_case_insensitive():
    assert resolve("france") == "FR"
    assert resolve("FRANCE") == "FR"
    assert resolve("uk") == "GB"


def test_resolve_with_whitespace():
    assert resolve("  France  ") == "FR"
    assert resolve(" UK ") == "GB"


def test_resolve_unknown():
    assert resolve("Narnia") is None
    assert resolve("") is None


def test_resolve_or_keep():
    assert resolve_or_keep("France") == "FR"
    assert resolve_or_keep("Narnia") == "Narnia"
    assert resolve_or_keep("  UK  ") == "GB"


def test_display_name():
    assert display_name("FR") == "France"
    assert display_name("GB") == "United Kingdom"
    assert display_name("XX") == "XX"  # unknown code returns itself


def test_all_countries():
    result = all_countries()
    assert len(result) > 40
    assert all("code" in c and "name" in c for c in result)
    codes = [c["code"] for c in result]
    assert "FR" in codes
    assert "GB" in codes
