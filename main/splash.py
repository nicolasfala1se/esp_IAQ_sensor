import machine
from main.oled_screen import oled_screen

_SCL = 18
_SDA = 5
_OLED_ADDR = 60


def show():
    i2c = machine.I2C(scl=machine.Pin(_SCL), sda=machine.Pin(_SDA), freq=400000)
    if _OLED_ADDR in i2c.scan():
        oled = oled_screen(i2c, _OLED_ADDR)
        oled.load_logo()
        del oled
    del i2c
