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
from PIL import Image, ImageChops
import logging

import serial


class _GU7000():

    def __init__(self, port, baudrate, width=140, height=32):
        self.flash_buffer_every_bytes = 4
        self.port = port
        self.baudrate = baudrate
        self.serial = serial.Serial(rtscts=False)
        # self.serial.write_timeout = 0
        # self.serial.inter_byte_timeout = 0
        self.width = width
        self.height = height

    def open(self):
        self.serial.baudrate = self.baudrate
        self.serial.port = self.port
        self.serial.open()

    def close(self):
        if self.serial.is_open == True:
            self.serial.close()

    def chunkData(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def write_data(self, data):
        # self.serial.write(data)
        for x in list(self.chunkData(data, self.flash_buffer_every_bytes)):
            while not self.serial.cts:
                pass
            self.serial.write(x)
            while not self.serial.cts:
                pass
            self.serial.flushOutput()

    def set_brightness(self, brightness):
        b = chr(max(int(min(brightness * 8, 8)), 1))
        packet = bytearray(b"\x1F\x58")
        packet.append(b)
        self.write_data(packet)

    def reset(self):
        self.write_data(b"\x1B\x40")

    def move_cursor(self, x, y):
        y = y / 8
        packet = bytearray(b"\x1F\x24")
        packet.append(chr(int(x) % 0x100))
        packet.append(int(x) / int(0x100))
        packet.append(chr(int(y) % 0x100))
        packet.append(int(y) / int(0x100))
        self.write_data(packet)

    def scroll(self, x, y, times, speed):
        pos = (x * self.height / 8) + (y / 8)
        packet = bytearray(b"\x1F\x28\x61\x10")
        packet.append(chr(int(pos) % 0x100))
        packet.append(int(pos) / int(0x100))
        packet.append(chr(int(times) % 0x100))
        packet.append(int(times) / int(0x100))
        packet.append(chr(speed))
        self.write_data(packet)

    def show_raw_image(self, image, imgWidth, imgHeight):
        imgWidth = int(imgWidth)
        imgHeight = int(imgHeight)
        packet = bytearray(b"\x1F\x28\x66\x11")
        packet.append(chr(imgWidth % 0x100))
        packet.append(imgWidth / int(0x100))
        packet.append(chr(imgHeight % 0x100))
        packet.append(imgHeight / int(0x100))
        packet.append(0x1)
        packet = packet + image
        self.write_data(packet)

    def show_pil_image(self, image, imgWidth, imgHeight):
        image_data = image.getdata()
        buf = bytearray(imgWidth * imgHeight / 8)
        threshold = 1
        for x in range(0, imgWidth):
            for y in range(0, imgHeight / 8):
                val = 0
                for i in range(0, 8):
                    val = (1 if i == 0 else (val + 1)) if image_data[ x + (y * 8 + i) * imgWidth] >= threshold else val
                    if i < 7:
                        val = val + val
                buf[x * (imgHeight / 8) + y] = val
        self.show_raw_image(buf, imgWidth=imgWidth, imgHeight=imgHeight / 8)

    def sleep(self):
        self.write_data(b"\x1F\x28\x61\x40\x00")

    def wakeup(self):
        self.write_data(b"\x1F\x28\x61\x40\x01")

    def clear_display(self):
        self.write_data(b"\x0C")

    def delayMicroseconds(self, microseconds):
        seconds = microseconds / 1000000.0  # divide microseconds by 1 million for seconds
        time.sleep(seconds)



class gu7000():

    def __init__(self, rows=32, cols=140, port='/dev/ttyAMA0', baudrate=115200):
        self.screensaverDelay = 60.0
        self.firstEmptyFrameDate = None
        self.emptyFrameCounter = 0
        self.isScreenSaverActive = False

        self.previousFrame = None
        self.port = port
        self.baudrate = baudrate

        self.rows = rows
        self.cols = cols

        self.fb = [[]]

        #Initialize the default font
        font = fonts.bmfont.bmfont('latin1_5x8_fixed.fnt')
        self.fp = font.fontpkg

        self.device = _GU7000(port=self.port, baudrate=self.baudrate, width=self.cols, height=self.rows)
        self.device.open()
        self.device.reset()
        self.device.clear_display()
        self.device.move_cursor(0, 0)
        self.device.set_brightness(0.5)

    def clear(self):
        self.device.clear_display()

    def message(self, text, row=0, col=0, varwidth=True):
        ''' Send string to LCD. Newline wraps to second line'''

        if row >= self.rows or col >= self.cols:
            raise IndexError

        textwidget = display.gwidgetText(text, self.fp, {}, [], varwidth)
        self.update(textwidget.image)

    def isPILImageEmpty(self, image):
        data = image.getdata()
        for i in range(0, len(data)):
            if data[i] != 0:
                return False
        return True

    def disable_screensaver(self):
        if self.isScreenSaverActive:
            self.device.wakeup()
        self.emptyFrameCounter = 0
        self.firstEmptyFrameDate = None
        self.isScreenSaverActive = False

    def update(self, image):
        newFrame = image.crop((0, 0, self.cols, self.rows))

        if self.previousFrame is not None:
            diff_image = ImageChops.logical_xor(newFrame, self.previousFrame)

            diff_data = diff_image.getdata()
            start_y = 0
            end_y = 0
            for i in range(0, len(diff_data)):
                if diff_data[i] != 0:
                    start_y = int(i) / int(self.cols)
                    break
            if start_y != 0:
                for i in reversed(range(0, len(diff_data))):
                    if diff_data[i] != 0:
                        end_y = int(i) / int(self.cols)
                        break
                if start_y != 0 and end_y != 0:
                    start_y = int(round(float(start_y) / 8)) * 8
                    self.previousFrame = newFrame
                    if ((end_y-start_y) % 8 !=0):
                        end_y = start_y + (8 * int(math.ceil(float(end_y-start_y) / float(8))))
                    diff_image = newFrame.crop((0, start_y, self.cols, end_y))
                    self.device.move_cursor(0, start_y)
                    self.device.show_pil_image(diff_image, self.cols, diff_image.size[1])

                    self.disable_screensaver()
                    return
            else:
                if self.emptyFrameCounter > 0:
                    self.emptyFrameCounter = self.emptyFrameCounter + 1
                    if self.firstEmptyFrameDate is not None and (time.time() - self.firstEmptyFrameDate) >= self.screensaverDelay:
                        if not self.isScreenSaverActive:
                            self.device.sleep()
                            self.isScreenSaverActive = True
                    return
                elif self.emptyFrameCounter == 0 and self.isPILImageEmpty(newFrame):
                    self.firstEmptyFrameDate = time.time()
                    self.emptyFrameCounter = self.emptyFrameCounter + 1
                    return

        self.disable_screensaver()

        self.device.move_cursor(0, 0)
        self.device.show_pil_image(newFrame, self.cols, self.rows)
        self.previousFrame = newFrame

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
