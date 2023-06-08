import time
import machine
import gc

import utils


def inf(name_str):
    print(utils.datetime_to_iso_8601_str(machine.RTC().datetime()) + " INF  : " + str(gc.mem_free()) + ", " + str(name_str))


def wrn(name_str):
    print(utils.datetime_to_iso_8601_str(machine.RTC().datetime()) + " WRN  : " + str(gc.mem_free()) + ", " + str(name_str))

    
def err(name_str):
    print(utils.datetime_to_iso_8601_str(machine.RTC().datetime()) + " ERROR: " + str(gc.mem_free()) + ", " + str(name_str))