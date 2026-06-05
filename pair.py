"""
Vidaa Remote – Einmaliges Pairing
Führe dieses Skript einmalig aus, um den TV zu koppeln.
Der PIN erscheint kurz auf dem TV-Bildschirm.
Die Tokens werden automatisch in config.py gespeichert.

Aufruf: python pair.py
"""

import paho.mqtt.client as mqtt
import ssl, json, re, sys, os, time, threading
from vidaa.credentials import generate_credentials
from vidaa.protocol import AuthMethod
import config

# ── Zertifikatspfad automatisch ermitteln ───────────────────
def find_certs():
    import os, sys
    # Direkt relativ zum Skript suchen (funktioniert mit venv in .)
    base = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(os.path.join(base, 'lib')):
        if 'vidaa_client.pem' in files:
            return root
    sys.exit('FEHLER: vidaa_client.pem nicht gefunden unter lib/')

CERT_DIR  = find_certs()
CERT_FILE = os.path.join(CERT_DIR, 'vidaa_client.pem')
KEY_FILE  = os.path.join(CERT_DIR, 'vidaa_client.key')

creds     = generate_credentials(config.MAC, auth_method=AuthMethod.MODERN)
CLIENT_ID = creds.client_id

pin_sent     = False
_connected   = threading.Event()
_done        = threading.Event()
_client      = None


def save_tokens(access_token, refresh_token):
    """Schreibt die Tokens direkt in config.py."""
    path = os.path.join(os.path.dirname(__file__), 'config.py')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(
        r"^ACCESS_TOKEN\s*=\s*'[^']*'",
        f"ACCESS_TOKEN  = '{access_token}'",
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r"^REFRESH_TOKEN\s*=\s*'[^']*'",
        f"REFRESH_TOKEN = '{refresh_token}'",
        content, flags=re.MULTILINE
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'\n✓ Tokens in config.py gespeichert.')
    print(f'  Access Token  (2 Tage gültig): {access_token[:30]}…')
    print(f'  Refresh Token (30 Tage):        {refresh_token[:30]}…')


def on_connect(client, userdata, flags, reason_code, properties):
    ok = not getattr(reason_code, 'is_failure', False)
    if ok:
        print('✓ Mit TV verbunden.')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/ui_service/data/authentication')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/ui_service/data/authenticationcode')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/platform_service/data/tokenissuance')
        _connected.set()
        # Pairing starten
        client.publish(
            f'/remoteapp/tv/ui_service/{CLIENT_ID}/actions/vidaa_app_connect',
            json.dumps({"app_version": 2, "connect_result": 0, "device_type": "Mobile App"})
        )
        print('→ Pairing-Anfrage gesendet — PIN erscheint gleich auf dem TV…')
    else:
        print(f'✗ Verbindung fehlgeschlagen: {reason_code}')
        sys.exit(1)


def on_message(client, userdata, msg):
    global pin_sent
    try:
        payload = json.loads(msg.payload.decode())
    except:
        payload = {}

    # TV fordert PIN an
    if msg.topic.endswith('/ui_service/data/authentication') and not pin_sent:
        pin = input('\n>>> PIN vom TV-Bildschirm eingeben: ').strip()
        pin_sent = True
        client.publish(
            f'/remoteapp/tv/ui_service/{CLIENT_ID}/actions/authenticationcode',
            json.dumps({"authNum": int(pin)})
        )
        print('→ PIN gesendet…')

    # PIN-Ergebnis
    elif 'authenticationcode' in msg.topic:
        result = payload.get('result')
        if result == 1:
            print('✓ PIN akzeptiert! Fordere Token an…')
            client.publish(
                f'/remoteapp/tv/platform_service/{CLIENT_ID}/data/gettoken',
                json.dumps({"refreshtoken": ""})
            )
            client.publish(
                f'/remoteapp/tv/ui_service/{CLIENT_ID}/actions/authenticationcodeclose',
                ""
            )
        else:
            print(f'✗ PIN abgelehnt (result={result}). Bitte neu starten.')
            _done.set()

    # Token erhalten
    elif 'tokenissuance' in msg.topic:
        access  = payload.get('accesstoken', '')
        refresh = payload.get('refreshtoken', '')
        if access:
            save_tokens(access, refresh)
            print('\n✓ Pairing abgeschlossen! Du kannst jetzt app.py starten.')
        else:
            print('✗ Kein Token erhalten.')
        _done.set()


def on_disconnect(client, userdata, flags, reason_code, properties):
    pass


def main():
    global _client
    print(f'Verbinde mit {config.TV_IP}:{config.TV_PORT}…')
    print(f'Client-ID: {CLIENT_ID}\n')

    c = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    c.username_pw_set(creds.username, creds.password)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    c.tls_set_context(ctx)

    c.on_connect    = on_connect
    c.on_message    = on_message
    c.on_disconnect = on_disconnect

    _client = c
    c.connect(config.TV_IP, config.TV_PORT, keepalive=60)
    c.loop_start()

    if not _connected.wait(timeout=10):
        print('✗ Timeout – TV nicht erreichbar. IP und Netzwerk prüfen.')
        sys.exit(1)

    _done.wait(timeout=30)
    c.loop_stop()
    c.disconnect()


if __name__ == '__main__':
    main()
