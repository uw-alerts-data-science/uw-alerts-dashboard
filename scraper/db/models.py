"""Pydantic contract mirroring schema.sql. Single source of truth for the
incidents/alerts columns and their allowed values — used to validate scraper
tool inputs before they reach Postgres.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class IncidentCategory(str, Enum):
    THEFT = "Theft"
    ROBBERY = "Robbery"
    ASSAULT = "Assault"
    SEXUAL_ASSAULT = "Sexual Assault"
    SHOOTING = "Shooting"
    HOMICIDE = "Homicide / Death Investigation"
    SUSPICIOUS_ACTIVITY = "Suspicious Activity"
    SUSPICIOUS_PERSON = "Suspicious Person"
    DISTURBANCE = "Disturbance"
    CIVIL_UNREST = "Civil Unrest"
    FIRE = "Fire"
    HAZARDOUS_MATERIALS = "Hazardous Materials"
    MEDICAL_EMERGENCY = "Medical Emergency"
    MISSING_PERSON = "Missing Person"
    MOTOR_VEHICLE_INCIDENT = "Motor Vehicle Incident"
    HARASSMENT = "Harassment"
    ANNOUNCEMENT = "Announcement"
    OTHER = "Other"


class AlertType(str, Enum):
    ORIGINAL = "original"
    UPDATE = "update"


class Incident(BaseModel):
    """Mirrors the `incidents` table."""

    id: int | None = None
    category: IncidentCategory | None = None
    nearest_address: str | None = None
    google_address: str | None = None
    lat: float | None = None
    lng: float | None = None
    occurred_at: datetime | None = None
    first_reported_at: datetime | None = None
    last_updated_at: datetime | None = None
    created_at: datetime | None = None

    @field_validator("category", mode="before")
    @classmethod
    def coerce_unknown_category_to_other(cls, v):
        if v is None or v == "":
            return None
        try:
            return IncidentCategory(v)
        except ValueError:
            return IncidentCategory.OTHER


class Alert(BaseModel):
    """Mirrors the `alerts` table."""

    id: int | None = None
    incident_id: int | None = None
    alert_type: AlertType
    reported_at: datetime | None = None
    incident_time: datetime | None = None
    summary: str | None = None
    full_text: str
    raw_scraped_text: str | None = None
    source_url: str | None = None
    text_hash: str | None = None
    created_at: datetime | None = None


class UpsertAlertInput(BaseModel):
    """Flat write-time shape matching the upsert_alert tool call, which
    populates both tables in a single request."""

    model_config = ConfigDict(extra="allow")

    is_new_incident: bool = True
    incident_id: int | None = None
    alert_type: AlertType
    category: IncidentCategory | None = None
    nearest_address: str | None = None
    google_address: str | None = None
    lat: float | None = None
    lng: float | None = None
    occurred_at: datetime | None = None
    reported_at: datetime | None = None
    incident_time: datetime | None = None
    summary: str | None = None
    full_text: str
    raw_scraped_text: str | None = None
    source_url: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def coerce_unknown_category_to_other(cls, v):
        if v is None or v == "":
            return None
        try:
            return IncidentCategory(v)
        except ValueError:
            return IncidentCategory.OTHER
