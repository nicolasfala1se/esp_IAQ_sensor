# ST7789V2 SPI LCD driver + screen class for 240x280 IPS display.
#
# Wiring (ESP32 HSPI — non-conflicting with I2C on SCL=18/SDA=5):
#   LCD VCC  → 3.3 V
#   LCD GND  → GND
#   LCD SCL/CLK  → GPIO 14   (HSPI clock)
#   LCD SDA/DIN  → GPIO 13   (HSPI MOSI)
#   LCD CS       → GPIO 15
#   LCD DC/RS    → GPIO 27
#   LCD RST/RES  → GPIO 26
#   LCD BL       → GPIO 25   (via 33 Ω resistor, or direct 3.3 V for always-on)
#   MISO is not connected (write-only).

import struct
from time import sleep_ms
from machine import Pin
import main.freesans25 as font25
import main.calibri10 as font10

# RGB565 palette
_BLACK  = 0x0000
_WHITE  = 0xFFFF
_GREEN  = 0x07E0
_CYAN   = 0x07FF
_YELLOW = 0xFFE0
_GRAY   = 0x7BEF
_RED    = 0xF800

_BG = _BLACK
_FG = _WHITE

# Pre-allocated RGB565 glyph buffer.
# Sized for freesans25 at scale=2: max_width=24*2=48, height=25*2=50 → 48*50*2 = 4800 bytes.
_LCD_GLYPH_BUF = bytearray(4800)



class _ST7789V2:
    """Minimal write-only SPI driver for ST7789V2. No MISO, no external dependency."""

    _SWRESET = 0x01
    _SLPOUT  = 0x11
    _NORON   = 0x13
    _INVON   = 0x21
    _DISPON  = 0x29
    _CASET   = 0x2A
    _RASET   = 0x2B
    _RAMWR   = 0x2C
    _MADCTL  = 0x36
    _COLMOD  = 0x3A

    def __init__(self, spi, dc, cs, rst=None, width=240, height=280,
                 x_offset=0, y_offset=0):
        self._spi   = spi
        self._dc    = dc
        self._cs    = cs
        self._rst   = rst
        self.width  = width
        self.height = height
        self._xoff  = x_offset
        self._yoff  = y_offset
        self._reset()
        self._init()

    def _reset(self):
        if self._rst:
            self._rst.value(0)
            sleep_ms(50)
            self._rst.value(1)
            sleep_ms(150)

    def _cmd(self, cmd, data=None):
        self._dc.value(0)
        self._cs.value(0)
        self._spi.write(bytes([cmd]))
        self._cs.value(1)
        if data is not None:
            self._dc.value(1)
            self._cs.value(0)
            self._spi.write(bytes(data))
            self._cs.value(1)

    def _init(self):
        self._cmd(self._SWRESET)
        sleep_ms(150)
        self._cmd(self._SLPOUT)
        sleep_ms(120)
        self._cmd(self._COLMOD, [0x05])   # RGB565
        self._cmd(self._MADCTL, [0x00])   # portrait, top-left origin
        self._cmd(self._INVON)            # ST7789V2 requires inversion
        self._cmd(self._NORON)
        # Clear full physical GDDRAM from row 0 (bypass y_offset) so the top
        # y_offset rows don't show uninitialized garbage on the panel.
        saved = self._yoff
        self._yoff = 0
        self.fill_rect(0, 0, self.width, self.height + saved, 0x0000)
        self._yoff = saved
        self._cmd(self._DISPON)
        sleep_ms(20)

    def _set_window(self, x0, y0, x1, y1):
        x0 += self._xoff; x1 += self._xoff
        y0 += self._yoff; y1 += self._yoff
        self._cmd(self._CASET, struct.pack('>HH', x0, x1))
        self._cmd(self._RASET, struct.pack('>HH', y0, y1))
        # send RAMWR command, then leave DC high for pixel data stream
        self._dc.value(0)
        self._cs.value(0)
        self._spi.write(bytes([self._RAMWR]))
        self._dc.value(1)

    def fill_rect(self, x, y, w, h, color):
        self._set_window(x, y, x + w - 1, y + h - 1)
        pixel = bytes([color >> 8, color & 0xFF])
        chunk = pixel * 64
        n = w * h
        while n >= 64:
            self._spi.write(chunk)
            n -= 64
        if n:
            self._spi.write(pixel * n)
        self._cs.value(1)

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)

    def blit_buffer(self, buf, x, y, w, h):
        self._set_window(x, y, x + w - 1, y + h - 1)
        self._spi.write(buf)
        self._cs.value(1)


class lcd_screen:
    """
    240x280 colour LCD with the same public interface as oled_screen.
    Drop-in replacement — appl.py calls update_screen() identically on both.
    """

    def __init__(self, spi, cs, dc, rst, bl=None, unit="C",
                 x_offset=0, y_offset=0):
        self._tft = _ST7789V2(
            spi,
            dc  = Pin(dc,  Pin.OUT),
            cs  = Pin(cs,  Pin.OUT),
            rst = Pin(rst, Pin.OUT),
            x_offset=x_offset,
            y_offset=y_offset,
        )
        if bl is not None:
            Pin(bl, Pin.OUT).value(1)
        self.unit           = unit
        self._str_text      = ""
        self._str_sub_text  = ""
        self._str_version   = ""
        self._sensor_name   = ""
        self._ip            = ""
        self._node_name     = ""

    def load_logo(self):
        self._tft.fill(_BG)
        self._draw_str(font25, "MqttS2",    4,  80, _FG, scale=2)
        self._draw_str(font10, "Loading...", 4, 130, _GRAY, scale=2)

    def set_sensor_config(self, sensor):
        self._sensor_name = sensor

    def set_system_info(self, ip, node_name):
        self._ip        = ip
        self._node_name = node_name

    def show(self):
        pass  # LCD blits are immediate; present for interface compatibility

    # ── rendering helpers ────────────────────────────────────────────────────

    def _glyph_w(self, font, s, scale=1):
        return sum(font.get_ch(c)[2] for c in s) * scale

    def _draw_glyph(self, glyph, w, h, x, y, fg, bg, scale):
        sw = w * scale
        sh = h * scale
        fg_hi, fg_lo = fg >> 8, fg & 0xFF
        bg_hi, bg_lo = bg >> 8, bg & 0xFF
        row_bytes = (w + 7) // 8
        mv = memoryview(_LCD_GLYPH_BUF)
        for sy in range(sh):
            src_y    = sy // scale
            row_base = src_y * row_bytes
            out_base = sy * sw
            for sx in range(sw):
                src_x = sx // scale
                bit = (glyph[row_base + src_x // 8] >> (7 - src_x % 8)) & 1
                i = (out_base + sx) * 2
                if bit:
                    mv[i] = fg_hi; mv[i + 1] = fg_lo
                else:
                    mv[i] = bg_hi; mv[i + 1] = bg_lo
        self._tft.blit_buffer(mv[:sw * sh * 2], x, y, sw, sh)
        return sw

    def _draw_str(self, font, s, x, y, fg=_FG, bg=_BG, scale=1):
        xpos = x
        for c in s:
            glyph, h, w = font.get_ch(c)
            xpos += self._draw_glyph(glyph, w, h, xpos, y, fg, bg, scale)

    # ── main display update ──────────────────────────────────────────────────

    def _draw_page2(self):
        tft = self._tft
        tft.fill(_BG)
        tft.fill_rect(0, 32, 240, 2, _GRAY)
        self._draw_str(font10, "Node:", 4, 4, _GRAY, scale=2)
        self._draw_str(font10, self._node_name, 4, 38, _CYAN, scale=2)
        tft.fill_rect(0, 72, 240, 1, _GRAY)
        self._draw_str(font10, "IP:", 4, 80, _GRAY, scale=2)
        self._draw_str(font10, self._ip if self._ip else "---", 4, 104, _WHITE, scale=2)
        self._draw_str(font10, self._sensor_name, 4, 140, _YELLOW, scale=2)
        if self._str_version:
            self._draw_str(font10, "v" + self._str_version, 4, 164, _GRAY, scale=2)
        import utime
        uptime_min = utime.ticks_ms() // 60000
        self._draw_str(font10, "Up:%dm" % uptime_min, 4, 200, _GRAY, scale=2)

    def update_screen(self, wifi_valid, mqtt_valid, tm, temp, hum,
                      str_text=None, sub_text=None, version=None, page=0):
        if version is not None:
            self._str_version = version
        if page == 1:
            self._draw_page2()
            return
        tft = self._tft
        tft.fill(_BG)

        # ── header band (y=0–33): status labels + sensor label ──────────────────
        x = 4
        self._draw_str(font10, "Wifi", x, 4, _GREEN if wifi_valid else _RED, scale=2)
        x += self._glyph_w(font10, "Wifi", scale=2) + 10
        self._draw_str(font10, "Mqtt", x, 4, _GREEN if mqtt_valid else _RED, scale=2)
        x += self._glyph_w(font10, "Mqtt", scale=2) + 10
        if self._sensor_name:
            self._draw_str(font10, self._sensor_name, x, 4, _CYAN, scale=2)

        # separator line below header
        tft.fill_rect(0, 32, 240, 2, _GRAY)

        # ── pressure + time on same line ─────────────────────────────────────
        if sub_text is not None:
            self._str_sub_text = sub_text
        hours    = tm[3] % 12 if tm[3] != 12 else 12
        time_str = "%d:%02d" % (hours, tm[4])
        tw = self._glyph_w(font25, time_str)
        self._draw_str(font25, time_str, 240 - tw - 4, 38, _FG)
        if self._str_sub_text:
            self._draw_str(font10, self._str_sub_text, 4, 38, _YELLOW, scale=2)

        # ── large temperature (left) + humidity (right) ──────────────────────
        if temp is not None:
            temp_str = "%d" % temp + self.unit
            self._draw_str(font25, temp_str, 4, 80, _WHITE, scale=2)
        if hum is not None:
            hum_str = "%d%%" % hum
            hw = self._glyph_w(font25, hum_str, scale=2)
            self._draw_str(font25, hum_str, 240 - hw, 80, _CYAN, scale=2)

        # ── status / IAQ text ────────────────────────────────────────────────
        if str_text is not None:
            self._str_text = str_text
        if self._str_text:
            self._draw_str(font25, self._str_text, 4, 200, _YELLOW)

        # ── version (below status text, right-justified) ─────────────────────
        if self._str_version:
            vw = self._glyph_w(font10, self._str_version, scale=2)
            self._draw_str(font10, self._str_version, 240 - vw - 6, 235, _WHITE, scale=2)
