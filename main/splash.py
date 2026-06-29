
_SCL = 18
_SDA = 5
_OLED_ADDR = 60

_LCD_SPI_BUS  = 1
_LCD_SPI_SCK  = 14
_LCD_SPI_MOSI = 13
_LCD_SPI_CS   = 15
_LCD_SPI_DC   = 27
_LCD_SPI_RST  = 26
_LCD_SPI_BL   = 25
_LCD_Y_OFFSET = 35


def show():
    import machine
    i2c = machine.I2C(scl=machine.Pin(_SCL), sda=machine.Pin(_SDA), freq=400000)
    if _OLED_ADDR in i2c.scan():
        from main.oled_screen import oled_screen
        oled = oled_screen(i2c, _OLED_ADDR)
        oled.load_logo()
        del oled
    else:
        try:
            from main.lcd_screen import lcd_screen
            spi = machine.SPI(_LCD_SPI_BUS, baudrate=40000000,
                              sck=machine.Pin(_LCD_SPI_SCK),
                              mosi=machine.Pin(_LCD_SPI_MOSI))
            lcd = lcd_screen(spi, _LCD_SPI_CS, _LCD_SPI_DC,
                             _LCD_SPI_RST, _LCD_SPI_BL,
                             y_offset=_LCD_Y_OFFSET)
            lcd.load_logo()
            del lcd
            spi.deinit()
            del spi
        except Exception as e:
            print('LCD splash failed:', e)
    del i2c
