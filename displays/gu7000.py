#!/usr/bin/python
# coding: UTF-8

# Driver for NoritakeGU7000 VFD display connected thru UART with CTS enabled
# Written by: Ivan Isaev
#


from __future__ import unicode_literals

import time, math, logging
import lcd_display_driver
import fonts
import graphics as g
from PIL import Image
import logging

import serial


class _GU7000():

    def __init__(self, port, baudrate, width=140, height=32):
        self.port = port
        self.baudrate = baudrate
        self.serial = serial.Serial(rtscts=True)
        self.width = width
        self.height = height

    def open(self):
        self.serial.baudrate = self.baudrate
        self.serial.port = self.port
        self.serial.open()

    def close(self):
        if self.serial.is_open == True:
            self.serial.close()

    def write_data(self, data):
        # self.serial.setRTS(True)
        # while not self.serial.getCTS():
        #     pass
        self.serial.write(data)
        # time.sleep(0.25)  # Wait for the data to have sent before disabling RTS
        # self.serial.setRTS(False)

    def set_brightness(self, brightness):
        b = chr(max(int(min(brightness * 8, 8)), 1))
        packet = bytearray(b"\x1F\x58")
        packet.append(b)
        self.write_data(packet)

    def move_cursor(self, x, y):
        packet = bytearray(b"\x1F\x24")
        packet.append(chr(int(x) % 0x100))
        packet.append(int(x) / int(0x100))
        packet.append(chr(int(y) % 0x100))
        packet.append(int(y) / int(0x100))
        self.write_data(packet)

    def show_raw_image(self, image, width=0, height=0):
        width = int(width)
        height = int(height)
        packet = bytearray(b"\x1F\x28\x66\x11")
        packet.append(chr(width % 0x100))
        packet.append(width / int(0x100))
        packet.append(chr(height % 0x100))
        packet.append(height / int(0x100))
        packet.append(0x1)
        packet = packet + image
        self.write_data(packet)
        # print(''.join('{:02x}'.format(x) for x in packet))

    #Straight from https://github.com/rm-hull/luma.oled/blob/master/luma/oled/device/__init__.py
    def show_pil_image(self, image):
        """
        Takes a 1-bit :py:mod:`PIL.Image` and dumps it to the SH1106
        OLED display.
        :param image: Image to display.
        :type image: :py:mod:`PIL.Image`
        """
        # assert (image.mode == self.mode)
        # assert (image.size == self.size)
        #
        # image = self.preprocess(image)

        image_data = image.getdata()
        buf = bytearray(self.width * self.height)

        for y in range(0, self.height):
            y_off = self.width * y
            for x in range(self.width):
                buf[x] = \
                    (image_data[x + y_off] and 0x01) | \
                    (image_data[x + y_off] and 0x02) | \
                    (image_data[x + y_off] and 0x04) | \
                    (image_data[x + y_off] and 0x08) | \
                    (image_data[x + y_off] and 0x10) | \
                    (image_data[x + y_off] and 0x20) | \
                    (image_data[x + y_off] and 0x40) | \
                    (image_data[x + y_off] and 0x80)
        self.show_raw_image(buf, width=self.width, height=self.height / 8)

    def clear_display(self):
        self.write_data(b"\x0C")

    def delayMicroseconds(self, microseconds):
        seconds = microseconds / 1000000.0  # divide microseconds by 1 million for seconds
        time.sleep(seconds)


class gu7000():

    def __init__(self, rows=32, cols=140, port='/dev/ttyAMA0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate

        self.rows = rows
        self.cols = cols

        self.fb = [[]]

        # Initialize the default font
        font = fonts.bmfont.bmfont('latin1_5x8_fixed.fnt')
        self.fp = font.fontpkg


        self.device = _GU7000(port=self.port, baudrate=self.baudrate, width=self.cols, height=self.rows)
        self.device.open()

    def clear(self):
        self.device.clear_display()

    def message(self, text, row=0, col=0, varwidth=True):
        ''' Send string to LCD. Newline wraps to second line'''

        if row >= self.rows or col >= self.cols:
            raise IndexError

        textwidget = display.gwidgetText(text, self.fp, {}, [], varwidth)
        self.update(textwidget.image)

    def update(self, image):
        retry = 5

        # Make image the same size as the display
        img = image.crop((0, 0, self.cols, self.rows))

        while retry:
            # send to display
            try:
                self.device.show_pil_image()
                break
            except IOError:
                retry -= 1

    def msgtest(self, text, wait=1.5):
        self.clear()
        self.message(text)
        time.sleep(wait)


if __name__ == '__main__':
    import getopt, sys, os
    import graphics as g
    import fonts
    import display
    import moment


    def processevent(events, starttime, prepost, db, dbp):
        for evnt in events:
            t, var, val = evnt

            if time.time() - starttime >= t:
                if prepost in ['pre']:
                    db[var] = val
                elif prepost in ['post']:
                    dbp[var] = val


    logging.basicConfig(format=u'%(asctime)s:%(levelname)s:%(message)s', handlers=[logging.StreamHandler()],
                        level=logging.DEBUG)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hr:c:", ["row=", "col=", "port=", "baudrate="])
    except getopt.GetoptError:
        print
        'gu7000.py -r <rows> -c <cols> --port <port> --baudrate <baudrate>'
        sys.exit(2)

    # Set defaults
    rows = 32
    cols = 140
    port = '/dev/ttyAMA0'
    baudrate = 115200

    for opt, arg in opts:
        if opt == '-h':
            print
            'gu7000.py -r <rows> -c <cols> --port <port> --baudrate <baudrate>'
            sys.exit()
        elif opt in ("-r", "--rows"):
            rows = int(arg)
        elif opt in ("-c", "--cols"):
            cols = int(arg)
        elif opt in ("--baudrate"):
            baudrate = int(baudrate)
        elif opt in ("--port"):
            port = arg

    db = {
        'actPlayer': 'mpd',
        'playlist_position': 1,
        'playlist_length': 5,
        'title': "Nicotine & Gravy",
        'artist': "Beck",
        'album': 'Midnight Vultures',
        'tracktype': 'MP3 Stereo 24 bit 44.1 Khz',
        'bitdepth': '16 bits',
        'samplerate': '44.1 kHz',
        'elapsed': 0,
        'length': 400,
        'volume': 50,
        'stream': 'Not webradio',
        'utc': moment.utcnow(),
        'outside_temp_formatted': '46\xb0F',
        'outside_temp_max': 72,
        'outside_temp_min': 48,
        'outside_conditions': 'Windy',
        'system_temp_formatted': '98\xb0C',
        'state': 'stop',
        'system_tempc': 81.0
    }

    dbp = {
        'actPlayer': 'mpd',
        'playlist_position': 1,
        'playlist_length': 5,
        'title': "Nicotine & Gravy",
        'artist': "Beck",
        'album': 'Midnight Vultures',
        'tracktype': 'MP3 Stereo 24 bit 44.1 Khz',
        'bitdepth': '16 bits',
        'samplerate': '44.1 kHz',
        'elapsed': 0,
        'length': 400,
        'volume': 50,
        'stream': 'Not webradio',
        'utc': moment.utcnow(),
        'outside_temp_formatted': '46\xb0F',
        'outside_temp_max': 72,
        'outside_temp_min': 48,
        'outside_conditions': 'Windy',
        'system_temp_formatted': '98\xb0C',
        'state': 'stop',
        'system_tempc': 81.0
    }

    events = [
        (15, 'state', 'play'),
        (20, 'title', 'Mixed Bizness'),
        (30, 'volume', 80),
        (40, 'title', 'I Never Loved a Man (The Way I Love You)'),
        (40, 'artist', 'Aretha Franklin'),
        (40, 'album', 'The Queen Of Soul'),
        (70, 'state', 'stop'),
        (90, 'state', 'play'),
        (100, 'title', 'Do Right Woman, Do Right Man'),
        (120, 'volume', 100),
        (140, 'state', 'play')
    ]

    try:
        print
        "GU7000 VFD Display Test"
        print
        "ROWS={0}, COLS={1}, PORT={2}, BAUDRATE={3}".format(rows, cols, port, baudrate)

        lcd = gu7000(rows, cols, port, baudrate)
        lcd.clear()
        lcd.message("pydPiper\nStarting", 0, 0, True)
        time.sleep(2)
        lcd.clear()

        starttime = time.time()
        elapsed = int(time.time() - starttime)
        timepos = time.strftime(u"%-M:%S", time.gmtime(int(elapsed))) + "/" + time.strftime(u"%-M:%S",
                                                                                            time.gmtime(int(254)))

        dc = display.display_controller((cols, rows))
        f_path = os.path.join(os.path.dirname(__file__), '../pages_gu7000.py')
        dc.load(f_path, db, dbp)

        starttime = time.time()
        while True:
            elapsed = int(time.time() - starttime)
            db['elapsed'] = elapsed
            db['utc'] = moment.utcnow()
            processevent(events, starttime, 'pre', db, dbp)
            img = dc.next()
            processevent(events, starttime, 'post', db, dbp)
            lcd.update(img)
            time.sleep(.001)


    except KeyboardInterrupt:
        pass

    finally:
        lcd.clear()
        lcd.message("Goodbye!", 0, 0, True)
        time.sleep(2)
        lcd.clear()
        print
        "GU7000 VFD Display Test Complete"
