"""
Vidaa Remote – Token erneuern
Führe dieses Skript aus, wenn der Access Token abgelaufen ist (nach 2 Tagen).
Der Refresh Token ist 30 Tage gültig. Danach muss pair.py erneut ausgeführt werden.

Aufruf: python refresh.py
"""

import paho.mqtt.client as mqtt
import ssl, json, re, sys, os, threading
from vidaa.credentials import generate_credentials
from vidaa.protocol import AuthMethod
import config


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

_connected = threading.Event()
_done      = threading.Event()


def save_tokens(access_token, refresh_token):
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
    print(f'✓ Neuer Access Token gespeichert (gültig 2 Tage).')
    print(f'  {access_token[:40]}…')


def on_connect(client, userdata, flags, reason_code, properties):
    ok = not getattr(reason_code, 'is_failure', False)
    if ok:
        print('✓ Verbunden. Sende Refresh-Anfrage…')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/platform_service/data/tokenissuance')
        _connected.set()
        # Refresh Token als Passwort senden
        client.publish(
            f'/remoteapp/tv/platform_service/{CLIENT_ID}/data/gettoken',
            json.dumps({"refreshtoken": config.REFRESH_TOKEN})
        )
    else:
        print(f'✗ Verbindung fehlgeschlagen: {reason_code}')
        print('  Möglicherweise ist auch der Refresh Token abgelaufen.')
        print('  Führe pair.py erneut aus.')
        sys.exit(1)


def on_message(client, userdata, msg):
    if 'tokenissuance' in msg.topic:
        try:
            payload = json.loads(msg.payload.decode())
            access  = payload.get('accesstoken', '')
            refresh = payload.get('refreshtoken', config.REFRESH_TOKEN)
            if access:
                save_tokens(access, refresh)
                print('✓ Token-Refresh erfolgreich!')
            else:
                print('✗ Kein neuer Token erhalten. Führe pair.py erneut aus.')
        except Exception as e:
            print(f'✗ Fehler: {e}')
        _done.set()


def on_disconnect(client, userdata, flags, reason_code, properties):
    pass


def main():
    if not config.REFRESH_TOKEN:
        print('✗ Kein Refresh Token in config.py. Führe zuerst pair.py aus.')
        sys.exit(1)

    print(f'Verbinde mit {config.TV_IP} für Token-Refresh…')

    c = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    # Beim Refresh: Access Token als Password (oder Refresh Token wenn abgelaufen)
    c.username_pw_set(creds.username, config.ACCESS_TOKEN or config.REFRESH_TOKEN)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    c.tls_set_context(ctx)

    c.on_connect    = on_connect
    c.on_message    = on_message
    c.on_disconnect = on_disconnect

    c.connect(config.TV_IP, config.TV_PORT, keepalive=60)
    c.loop_start()

    if not _connected.wait(timeout=10):
        print('✗ Timeout – TV nicht erreichbar.')
        sys.exit(1)

    _done.wait(timeout=15)
    c.loop_stop()
    c.disconnect()


if __name__ == '__main__':
    main()
