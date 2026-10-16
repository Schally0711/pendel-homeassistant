from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pendel.const import (
    CONF_HOME_ZONE,
    CONF_OFFICE_ZONE,
    CONF_PERSON,
    CONF_TRACK_LOCATION,
    DOMAIN,
)

URL = "https://pendel.test"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


def today(**overrides: Any) -> dict:
    day = {
        "day": "2026-10-14",
        "target": 480,
        "actual": 200.4,
        "diff": -280,
        "gross": 230,
        "breaks_recorded": 30,
        "breaks_effective": 30,
        "commute": 40,
        "commute_credit": 0,
        "warnings": [],
        "holiday": None,
        "entry": None,
        "kinds": ["office"],
    }
    data = {
        "now": "2026-10-14T10:00:00Z",
        "day": day,
        "running_session": {
            "id": 1,
            "kind": "office",
            "place_id": 2,
            "start": "2026-10-14T06:00:00Z",
            "end": None,
            "source": "automatic",
            "note": "",
            "breaks": [],
        },
        "running_break": None,
        "running_commute": None,
        "balance": 95,
        "balance_before_today": 375,
        "week_actual": 1400,
        "week_target": 1440,
    }
    data.update(overrides)
    return data


VACATION = {
    "year": 2026,
    "configured": True,
    "days": 30,
    "carried_over": 2,
    "total": 32,
    "taken": 19,
    "planned": 8,
    "remaining": 5,
    "suggested_carry_over": 0,
}
ABSENCES = {
    "account": VACATION,
    "periods": [
        {
            "start": "2026-07-20",
            "end": "2026-07-31",
            "kind": "vacation",
            "note": "Sommer",
            "workdays": 10,
            "vacation_days": 10,
        },
        {
            "start": "2026-12-21",
            "end": "2026-12-31",
            "kind": "vacation",
            "note": "Weihnachten",
            "workdays": 8,
            "vacation_days": 8,
        },
    ],
}
PLACES = [
    {"id": 1, "name": "Zuhause", "kind": "home", "distance_km": None, "zone": None, "archived": False},
    {"id": 2, "name": "Büro", "kind": "office", "distance_km": 28.0, "zone": None, "archived": False},
]


def mock_pendel(aioclient_mock: AiohttpClientMocker, today_data: dict | None = None) -> None:
    aioclient_mock.get(f"{URL}/api/today", json=today_data or today())
    aioclient_mock.get(f"{URL}/api/vacation/2026", json=VACATION)
    aioclient_mock.get(f"{URL}/api/absences?year=2026", json=ABSENCES)
    aioclient_mock.get(f"{URL}/api/places", json=PLACES)
    aioclient_mock.put(f"{URL}/api/places/1", json=PLACES[0])
    aioclient_mock.put(f"{URL}/api/places/2", json=PLACES[1])
    aioclient_mock.post(f"{URL}/api/events", json={"events": [{"id": 1}]})
    aioclient_mock.post(f"{URL}/api/clock/start", json={}, status=201)
    aioclient_mock.post(f"{URL}/api/clock/stop", json={})


@pytest.fixture
def entry_data() -> dict:
    return {
        "url": URL,
        "token": "secret-token",
        CONF_TRACK_LOCATION: True,
        CONF_PERSON: "person.ich",
        CONF_HOME_ZONE: "zone.home",
        CONF_OFFICE_ZONE: "zone.arbeit",
    }


@pytest.fixture
def config_entry(hass, entry_data) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Pendel (Yannick)", data=entry_data, unique_id=f"{URL}#1")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def zones(hass):
    hass.states.async_set("zone.home", "0", {"friendly_name": "Home"})
    hass.states.async_set("zone.arbeit", "0", {"friendly_name": "Arbeit"})
    hass.states.async_set("zone.supermarkt", "0", {"friendly_name": "Supermarkt"})
    hass.states.async_set("person.ich", "home")
