import network
from time import sleep_ms
from machine import Pin

GITHUB_HTTPS_ADDRESS = "https://github.com/nicolasfala1se/esp_IAQ_sensor"

def wifi_connect(wifi_ssid, wifi_password, verbose=False):
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        if verbose:
            print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(wifi_ssid, wifi_password)
        while not sta_if.isconnected():
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
