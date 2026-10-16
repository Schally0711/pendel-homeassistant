<p align="center"><img src="https://raw.githubusercontent.com/Schally0711/pendel/main/frontend/assets/icon.svg" width="80" alt="" /></p>

<h1 align="center">Pendel für Home Assistant</h1>

<p align="center">
  <a href="https://github.com/Schally0711/pendel-homeassistant/actions/workflows/validate.yml"><img src="https://github.com/Schally0711/pendel-homeassistant/actions/workflows/validate.yml/badge.svg" alt="Validate" /></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5" alt="HACS Custom" /></a>
</p>

Integration für [Pendel](https://github.com/Schally0711/pendel), die selbst gehostete Arbeitszeiterfassung für
Homeoffice, Büro und Arbeitsweg.

**English:** Home Assistant integration for Pendel. It reports a person's zone changes (home / office / away) to Pendel,
which records commute, office time and breaks automatically, and provides sensors (status, worked today, flexitime
balance, vacation …) and buttons (start home office / office, break, finish work). See the
[English summary](#english-summary) below.

## Funktionen

- **Automatische Erfassung:** Meldet Zonenwechsel einer Person (Zuhause / Büro / unterwegs) an Pendel. Pendel macht
  daraus Arbeitsweg, Bürozeit und Pausen (Büro kurz verlassen = Pause, länger = Arbeitszeit, z. B. Kundentermin).
  Ist Pendel nicht erreichbar, werden die Meldungen gespeichert und später nachgereicht.
- **Sensoren:** Status (Homeoffice, Büro, Pause, unterwegs …), Status seit, heute gearbeitet, Soll heute, noch bis zum
  Soll, Gleitzeitkonto, diese Woche (Ist und Soll), Pausen heute, Arbeitsweg heute, Resturlaub, nächste Abwesenheit.
- **Knöpfe:** Homeoffice starten, Im Büro starten, Pause starten/beenden, Feierabend – z. B. für Dashboards,
  NFC-Tags, Zigbee-Taster oder eigene Automationen.
- Einrichtung komplett über die Oberfläche, kein YAML. Unterstützt die Zwei-Faktor-Anmeldung von Pendel.

## Voraussetzungen

- Eine laufende Pendel-Instanz ([Installation](https://github.com/Schally0711/pendel/blob/main/docs/installation.md)),
  die Home Assistant erreicht – empfohlen Pendel 0.9 oder neuer.
- Home Assistant 2025.10 oder neuer.
- Für die automatische Erfassung: eine Person mit Standort (z. B. Companion App) und eine **Zone für das Büro**
  (*Einstellungen → Bereiche, Labels & Zonen → Zonen*).

## Installation

**Über HACS (empfohlen):**

1. HACS öffnen → Menü (⋮) → *Benutzerdefinierte Repositories*.
2. `https://github.com/Schally0711/pendel-homeassistant` mit Typ **Integration** hinzufügen.
3. **Pendel** suchen, herunterladen und Home Assistant neu starten.

**Manuell:** den Ordner `custom_components/pendel` aus dem
[neuesten Release](https://github.com/Schally0711/pendel-homeassistant/releases) in den Ordner `custom_components`
deiner Home-Assistant-Konfiguration kopieren und neu starten.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → Pendel*

1. **Adresse** von Pendel (z. B. `https://pendel.example.com`), **E-Mail** und **Passwort** – bei aktiver
   Zwei-Faktor-Anmeldung zusätzlich den Code. Home Assistant erstellt sich damit einen eigenen API-Token; das
   Passwort wird nicht gespeichert. Der Token erscheint in Pendel unter *Einstellungen → Integrationen* und kann dort
   widerrufen werden.
2. **Automatische Erfassung:** Person sowie die Zonen für Zuhause und Büro wählen. Die Integration trägt die Zonen in
   die Orte in Pendel ein. Ohne automatische Erfassung gibt es nur Sensoren und Knöpfe.

Person und Zonen lassen sich später über *Konfigurieren* ändern. Lehnt Pendel den Token ab (z. B. nach dem
Widerrufen), fordert Home Assistant zur erneuten Anmeldung auf.

## Entitäten

Alle Entitäten hängen an einem Gerät „Pendel (&lt;Name&gt;)“; die Werte werden jede Minute aktualisiert.

| Entität | Beschreibung |
|---|---|
| Status | `idle`, `working_home`, `working_office`, `working_other`, `break`, `commute_to_work`, `commute_from_work` |
| Status seit | Zeitpunkt des letzten Statuswechsels |
| Heute gearbeitet, Soll heute, Noch bis zum Soll | Dauer |
| Gleitzeitkonto | Kontostand inklusive heute |
| Diese Woche gearbeitet, Soll diese Woche | Dauer |
| Pausen heute, Arbeitsweg heute | Dauer |
| Resturlaub | Tage; Attribute `year`, `entitlement`, `carried_over`, `taken`, `planned` |
| Nächste Abwesenheit | Datum; Attribute `end`, `kind`, `note`, `workdays` |
| Knöpfe | Homeoffice starten, Im Büro starten, Pause starten, Pause beenden, Feierabend |

## Aktion: Arbeitsgerät aktiv (intelligenter Start)

`pendel.device_active` meldet, dass dein Arbeitsgerät benutzt wird. Pendel startet dann die Arbeitszeit (Standard:
Zuhause, optional `place: Büro`) – aber nur an einem Arbeitstag ohne Abwesenheit, wenn nichts läuft und heute noch
nicht gearbeitet wurde. Die Aktion darf also oft ausgelöst werden. Beispiel: Arbeitsnotebook kommt ins Heimnetz.

```yaml
automation:
  - alias: Arbeitsnotebook im Heimnetz → Homeoffice
    triggers:
      - trigger: state
        entity_id: device_tracker.arbeitsnotebook
        to: home
    actions:
      - action: pendel.device_active
```

Die Antwort (`response_variable`) enthält `started` (true/false) und die Aktionen von Pendel. Erfordert Pendel ≥ 0.9.2.

## Beispiel-Automation

Hinweis, wenn um 20 Uhr noch eingestempelt ist (Entitäts-ID an deinen Namen anpassen).

```yaml
automation:
  - alias: Feierabend vergessen?
    triggers:
      - trigger: time
        at: "20:00:00"
    conditions:
      - condition: not
        conditions:
          - condition: state
            entity_id: sensor.pendel_alex_status
            state: idle
    actions:
      - action: notify.notify
        data:
          message: Du bist noch eingestempelt.
```

## Fehlersuche

- **„Pendel ist unter dieser Adresse nicht erreichbar“:** Adresse aus Sicht von Home Assistant prüfen. Steht
  Cloudflare Access vor Pendel, braucht es eine Bypass-Regel für `/api/*`.
- **Es wird nichts automatisch erfasst:** Stimmen Person und Zonen (*Konfigurieren*)? In Pendel zeigt der
  Tageseditor unter *Automatik-Protokoll*, welche Meldungen angekommen sind und was daraus wurde.
- **Diagnose:** *Einstellungen → Geräte & Dienste → Pendel → ⋮ → Diagnose herunterladen* – Token und Adresse sind darin
  unkenntlich gemacht; die Datei gerne an Fehlerberichte anhängen.
- Logs: *Einstellungen → System → Protokolle*, Filter „pendel“.

Fehler und Ideen bitte als [Issue](https://github.com/Schally0711/pendel-homeassistant/issues) melden.

## English summary

- **Install:** HACS → *Custom repositories* → add `https://github.com/Schally0711/pendel-homeassistant` (type
  *Integration*) → download *Pendel* → restart. Or copy `custom_components/pendel` manually.
- **Set up:** *Settings → Devices & services → Add integration → Pendel*: Pendel address, e-mail, password (and the
  2FA code if enabled; the password is not stored, HA creates its own API token), then the person and the home/office zones.
- **Entities:** status, status since, worked today, target today, remaining today, flexitime balance, worked/target this
  week, breaks today, commute today, vacation remaining, next time off; buttons to start home office / office,
  start/end break, finish work. Updated every minute.
- Zone changes are queued while Pendel is unreachable and sent later. Requires Home Assistant ≥ 2025.10; Pendel ≥ 0.9 recommended.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format .
```

Lizenz: [AGPL-3.0](LICENSE)
