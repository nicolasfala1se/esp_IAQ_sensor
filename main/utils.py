import network
from time import sleep_ms, ticks_ms, ticks_diff
from machine import Pin

GITHUB_HTTPS_ADDRESS = "https://github.com/nicolasfala1se/esp_IAQ_sensor"

def wifi_connect(wifi_ssid, wifi_password, verbose=False, timeout_ms=15000):
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        if verbose:
            print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(wifi_ssid, wifi_password)
        t0 = ticks_ms()
        while not sta_if.isconnected():
            if ticks_diff(ticks_ms(), t0) > timeout_ms:
                raise OSError('WiFi connect timeout')
            sleep_ms(200)
        if verbose:
            print('network config:', sta_if.ifconfig())
            print('network status:', sta_if.status())
    elif verbose:
        print("Already connected to network")

def wifi_disconnect():
    sta_if = network.WLAN(network.STA_IF)
    if sta_if.active():
        sta_if.disconnect()
        sta_if.active(False)

class led:
    def __init__(self, pin_number):
        self._pin = Pin(pin_number, Pin.OUT) if pin_number is not None else None

    def set_on(self):
        if self._pin is not None:
            self._pin.value(1)

    def set_off(self):
        if self._pin is not None:
            self._pin.value(0)
