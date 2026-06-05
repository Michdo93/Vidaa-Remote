# Vidaa Remote

Web-basierte Fernbedienung für Hisense / VIDAA Smart TVs.
Läuft lokal als Flask-App – keine Cloud, keine externen Dienste.

---

## Voraussetzungen

- **Python 3.10+** (getestet mit 3.14)
- TV und Rechner im **selben Netzwerk**
- TV ist eingeschaltet und hat eine feste IP (am besten im Router reservieren)

---

## Installation

```bash
# 1. Repository klonen
git clone https://github.com/Michdo93/Vidaa-Remote
cd Vidaa-Remote
sudo mv Vidaa-Remote /opt
sudo chown -R $USER:$USER /opt/Vidaa-Remote

# 2. Python installieren, falls noch nicht vorhanden
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# 3. Venv erstellen
cd /opt/Vidaa-Remote
python3 -m venv .

# 4. Abhängigkeiten installieren
source bin/activate
pip install -r requirements.txt
```

---

## Einrichtung

---

### Schritt 1 – config.py anpassen

Öffne `config.py` und trage deine TV-Daten ein:

```python
TV_IP = '192.168.0.48'        # IP-Adresse deines TVs
TV_PORT = 36669               # Nicht ändern
MAC   = 'AA:11:BB:22:CC:33'   # MAC-Adresse des TVs
```

Die **MAC-Adresse** findest du:
- Im Router (DHCP-Tabelle)
- Am TV unter: Einstellungen → Netzwerk → Netzwerkinformationen

Die Felder `ACCESS_TOKEN` und `REFRESH_TOKEN` bleiben vorerst leer – die werden durch das Pairing automatisch befüllt.

---

### Schritt 2 – Einmaliges Pairing

```bash
python pair.py
```

- Der TV zeigt kurz einen **4-stelligen PIN** auf dem Bildschirm an
- PIN in der Konsole eingeben und Enter drücken
- Die Tokens werden automatisch in `config.py` gespeichert

Das Pairing muss nur **einmalig** durchgeführt werden.

---

### Schritt 3 – App starten

```bash
python app.py
```

Browser öffnen: **http://localhost:5000**

---

### Schritt 4 – Als systemd-Dienst einrichten

```bash
# Service-Datei installieren
sudo cp /opt/Vidaa-Remote/vidaa-remote.service /etc/systemd/system/

# Dienst aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable vidaa-remote
sudo systemctl start vidaa-remote

# Status prüfen
sudo systemctl status vidaa-remote
```

Nützliche Befehle:

```bash
sudo systemctl stop vidaa-remote      # Stoppen
sudo systemctl restart vidaa-remote   # Neu starten
journalctl -u vidaa-remote -f         # Logs live verfolgen
```

---

## Token-Verwaltung

| Token | Gültigkeit | Aktion bei Ablauf |
|---|---|---|
| Access Token | 2 Tage | `python refresh.py` ausführen |
| Refresh Token | 30 Tage | `python pair.py` erneut ausführen |

---

### Token erneuern (alle 2 Tage)

```bash
cd /opt/Vidaa-Remote
source bin/activate
python refresh.py
deactivate
sudo systemctl restart vidaa-remote
```

> **Tipp:** Mit einem Cron-Job automatisieren:
> ```bash
> sudo crontab -e
> # Token erneuern alle 2 Tage (z.B. jeden geraden Tag um 3 Uhr)
> 0 3 */2 * * cd /opt/Vidaa-Remote && ./bin/python refresh.py && systemctl restart vidaa-remote
>
> # Pairing alle 25 Tage (vor Ablauf des 30-Tage-Refresh-Tokens)
> 0 3 */25 * * cd /opt/Vidaa-Remote && ./bin/python pair.py
> ```

---

## Projektstruktur

```
Vidaa-Remote/
├── app.py                  # Flask-App (Hauptprogramm)
├── bin/                    # bin-Verzeichnis des Virtualenv's (lokal erstellt, nicht im Repo)
├── config.py               # Konfiguration (IP, MAC, Tokens)
├── include/                # include-Verzeichnis des Virtualenv's (lokal erstellt, nicht im Repo)
├── lib/                    # lib-Verzeichnis des Virtualenv's (lokal erstellt, nicht im Repo)
├── lib64/                  # lib64-Verzeichnis des Virtualenv's (lokal erstellt, nicht im Repo)
├── pair.py                 # Einmaliges TV-Pairing
├── pyvenv.cfg              # Konfigurationsdatei des Virtualenv's (lokal erstellt, nicht im Repo)
├── README.md               # README des Projekts
├── refresh.py              # Token erneuern
├── requirements.txt
├── templates/
│    └── remote.html        # Web-Frontend
├── vidaa-remote.service    # systemd-Unit für DietPi/Raspberry Pi
```

> **Hinweis:** Der erste `pip install` kann 2–10 Minuten dauern, da manche Pakete je nach Plattform (z.B. ARM) kompiliert werden könnten. Einfach abwarten.

---

## Funktionsübersicht

| Kategorie | Funktionen |
|---|---|
| Power | An/Aus |
| Navigation | Hoch/Runter/Links/Rechts/OK/Zurück/Home/Menü/Exit |
| Lautstärke | +/−, Direktwert per Slider, Mute |
| Kanal | +/− |
| Wiedergabe | Play/Pause/Stop/Vorspulen/Zurückspulen |
| Eingänge | TV, HDMI 1–3 |
| Apps | Netflix, YouTube, Prime Video, Disney+ |
| Farbtasten | Rot/Grün/Gelb/Blau |
| Zifferntasten | 0–9 |
| Info | Status-Anzeige (Kanal, Lautstärke, Verbindung) |

---

## Problembehandlung

**„Nicht verbunden" in der App**
→ Token abgelaufen: `python refresh.py` ausführen
→ TV ausgeschaltet oder IP geändert

**TV zeigt keinen PIN beim Pairing**
→ TV neu starten und `pair.py` erneut ausführen
→ Sicherstellen dass TV und Rechner im selben Netzwerk sind

**RC=5 Fehler**
→ Token abgelaufen → `python refresh.py`
→ Oder komplett neu pairen: `python pair.py`
