import ssd1306, framebuf
import main.freesans25 as font25
import main.calibri10 as font10

_bmp_wifi = bytearray(b'\x00\x03\x05\t\x11\xff\x11\xc9\x05\xe3\x00\xf0\x00\xf8\x00\xfc')
_bmp_mqtt = bytearray(b'~\x02\x04\x02~\x00<Bb|\x00\x02~\x02\x00\x02~\x02\x00\x00')
_bmp_b6   = bytearray(b'~JJ4\x00<JJ0\x00')
_bmp_b2   = bytearray(b'~JJ4\x00DbRL\x00')

# Pre-built icon FrameBuffers — created once, blitted every frame
_FB_WIFI = framebuf.FrameBuffer(_bmp_wifi, 16, 8, framebuf.MONO_VLSB)
_FB_MQTT = framebuf.FrameBuffer(_bmp_mqtt, 20, 8, framebuf.MONO_VLSB)
_FB_B6   = framebuf.FrameBuffer(_bmp_b6,   10, 8, framebuf.MONO_VLSB)
_FB_B2   = framebuf.FrameBuffer(_bmp_b2,   10, 8, framebuf.MONO_VLSB)

# Single reusable glyph buffer: freesans25 max_width=24, height=25 → ceil(24/8)*25 = 75 bytes
_GLYPH_BUF = bytearray(75)

class oled_screen(ssd1306.SSD1306_I2C):
    def __init__(self, i2c, addr=0x3c, unit="C"):
        super().__init__(128, 64, i2c, addr)
        self.unit = unit
        self._fb_sensor = None
        self._str_text = ""
        self._str_sub_text = ""
        self._str_version = ""

    def load_logo(self):
        self.print_scr(font25, "MqttS1", 0, 10)
        self.text("Loading...", 0, 50)
        self.show()

    def set_sensor_config(self, sensor):
        self._fb_sensor = _FB_B6 if sensor == 'BME680' else _FB_B2

    def _str_width(self, font, s):
        return sum(font.get_ch(c)[2] for c in s)

    def print_scr(self, font, s, x, y):
        xpos = x
        for c in s:
            glyph, char_height, char_width = font.get_ch(c)
            _GLYPH_BUF[:len(glyph)] = glyph
            self.blit(
                framebuf.FrameBuffer(_GLYPH_BUF, char_width, char_height, framebuf.MONO_HLSB),
                xpos, y)
            xpos += char_width

    def update_screen(self, wifi_valid, mqtt_valid, tm, temp, hum, str_text=None, sub_text=None, version=None):
        self.fill(0)
        if wifi_valid:
            self.blit(_FB_WIFI, 0, 0)
        if mqtt_valid:
            self.blit(_FB_MQTT, 24, 0)
        if self._fb_sensor is not None:
            self.blit(self._fb_sensor, 48, 0)

        hours = tm[3] % 12 if tm[3] != 12 else 12
        time_str = "%d:%02d" % (hours, tm[4])
        self.print_scr(font25, time_str, 128 - self._str_width(font25, time_str), 0)
        if temp is not None:
            temp_str = "%d" % temp + self.unit
            self.print_scr(font25, temp_str , 0, 28)
        if hum is not None:
            hum_str = "%d%%" % hum
            self.print_scr(font25, hum_str, 128 - self._str_width(font25, hum_str), 28)

        if str_text is not None:
            self._str_text = str_text
        self.text(self._str_text, 0, 56, 1)

        if version is not None:
            self._str_version = version
        if self._str_version:
            self.text(self._str_version, 128 - len(self._str_version) * 8, 56, 1)

        if sub_text is not None:
            self._str_sub_text = sub_text
        self.print_scr(font10, self._str_sub_text, 0, 10)

        self.show()
