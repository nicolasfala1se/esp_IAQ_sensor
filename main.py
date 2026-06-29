# main.py file

def init_screen():
    import sys, gc
    import main.splash as splash
    splash.show()
    for mod in ('main.splash', 'main.lcd_screen', 'main.freesans25',
                'main.calibri10', 'main.oled_screen'):
        sys.modules.pop(mod, None)
    gc.collect()

def boot():
    import gc, machine, main.secrets as secrets, network
    from main.ota_updater import OTAUpdater
    from main.utils import GITHUB_HTTPS_ADDRESS

    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(secrets.WIFI_SSID, secrets.WIFI_PASS)
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())
    gc.collect()

    print('Memory free', gc.mem_free())

    otaUpdater = OTAUpdater(GITHUB_HTTPS_ADDRESS, main_dir='main', secrets_file="secrets.py")
    try:
        hasUpdated = otaUpdater.install_update_if_available()
        if hasUpdated:
            machine.reset()
    except Exception as e:
        print('OTA check failed:', e)
    finally:
        del otaUpdater
        import sys
        for mod in ('main.ota_updater', 'main.httpclient'):
            sys.modules.pop(mod, None)
        gc.collect()

def start_app():
    # execute application
    from main.review_config import collect_u_config
    import sys, gc

    u_config = collect_u_config()

    for mod in ('main.review_config', 'main.config_file', 'user_config'):
        sys.modules.pop(mod, None)
    gc.collect()

    from main.appl import application
    print('Memory free in application', gc.mem_free())
    application(u_config)

if __name__ == "__main__":
    init_screen()
    boot()
    start_app()
