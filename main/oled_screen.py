import ssd1306, framebuf
import main.freesans25 as font25
import main.calibri10 as font10

hSize       = 64  # Hauteur ecran en pixels | display heigh in pixels
wSize       = 128 # Largeur ecran en pixels | display width in pixels

bmp_wifi = bytearray(b'\x00\x03\x05\t\x11\xff\x11\xc9\x05\xe3\x00\xf0\x00\xf8\x00\xfc')
mqtt_bmp = bytearray(b'~\x02\x04\x02~\x00<Bb|\x00\x02~\x02\x00\x02~\x02\x00\x00')
b6_bmp = bytearray(b'~JJ4\x00<JJ0\x00')
b2_bmp = bytearray(b'~JJ4\x00DbRL\x00')

class oled_screen(ssd1306.SSD1306_I2C):
    def __init__ (self, i2c, addr=0x3c, unit="F"):
        super().__init__(wSize, hSize, i2c, addr)
        self.unit = unit
        self.bme680_present = False
        self.bme280_present = False
        self.str_text=""
        self.str_sub_text=""
        self.bme_display = None

    def load_logo(self):
        self.print_scr(font25, "MqttS1", 0, 10 )
        super().text("Loading...",0,50)
        super().show()

    def set_sensor_config ( self, sensor ):
        if sensor == 'BME680':
            self.bme_display = b6_bmp
        else:
            self.bme_display = b2_bmp

    def print_scr(self, font, s, x, y):
        xpos = x
        ypos = y
        for c in s:
            glyph, char_height, char_width = font.get_ch(c)
            buf = bytearray(glyph)
            fbc = framebuf.FrameBuffer(buf, char_width, char_height, framebuf.MONO_HLSB)
            super().blit(fbc, xpos, ypos)
            xpos += char_width
        #print("end: ",xpos)

    def text( self, s):
        if s is not None:
            self.str_text=s
    
    def sub_text( self, s):
        if s is not None:
            self.str_sub_text=s 

    def update_screen ( self, wifi_valid, mqtt_valid, tm, temp, hum, str_text=None, sub_text=None ):
        super().fill(0)
        if wifi_valid:
            fb = framebuf.FrameBuffer(bmp_wifi, 16, 8, framebuf.MONO_VLSB)
            super().blit(fb, 0, 0)
        if mqtt_valid:
            fb = framebuf.FrameBuffer(mqtt_bmp, 20, 8, framebuf.MONO_VLSB)
            super().blit(fb, 24, 0)
        # display sensor
        if self.bme_display is not None:
            fb = framebuf.FrameBuffer(self.bme_display, 10, 8, framebuf.MONO_VLSB)
            super().blit(fb, 48, 0)

        hours = tm[3]%12 if tm[3] != 12 else 12
        str_to_print = "%2d:%02d"%(hours,tm[4])
        self.print_scr(font25,str_to_print,64,0)
        if temp is not None:
            str_to_print = "%3d"%temp+self.unit
            self.print_scr(font25, str_to_print,0,28)
        if hum is not None:
            str_to_print = "%3d%%"%hum
            self.print_scr(font25, str_to_print,64,28)

        self.text(str_text)
        super().text(self.str_text,0,56,1)

        self.sub_text(sub_text)
        self.print_scr(font10,self.str_sub_text,0,10)

        super().show()
