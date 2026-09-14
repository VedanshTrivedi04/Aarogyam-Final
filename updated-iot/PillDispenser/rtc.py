from machine import Pin, I2C

from config import (
    RTC_SDA,
    RTC_SCL,
    RTC_ADDRESS
)


# ============================================================
# I2C
# ============================================================

i2c = I2C(
    0,
    scl=Pin(RTC_SCL),
    sda=Pin(RTC_SDA),
    freq=100000
)


# ============================================================
# DS3231
# ============================================================

class DS3231:

    def __init__(
        self,
        i2c,
        address=0x68
    ):

        self.i2c = i2c
        self.address = address


    def bcd2dec(self, value):

        return (
            (value >> 4) * 10
            +
            (value & 0x0F)
        )


    def dec2bcd(self, value):

        return ((value // 10) << 4) | (value % 10)


    def now(self):

        data = self.i2c.readfrom_mem(
            self.address,
            0x00,
            7
        )

        second = self.bcd2dec(
            data[0] & 0x7F
        )

        minute = self.bcd2dec(
            data[1] & 0x7F
        )

        hour = self.bcd2dec(
            data[2] & 0x3F
        )

        day = self.bcd2dec(
            data[4] & 0x3F
        )

        month = self.bcd2dec(
            data[5] & 0x1F
        )

        year = (
            2000
            +
            self.bcd2dec(data[6])
        )

        return (
            year,
            month,
            day,
            hour,
            minute,
            second
        )


    def set_time(self, year, month, day, hour, minute, second):
        """
        Write year, month, day, hour, minute, second to DS3231 registers.
        """
        data = bytes([
            self.dec2bcd(second),
            self.dec2bcd(minute),
            self.dec2bcd(hour),
            self.dec2bcd(1),       # Day of week (1-7)
            self.dec2bcd(day),
            self.dec2bcd(month),
            self.dec2bcd(year - 2000 if year >= 2000 else year)
        ])

        self.i2c.writeto_mem(
            self.address,
            0x00,
            data
        )

        print("[RTC] Time synchronized: {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            year, month, day, hour, minute, second
        ))


    def get_iso(self):
        """Returns ISO-8601 string: YYYY-MM-DDTHH:MM:SS"""
        t = self.now()
        return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
            t[0], t[1], t[2], t[3], t[4], t[5]
        )


# ============================================================
# RTC OBJECT
# ============================================================

rtc = DS3231(
    i2c,
    RTC_ADDRESS
)


# ============================================================
# RTC CHECK
# ============================================================

def check_rtc():

    try:

        devices = i2c.scan()

        print("I2C Devices:", devices)

        if RTC_ADDRESS not in devices:

            print("RTC NOT FOUND")

            return False


        now = rtc.now()

        print(
            "RTC Date: {:02d}/{:02d}/{}".format(
                now[2],
                now[1],
                now[0]
            )
        )

        print(
            "RTC Time: {:02d}:{:02d}:{:02d}".format(
                now[3],
                now[4],
                now[5]
            )
        )

        return True


    except Exception as e:

        print("RTC ERROR:", e)

        return False