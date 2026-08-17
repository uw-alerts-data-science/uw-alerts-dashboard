# scraper/tests/test_models.py
import pytest
from pydantic import ValidationError

from scraper.db.models import IncidentCategory, IncidentStatus, UpsertAlertInput, Weapon

BASE_INPUT = {
    "is_new_incident": True,
    "alert_type": "original",
    "full_text": "Test alert",
    "raw_scraped_text": "Test alert",
}


def test_known_category_validates():
    v = UpsertAlertInput(**{**BASE_INPUT, "category": "Shooting"})
    assert v.category == IncidentCategory.SHOOTING


def test_new_announcement_category_validates():
    v = UpsertAlertInput(**{**BASE_INPUT, "category": "Announcement"})
    assert v.category == IncidentCategory.ANNOUNCEMENT


def test_unknown_category_coerces_to_other():
    v = UpsertAlertInput(**{**BASE_INPUT, "category": "Stabbing"})
    assert v.category == IncidentCategory.OTHER


def test_blank_category_becomes_none():
    v = UpsertAlertInput(**{**BASE_INPUT, "category": ""})
    assert v.category is None


def test_missing_category_defaults_to_none():
    v = UpsertAlertInput(**BASE_INPUT)
    assert v.category is None


def test_invalid_alert_type_raises():
    with pytest.raises(ValidationError):
        UpsertAlertInput(**{**BASE_INPUT, "alert_type": "breaking_news"})


def test_missing_full_text_raises():
    inputs = {k: v for k, v in BASE_INPUT.items() if k != "full_text"}
    with pytest.raises(ValidationError):
        UpsertAlertInput(**inputs)


def test_malformed_occurred_at_raises():
    with pytest.raises(ValidationError):
        UpsertAlertInput(**{**BASE_INPUT, "occurred_at": "sometime last Tuesday"})


def test_known_status_validates():
    v = UpsertAlertInput(**{**BASE_INPUT, "status": "cleared"})
    assert v.status == IncidentStatus.CLEARED


def test_unknown_status_coerces_to_none():
    v = UpsertAlertInput(**{**BASE_INPUT, "status": "in_progress"})
    assert v.status is None


def test_blank_status_becomes_none():
    v = UpsertAlertInput(**{**BASE_INPUT, "status": ""})
    assert v.status is None


def test_missing_status_defaults_to_none():
    v = UpsertAlertInput(**BASE_INPUT)
    assert v.status is None


def test_known_weapon_validates():
    v = UpsertAlertInput(**{**BASE_INPUT, "weapon": "Handgun"})
    assert v.weapon == Weapon.HANDGUN


def test_unknown_weapon_coerces_to_none():
    v = UpsertAlertInput(**{**BASE_INPUT, "weapon": "Machete"})
    assert v.weapon is None


def test_num_suspects_and_suspect_at_large_pass_through():
    v = UpsertAlertInput(**{**BASE_INPUT, "num_suspects": 2, "suspect_at_large": True})
    assert v.num_suspects == 2
    assert v.suspect_at_large is True
