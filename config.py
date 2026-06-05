"""
Vidaa Remote – Konfiguration
Hier einmalig deine TV-Daten eintragen.
"""

# ── TV-Netzwerk ──────────────────────────────────────────────
TV_IP   = '192.168.0.X'        # IP-Adresse des TVs (am besten im Router fest vergeben)
TV_PORT = 36669                # MQTT-Port (nicht ändern)
MAC     = 'AA:BB:CC:DD:EE:FF'  # MAC-Adresse des TVs

# ── Tokens (werden durch pair.py automatisch befüllt) ────────
ACCESS_TOKEN  = ''
REFRESH_TOKEN = ''

# ── Flask ────────────────────────────────────────────────────
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
