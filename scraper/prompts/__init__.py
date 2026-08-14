"""Jinja-templated agent system prompts, kept in one place.

Usage:
    from scraper.prompts import render_prompt
    SYSTEM_PROMPT = render_prompt("system_prompt.j2")
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scraper.db.models import IncidentCategory, IncidentStatus, Weapon

_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

# Available to every template without needing to pass it explicitly.
_ENV.globals["category_list"] = ", ".join(c.value for c in IncidentCategory)
_ENV.globals["status_list"] = ", ".join(s.value for s in IncidentStatus)
_ENV.globals["weapon_list"] = ", ".join(w.value for w in Weapon)


def render_prompt(template_name: str, **context) -> str:
    """Render a prompt template from this directory."""
    return _ENV.get_template(template_name).render(**context)
