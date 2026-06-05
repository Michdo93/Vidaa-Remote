"""
Vidaa Remote – Flask Web-App
Starten: python app.py
Browser: http://localhost:5000
"""

from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import ssl, json, threading, sys, os
from vidaa.credentials import generate_credentials
from vidaa.protocol import AuthMethod
import config

app = Flask(__name__)


# ── Zertifikatspfad ─────────────────────────────────────────
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


# ── MQTT-Setup ───────────────────────────────────────────────
creds     = generate_credentials(config.MAC, auth_method=AuthMethod.MODERN)
CLIENT_ID = creds.client_id

tv_state = {
    'connected': False,
    'channel':   '–',
    'source':    'TV',
    'volume':    0,
    'muted':     False,
}

_mqtt_client  = None
_connected_ev = threading.Event()
_lock         = threading.Lock()


def on_connect(client, userdata, flags, reason_code, properties):
    ok = not getattr(reason_code, 'is_failure', False)
    if ok:
        with _lock:
            tv_state['connected'] = True
        client.subscribe('/remoteapp/mobile/broadcast/ui_service/state')
        client.subscribe('/remoteapp/mobile/broadcast/ui_service/volume')
        client.subscribe('/remoteapp/mobile/broadcast/platform_service/actions/volumechange')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/ui_service/data/sourcelist')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/ui_service/data/authentication')
        client.subscribe(f'/remoteapp/mobile/{CLIENT_ID}/platform_service/data/tokenissuance')
        _connected_ev.set()
        print(f'✓ TV verbunden ({config.TV_IP})')
    else:
        with _lock:
            tv_state['connected'] = False
        print(f'✗ TV-Verbindung fehlgeschlagen: {reason_code}')
        print('  → Führe python refresh.py oder python pair.py aus.')


def on_disconnect(client, userdata, flags, reason_code, properties):
    with _lock:
        tv_state['connected'] = False
    _connected_ev.clear()
    print('TV getrennt. Versuche Reconnect…')


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except:
        return
    topic = msg.topic
    with _lock:
        if 'broadcast/ui_service/state' in topic:
            tv_state['channel'] = payload.get('channel_name', tv_state['channel'])
            tv_state['source']  = payload.get('sourceid', tv_state['source'])
        elif 'volumechange' in topic or '/volume' in topic:
            vtype = payload.get('volume_type', 0)
            if vtype == 0:
                tv_state['volume'] = payload.get('volume_value', tv_state['volume'])
            elif vtype == 2:
                tv_state['muted'] = (payload.get('volume_value', 0) == 1)


def build_and_connect():
    global _mqtt_client
    _connected_ev.clear()

    if not config.ACCESS_TOKEN:
        print('✗ Kein Access Token in config.py. Führe zuerst pair.py aus.')
        return False

    if _mqtt_client:
        try:
            _mqtt_client.loop_stop()
            _mqtt_client.disconnect()
        except:
            pass

    c = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )
    c.username_pw_set(creds.username, config.ACCESS_TOKEN)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    c.tls_set_context(ctx)

    c.on_connect    = on_connect
    c.on_disconnect = on_disconnect
    c.on_message    = on_message

    _mqtt_client = c
    try:
        c.connect(config.TV_IP, config.TV_PORT, keepalive=60)
        c.loop_start()
        return _connected_ev.wait(timeout=8)
    except Exception as e:
        print(f'Verbindungsfehler: {e}')
        return False


def ensure_connected():
    if tv_state['connected']:
        return True
    return build_and_connect()


def pub(topic, payload=''):
    if not ensure_connected():
        return False
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    _mqtt_client.publish(topic, payload)
    return True


# ── Flask Routes ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('remote.html')


@app.route('/api/status')
def status():
    with _lock:
        state = dict(tv_state)
    if not state['connected']:
        ensure_connected()
    return jsonify(state)


@app.route('/api/key/<key>', methods=['POST'])
def key_press(key):
    ok = pub(f'/remoteapp/tv/remote_service/{CLIENT_ID}/actions/sendkey', key)
    return jsonify({'ok': ok})


@app.route('/api/volume', methods=['POST'])
def volume():
    level = (request.json or {}).get('level')
    if level is None:
        return jsonify({'ok': False, 'error': 'level missing'})
    level = max(0, min(100, int(level)))
    ok = pub(f'/remoteapp/tv/platform_service/{CLIENT_ID}/actions/changevolume', str(level))
    return jsonify({'ok': ok})


@app.route('/api/source/<source_id>', methods=['POST'])
def source(source_id):
    ok = pub(f'/remoteapp/tv/ui_service/{CLIENT_ID}/actions/changesource',
             {'sourceid': str(source_id)})
    return jsonify({'ok': ok})


@app.route('/api/app', methods=['POST'])
def app_launch():
    data = request.json or {}
    ok = pub(f'/remoteapp/tv/ui_service/{CLIENT_ID}/actions/launchapp', data)
    return jsonify({'ok': ok})


@app.route('/api/connect', methods=['POST'])
def reconnect():
    ok = build_and_connect()
    return jsonify({'ok': ok, 'connected': tv_state['connected']})


if __name__ == '__main__':
    print('Vidaa Remote startet…')
    build_and_connect()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=False,
        use_reloader=False,
    )
