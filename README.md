# Pendel for Home Assistant

Home Assistant integration for [Pendel](https://github.com/Schally0711/pendel), a self-hosted work time tracker for
people who split their week between home office and office.

- **Automatic tracking:** reports zone changes of a person (home / office / away) to Pendel, which records the
  commute, office time and breaks (leaving the office for up to 90 minutes = break, longer = work, e.g. a customer visit).
  Events are queued while Pendel is unreachable and sent later.
- **Sensors:** status (home office, office, break, commuting …), worked today, target, remaining, flexitime balance,
  this week, breaks, commute, remaining vacation, next time off.
- **Buttons:** start home office, start at the office, start/end break, finish work – handy for NFC tags,
  Zigbee buttons or automations.

No YAML needed: the setup dialog signs in once, creates its own API token (the password is not stored) and writes
the chosen zones to your Pendel places.

## Installation

**HACS:** add this repository as a custom repository (category *Integration*), install *Pendel*, restart Home Assistant.

**Manual:** copy `custom_components/pendel` into the `custom_components` folder of your Home Assistant configuration
and restart.

Then: *Settings → Devices & services → Add integration → Pendel*.

1. Pendel address (e.g. `https://pendel.example.com`), e-mail and password.
2. Person to track and the zones for home and office (create an office zone first under *Settings → Areas & zones*).

Zones and the person can be changed later via *Configure*. Requires Pendel ≥ 0.4.0.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

---

### Deutsch (Kurzfassung)

Installieren (HACS oder Ordner `custom_components/pendel` kopieren), HA neu starten, dann *Einstellungen → Geräte &
Dienste → Integration hinzufügen → Pendel*: Adresse, E-Mail und Passwort eingeben, Person sowie die Zonen für Zuhause
und Büro wählen – fertig. Pendel erfasst dann Arbeitsweg, Bürozeit und Pausen automatisch.
