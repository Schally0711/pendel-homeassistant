from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import URL, mock_pendel, today


async def setup(hass, config_entry):
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def event_calls(aioclient_mock):
    return [c[2] for c in aioclient_mock.mock_calls if c[0] == "POST" and str(c[1]).endswith("/api/events")]


async def test_sensors(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    status = hass.states.get("sensor.pendel_alex_status")
    assert status.state == "working_office"
    assert hass.states.get("sensor.pendel_alex_status_since").state == "2026-10-14T06:00:00+00:00"
    worked = hass.states.get("sensor.pendel_alex_worked_today")
    assert round(float(worked.state), 2) == 3.33 and worked.attributes["unit_of_measurement"] == "h"
    assert round(float(hass.states.get("sensor.pendel_alex_flexitime_balance").state), 2) == 1.58
    vac = hass.states.get("sensor.pendel_alex_vacation_remaining")
    assert float(vac.state) == 5 and vac.attributes["planned"] == 8
    nxt = hass.states.get("sensor.pendel_alex_next_time_off")
    assert nxt.state == "2026-12-21" and nxt.attributes["note"] == "Weihnachten"


async def test_auth_failure_starts_reauth(hass, aioclient_mock, config_entry, zones):
    aioclient_mock.get(f"{URL}/api/today", status=401)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_zone_changes_are_reported(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)

    hass.states.async_set("person.ich", "not_home")
    await hass.async_block_till_done()
    hass.states.async_set("person.ich", "Supermarkt")  # unconfigured zone counts as away → nothing sent
    await hass.async_block_till_done()
    hass.states.async_set("person.ich", "Arbeit")
    await hass.async_block_till_done()
    hass.states.async_set("person.ich", "unavailable")
    await hass.async_block_till_done()

    calls = event_calls(aioclient_mock)
    assert [(c["from"], c["to"]) for c in calls] == [("zone.home", "not_home"), ("not_home", "zone.arbeit")]
    assert all(c["type"] == "zone_change" and c["source"] == "home_assistant" and c["at"] for c in calls)


async def test_events_are_queued_while_offline(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{URL}/api/events", exc=TimeoutError)

    hass.states.async_set("person.ich", "not_home")
    await hass.async_block_till_done()
    hass.states.async_set("person.ich", "Arbeit")
    await hass.async_block_till_done()
    assert config_entry.runtime_data.tracker.pending == 2

    aioclient_mock.clear_requests()
    mock_pendel(aioclient_mock)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()
    assert config_entry.runtime_data.tracker.pending == 0
    assert [(c["from"], c["to"]) for c in event_calls(aioclient_mock)] == [
        ("zone.home", "not_home"),
        ("not_home", "zone.arbeit"),
    ]


async def test_queue_survives_restart(hass, aioclient_mock, config_entry, zones, hass_storage):
    hass_storage[f"pendel.{config_entry.entry_id}.queue"] = {
        "version": 1,
        "data": [{"from": "zone.home", "to": "not_home", "at": dt_util.utcnow().isoformat()}],
    }
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    assert [(c["from"], c["to"]) for c in event_calls(aioclient_mock)] == [("zone.home", "not_home")]


async def test_tracking_disabled(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    hass.config_entries.async_update_entry(config_entry, options={"track_location": False})
    await setup(hass, config_entry)
    hass.states.async_set("person.ich", "not_home")
    await hass.async_block_till_done()
    assert event_calls(aioclient_mock) == []
    assert config_entry.runtime_data.tracker is None


async def test_buttons(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock, today(running_session=None))
    await setup(hass, config_entry)
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pendel_alex_start_home_office"}, blocking=True
    )
    start = next(c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/api/clock/start"))
    assert start[2] == {"kind": "home", "place_id": 1}
    assert start[3]["Authorization"] == "Bearer secret-token"


async def test_button_conflict_raises(hass, aioclient_mock, config_entry, zones):
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    mock_pendel(aioclient_mock)
    aioclient_mock.post(f"{URL}/api/clock/break/stop", json={"detail": "no_break_running"}, status=409)
    await setup(hass, config_entry)
    with pytest.raises(HomeAssistantError, match="no_break_running"):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.pendel_alex_end_break"}, blocking=True
        )


async def test_options_flow(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "track_location": True,
            "person": "person.ich",
            "home_zone": "zone.home",
            "office_zone": "zone.supermarkt",
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert config_entry.runtime_data.tracker.zones == {"zone.home", "zone.supermarkt"}


async def test_diagnostics_redact_secrets(hass, aioclient_mock, config_entry, zones):
    from custom_components.pendel.diagnostics import async_get_config_entry_diagnostics

    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"]["token"] == "**REDACTED**"
    assert diag["entry"]["data"]["url"] == "**REDACTED**"
    assert "secret-token" not in str(diag) and URL not in str(diag)
    assert diag["status"] == "working_office"
    assert diag["tracker"] == {"person": "person.ich", "queued_events": 0}


async def test_device_active_action(hass, aioclient_mock, config_entry, zones):
    mock_pendel(aioclient_mock)
    await setup(hass, config_entry)
    aioclient_mock.clear_requests()  # first matching mock wins: register the events answer first
    aioclient_mock.post(
        f"{URL}/api/events", json={"events": [{"payload": {"actions": ["device_session_started"]}}]}
    )
    mock_pendel(aioclient_mock)
    result = await hass.services.async_call(
        "pendel", "device_active", {"place": "Zuhause"}, blocking=True, return_response=True
    )
    assert result == {"actions": ["device_session_started"], "started": True}
    body = event_calls(aioclient_mock)[-1]
    assert body == {"type": "device_active", "source": "home_assistant", "zone": "Zuhause"}
