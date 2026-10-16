from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.pendel.const import DOMAIN

from .conftest import PLACES, URL

LOGIN = {"url": "pendel.test/", "email": "me@example.org", "password": "pw"}
TRACKING = {
    "track_location": True,
    "person": "person.ich",
    "home_zone": "zone.home",
    "office_zone": "zone.arbeit",
}


def mock_login(aioclient_mock, status=201):
    aioclient_mock.post(f"{URL}/api/auth/token", json={"token": "new-token"}, status=status)
    aioclient_mock.get(f"{URL}/api/me", json={"id": 1, "display_name": "Yannick"})
    aioclient_mock.get(f"{URL}/api/places", json=PLACES)
    aioclient_mock.put(f"{URL}/api/places/1", json=PLACES[0])
    aioclient_mock.put(f"{URL}/api/places/2", json=PLACES[1])


async def test_full_flow(hass, aioclient_mock, zones):
    mock_login(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["step_id"] == "tracking"
    login_call = next(c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/api/auth/token"))
    assert login_call[2] == {"email": "me@example.org", "password": "pw", "name": "Home Assistant"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TRACKING, "office_zone": "zone.home"}
    )
    assert result["errors"] == {"office_zone": "same_zone"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], TRACKING)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pendel (Yannick)"
    assert result["data"] == {"url": URL, "token": "new-token", **TRACKING}
    assert "password" not in result["data"]
    puts = {str(c[1]): c[2]["zone"] for c in aioclient_mock.mock_calls if c[0] == "PUT"}
    assert puts == {f"{URL}/api/places/1": "zone.home", f"{URL}/api/places/2": "zone.arbeit"}


async def test_invalid_auth(hass, aioclient_mock):
    mock_login(aioclient_mock, status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/auth/token", exc=TimeoutError)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_tracking_disabled_needs_no_zones(hass, aioclient_mock, zones):
    mock_login(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"track_location": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not any(c[0] == "PUT" for c in aioclient_mock.mock_calls)


async def test_already_configured(hass, aioclient_mock, config_entry):
    mock_login(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
