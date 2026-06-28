# MQTT temperature monitor.
from umqtt.robust import MQTTClient
import main.bme680 as bme680
from main.ota_updater import OTAUpdater
from main.utils import wifi_connect, wifi_disconnect, led, GITHUB_HTTPS_ADDRESS
from main.bme280 import bme280 as BME280
from main.rtos import rtos, rtos_task
from main.schedule_file import schedule_table
from main.oled_screen import oled_screen
from main.ntptime import settime

import machine, time, micropython, framebuf, utime, network
from ubinascii import hexlify
import ujson as json
import gc

micropython.alloc_emergency_exception_buf(100)

debug_mode_verwrite = 1

# Default MQTT server to connect to
CLIENT_ID = b"ESP_"+hexlify(machine.unique_id())
TOPIC_TEMPERATURE = "/temperature"
TOPIC_HUMIDITY = "/humidity"
TOPIC_PRESSURE = "/pressure"
TOPIC_IAQ = "/iaq"

IAQ_HUM_BASELINE  = 40.0   # ideal humidity %
IAQ_HUM_WEIGHTING = 0.25   # humidity share of IAQ score
IAQ_BURN_IN_TICKS = 20     # readings discarded before IAQ is valid (~20 min at 60 s wakeup)

NTP_SYNC_TICKS = 60        # resync NTP every 1 ticks (~1 h at 60 s wakeup)

RUNTIME_FILE = 'runtime.json'

I2C_SCL_PIN_NUMBER = 18
I2C_SDA_PIN_NUMBER = 5

DEFAULT_OLED_I2C_ADDR   = 60   # 0x3c
DEFAULT_BME280_I2C_ADDR = 118  # 0x76
DEFAULT_BME680_I2C_ADDR = 119  # 0x77

LCD_SPI_BUS  = 1   # HSPI — SCK=14, MOSI=13 (non-conflicting with I2C SCL=18/SDA=5)
LCD_SPI_SCK  = 14
LCD_SPI_MOSI = 13
LCD_SPI_CS   = 15
LCD_SPI_DC   = 27
LCD_SPI_RST  = 26
LCD_SPI_BL   = 25
LCD_Y_OFFSET = 35  # 240x280 panels are a 240x320 die; visible rows start at controller row 20

def _load_runtime():
    try:
        with open(RUNTIME_FILE) as f:
            return json.load(f)
    except:
        return {}

def _save_runtime(data):
    try:
        with open(RUNTIME_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print("runtime.json write failed:", e)

def _iaq(gas, humidity, baseline):
    hum_offset = humidity - IAQ_HUM_BASELINE
    if hum_offset > 0:
        hum_score = (100 - IAQ_HUM_BASELINE - hum_offset) / (100 - IAQ_HUM_BASELINE) * IAQ_HUM_WEIGHTING
    else:
        hum_score = (IAQ_HUM_BASELINE + hum_offset) / IAQ_HUM_BASELINE * IAQ_HUM_WEIGHTING
    gas_score = min(gas / baseline, 1.0) * (1.0 - IAQ_HUM_WEIGHTING)
    return (hum_score + gas_score) * 100


class task1 (rtos_task):

    PRESENCE_TIMEOUT = 130000

    def task_init(self, param1):
        self.pin = machine.Pin(16, machine.Pin.OUT)
        self.pin.value(0)
        print("Init application task")

        str_out = ""
        self.wifi_valid, self.mqtt_valid = [False, False]

        # configure led pin
        self.l_pin = led(2)

        self.oledIsConnected, self.bme280IsConnected, self.bme680IsConnected = [False, False, False]
        # init ic2 object
        i2c = machine.I2C(scl=machine.Pin(I2C_SCL_PIN_NUMBER), sda=machine.Pin(I2C_SDA_PIN_NUMBER),freq=400000)
        # Scan i2c bus and check if BME2 and OLDE display are connected
        #print('Scan i2c bus...')
        devices = i2c.scan()
        if len(devices) == 0:
            print("No i2c device !")
        else:
            #print('i2c devices found:',len(devices))
            for device in devices: 
                if device == DEFAULT_OLED_I2C_ADDR:
                    self.oledIsConnected = True
                if device == DEFAULT_BME280_I2C_ADDR:
                    self.bme280IsConnected = True  
                if device == DEFAULT_BME680_I2C_ADDR:
                    self.bme680IsConnected = True  
                #print ('Adr: ',device)
        # BME280
        if self.bme280IsConnected:
            try:
                self.bme280 = BME280.BME280(i2c=i2c, mode=BME280.BME280_OSAMPLE_1, address=DEFAULT_BME280_I2C_ADDR)
            except:
                self.bme280IsConnected = False
                str_out = "No sensor"
                print("Error: No sensor")
            else:
                # discard first measure to switch sensor in FORCED MODE
                self.bme280.read_compensated_data()

        if self.bme680IsConnected:
            try:
                self.bme680 = bme680.BME680(i2c_addr=bme680.constants.I2C_ADDR_SECONDARY, i2c_device=i2c)
                self.bme680.set_humidity_oversample(bme680.constants.OS_2X)
                self.bme680.set_pressure_oversample(bme680.constants.OS_4X)
                self.bme680.set_temperature_oversample(bme680.constants.OS_8X)
                self.bme680.set_filter(bme680.constants.FILTER_SIZE_3)

                self.bme680.set_gas_status(bme680.constants.ENABLE_GAS_MEAS)
                self.bme680.set_gas_heater_temperature(320)
                self.bme680.set_gas_heater_duration(150)
                self.bme680.select_gas_heater_profile(0)
                rt = _load_runtime()
                self.gas_baseline = rt.get('gas_baseline', 50000)
                self.gas_baseline_saved = self.gas_baseline
                self.gas_ticks = 0
            except:
                self.bme680IsConnected = False
                str_out = "No sensor"
                print("Error: No sensor")

        if debug_mode_verwrite != 0:
            self.debug_p = True
        else:
            self.debug_p = False if param1['DEBUG_MODE']=="0" else True 

        # program execution
        if self.debug_p: print("Node: ",param1['NODE_NAME'])
        
        # Display — try OLED (I2C) first, fall back to LCD (SPI)
        # Initialized before WiFi/MQTT so the logo is visible during connection.
        self.oled = None
        if self.oledIsConnected:
            self.oled = oled_screen(i2c, DEFAULT_OLED_I2C_ADDR, unit=param1['UNIT'])
        else:
            try:
                from main.lcd_screen import lcd_screen
                spi = machine.SPI(LCD_SPI_BUS, baudrate=40000000,
                                  sck=machine.Pin(LCD_SPI_SCK),
                                  mosi=machine.Pin(LCD_SPI_MOSI))
                self.oled = lcd_screen(spi, LCD_SPI_CS, LCD_SPI_DC,
                                       LCD_SPI_RST, LCD_SPI_BL, unit=param1['UNIT'],
                                       y_offset=LCD_Y_OFFSET)
                self.oledIsConnected = True
            except Exception as e:
                print('LCD init failed:', e)
                print('! No display')
        self.ntp_ticks = 0
        if param1['WIFI_CONF']:
            import main.secrets as secrets
            self._wifi_ssid = secrets.WIFI_SSID
            self._wifi_pass = secrets.WIFI_PASS
            wifi_connect(self._wifi_ssid, self._wifi_pass)
            self.wifi_valid = True

            if param1['MQTT_CONF']:
                self.c = MQTTClient(CLIENT_ID, param1['MQTT_SERVER'])
                try:
                    self.c.connect()
                    self.mqtt_valid = True
                except:
                    print("unable to connect to MQTT server, will retry")
                    self.mqtt_valid = False

        if self.oled:
            sensor = 'BME680' if self.bme680IsConnected else 'BME280'
            self.oled.set_sensor_config(sensor)
            self.oled.update_screen(self.wifi_valid, self.mqtt_valid, utime.localtime(), None, None, str_text=str_out, version=param1['VERSION'])

# Task body
#
    def task_body(self, param1):

        while True:
            self.pin.value(1)
            self.l_pin.set_on()
            if self.debug_p: print("New measure...")
            str_out = ""
            t, h, p = (None, None, None)
            l_mqtt_valid = False
            iaq_str = None

            dht_measured=0 
            if self.bme280IsConnected: 
                try:
                    t, p, h = self.bme280.read_compensated_data()
                    p = (p/256)/100
                    t = t/100
                    h = h/1024
                except Exception as other:
                    dht_measured=0
                    str_out = "[01] Call Daddy..."
                    print ("Bme exception:", other)
                else:
                    from math import log
                    _g = (log(h, 10) - 2) / 0.4343 + (17.62 * t) / (243.12 + t)
                    dew = 243.12 * _g / (17.62 - _g)

                    if param1['UNIT'] == 'F':
                        dew = dew * 9.0/5.0 + 32
                        str_out = 'Dew pt:{:.0f}F'.format(dew)
                    else:
                        str_out = 'Dew pt:{:.0f}C'.format(dew)

                    dht_measured=1

            if self.bme680IsConnected:
                status = False
                try:                        
                    status = self.bme680.get_sensor_data()
                except Exception as other:
                    dht_measured=0
                    str_out = "[02] Call Daddy..."
                    print ("Bme exception:", other)
                else:
                    if status==True:
                        t = self.bme680.data.temperature
                        h = self.bme680.data.humidity
                        p = self.bme680.data.pressure
                        gas = self.bme680.data.gas_resistance
                        if self.gas_ticks <= IAQ_BURN_IN_TICKS:
                            self.gas_ticks += 1
                        if self.gas_ticks <= IAQ_BURN_IN_TICKS:
                            self.gas_baseline = max(self.gas_baseline, gas)
                            str_out = 'IAQ:warm-up'
                        else:
                            if gas > self.gas_baseline:
                                self.gas_baseline = gas * 0.1 + self.gas_baseline * 0.9
                            else:
                                self.gas_baseline = gas * 0.01 + self.gas_baseline * 0.99
                            if abs(self.gas_baseline - self.gas_baseline_saved) / self.gas_baseline_saved > 0.02:
                                _save_runtime({'gas_baseline': self.gas_baseline})
                                self.gas_baseline_saved = self.gas_baseline
                            iaq = _iaq(gas, h, self.gas_baseline)
                            iaq_str = "{:.1f}".format(iaq)
                            str_out = 'IAQ:{:.0f}'.format(iaq)
                            if self.debug_p:
                                print("Gas:{:.0f} Ohm  IAQ:{}".format(gas, str_out))
                        dht_measured=1
                    else:
                        print ("No data!")
                        dht_measured=0


            if dht_measured == 1:

                if param1['UNIT'] == 'F':
                    t = t*9.0/5.0+32

                temperature_str = "{:.02f}".format(t)
                humidity_str = "{:.02f}".format(h)
                pressure_str = "{:.01f}".format(p)

                # verify wifi connection, reconnect if dropped
                sta_if = network.WLAN(network.STA_IF)
                if not sta_if.isconnected() and param1['WIFI_CONF']:
                    try:
                        wifi_connect(self._wifi_ssid, self._wifi_pass)
                    except Exception as e:
                        print("WiFi reconnect failed:", e)
                self.wifi_valid = sta_if.isconnected()
                del sta_if

                if self.wifi_valid:
                    self.ntp_ticks += 1
                    if self.ntp_ticks >= NTP_SYNC_TICKS:
                        try:
                            settime(int(param1['UTC_OFS']) * 3600)
                            self.ntp_ticks = 0
                            if self.debug_p: print("NTP synced")
                        except Exception as e:
                            print("NTP sync failed:", e)

                    if param1['MQTT_CONF']:
                        if not self.mqtt_valid:
                            try:
                                self.c.connect()
                                self.mqtt_valid = True
                            except Exception as e:
                                print("MQTT reconnect failed:", e)
                        if self.mqtt_valid:
                            try:
                                self.c.publish(param1['NODE_NAME']+TOPIC_TEMPERATURE, temperature_str)
                                self.c.publish(param1['NODE_NAME']+TOPIC_HUMIDITY, humidity_str)
                                self.c.publish(param1['NODE_NAME']+TOPIC_PRESSURE, pressure_str)
                                if iaq_str is not None:
                                    self.c.publish(param1['NODE_NAME']+TOPIC_IAQ, iaq_str)
                                self.mqtt_valid = True
                            except:
                                print("Cannot publish measurements")
                                self.mqtt_valid = False
                else:
                    self.mqtt_valid = False
                l_mqtt_valid = self.mqtt_valid
            
                if self.debug_p: 
                    print("Temperature:", temperature_str)
                    print("Humidity:", humidity_str)
                    print("Pressure:", pressure_str)

            if self.oledIsConnected:
                str_sub_text = ' {:.1f} hPa'.format(p) if p is not None else None
                self.oled.update_screen(self.wifi_valid, l_mqtt_valid, utime.localtime(), t, h, str_text=str_out, sub_text=str_sub_text)
                
            self.l_pin.set_off()
            self.pin.value(0)

            gc.collect()
            yield None

class updater_task(rtos_task):
    """ implementation of the updater task """
    updater = None

    def task_init(self,param1):
        print("Init updater task")
        self.updater = OTAUpdater(GITHUB_HTTPS_ADDRESS)

    def task_body(self,param1):
        while True:
            print('Checking for update...')
            if self.updater.check_for_update_to_install_during_next_reboot()==True:
                machine.reset()
            yield None

def application(u_config): 
    gc.collect()

    if u_config['WIFI_CONF']:
        try:
            settime(int(u_config['UTC_OFS'])*60*60)
        except Exception as e:
            print("NTP sync failed:", e)

    u_config['VERSION'] = OTAUpdater(GITHUB_HTTPS_ADDRESS).get_version('main')

    # convert counters
    wakeup_period = int(u_config['WAKEUP_PERIOD'])*1000
    t1=task1(priority=2, param1=u_config)
    t2=updater_task(priority=1)
    task_list = [t1,t2]
    r = rtos(s_table=schedule_table, t_list=task_list )   # configure OS wih static configuration
    # timer 1 used to scheduled the first execution
    tim = machine.Timer(1)
    tim.init(period=10000, mode=machine.Timer.ONE_SHOT, callback=lambda t:r.scheduler_tick_call())
    # timer 0 used for rtos schedule
    tim = machine.Timer(0)
    tim.init(period=wakeup_period, mode=machine.Timer.PERIODIC, callback=lambda t:r.scheduler_tick_call())


    #print(r.task_list)
    try:
        r.start()       # start OS
    finally:
        tim.deinit()    # stop the timer
        r.stop()        # stop OS
    print("Close all")
