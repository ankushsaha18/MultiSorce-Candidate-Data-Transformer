from __future__ import annotations

from candidate_transformer.normalization import (
    is_valid_alpha2_country,
    is_valid_year_month,
    normalize_country_to_alpha2,
    normalize_date_range,
    normalize_date_to_year_month,
    normalize_phone_to_e164,
    normalize_phones_to_e164,
    normalize_skill_name,
    normalize_skill_names,
    split_and_normalize_skills,
)


def test_normalize_phone_to_e164_with_default_region():
    assert normalize_phone_to_e164("(415) 555-2671", default_region="US") == "+14155552671"
    assert normalize_phone_to_e164("+44 20 7946 0958", default_region="US") == "+442079460958"


def test_normalize_phone_to_e164_rejects_invalid_values():
    assert normalize_phone_to_e164("") is None
    assert normalize_phone_to_e164("not a phone") is None
    assert normalize_phone_to_e164("123", default_region="US") is None


def test_normalize_phones_to_e164_deduplicates_in_order():
    assert normalize_phones_to_e164(
        ["415-555-2671", "+1 415 555 2671", "bad"],
        default_region="US",
    ) == ["+14155552671"]


def test_normalize_date_to_year_month_accepts_common_formats():
    assert normalize_date_to_year_month("2024-06") == "2024-06"
    assert normalize_date_to_year_month("Jun 2024") == "2024-06"
    assert normalize_date_to_year_month("June 2024") == "2024-06"
    assert normalize_date_to_year_month("6/2024") == "2024-06"
    assert normalize_date_to_year_month("2024/6") == "2024-06"
    assert normalize_date_to_year_month("2024") == "2024-01"


def test_normalize_date_to_year_month_rejects_invalid_values():
    assert normalize_date_to_year_month("") is None
    assert normalize_date_to_year_month("2024-13") is None
    assert normalize_date_to_year_month("present") is None
    assert not is_valid_year_month("2024-13")
    assert is_valid_year_month("2024-12")


def test_normalize_date_range():
    assert normalize_date_range("Jan 2020 - Mar 2022") == ("2020-01", "2022-03")
    assert normalize_date_range("2020 - Present") == ("2020-01", None)
    assert normalize_date_range("Mar 2022") == ("2022-03", None)


def test_normalize_skill_name_uses_aliases_and_display_case():
    assert normalize_skill_name("js") == "JavaScript"
    assert normalize_skill_name("nodejs") == "Node.js"
    assert normalize_skill_name("amazon web services") == "AWS"
    assert normalize_skill_name("REST API") == "Rest API"


def test_normalize_skill_names_deduplicates_in_order():
    assert normalize_skill_names(["py", "Python", "SQL", "sql"]) == ["Python", "SQL"]


def test_split_and_normalize_skills():
    assert split_and_normalize_skills("py, js | distributed systems") == [
        "Python",
        "JavaScript",
        "Distributed Systems",
    ]


def test_normalize_country_to_alpha2():
    assert normalize_country_to_alpha2("us") == "US"
    assert normalize_country_to_alpha2("United States") == "US"
    assert normalize_country_to_alpha2("India") == "IN"
    assert normalize_country_to_alpha2("United Kingdom") == "GB"
    assert normalize_country_to_alpha2("not-a-country") is None
    assert is_valid_alpha2_country("GB")
    assert not is_valid_alpha2_country("ZZ")
