from main.config_file import jsonfile
import user_config

_DEFAULTS = {
    'WAKEUP_PERIOD': '60',
    'NODE_NAME':     'None',
    'UTC_OFS':       '0',
    'UNIT':          'C',
    'DEBUG_MODE':    '0',
}

def review_u_config(cfg):
    for key, val in _DEFAULTS.items():
        if key not in cfg:
            cfg[key] = val

    try:
        int(cfg['WAKEUP_PERIOD'])
    except (ValueError, TypeError):
        cfg['WAKEUP_PERIOD'] = _DEFAULTS['WAKEUP_PERIOD']

    try:
        import main.secrets as secrets
        _ = secrets.WIFI_SSID, secrets.WIFI_PASS
        cfg['WIFI_CONF'] = True
    except Exception:
        print('No WiFi: secrets.py missing or incomplete')
        cfg['WIFI_CONF'] = False

    cfg['MQTT_CONF'] = 'MQTT_SERVER' in cfg


def collect_u_config():
    cfg = jsonfile('/config.json', user_config.default_user_config).get_data()
    review_u_config(cfg)
    return cfg
