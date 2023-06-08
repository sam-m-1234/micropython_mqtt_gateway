import logging as log


def zfl(s, width):
    # Pads the provided string with leading 0's to suit the specified 'chrs' length
    # Force # characters, fill with leading 0's
    return '{:0>{w}}'.format(str(s), w=width)


def datetime_to_iso_8601_str(dt):
    yyyy = zfl(dt[0], 4)
    mm = zfl(dt[1], 2)
    dd = zfl(dt[2], 2)
    HH = zfl(dt[4], 2)
    MM = zfl(dt[5], 2)
    SS = zfl(dt[6], 2)
    #ss = zfl(dt[7], 6)
    return f'{yyyy}-{mm}-{dd}T{HH}:{MM}:{SS}'#.{ss}'


def datetime_to_compressed_str(dt):
    yyyy = zfl(dt[0], 4)
    mm = zfl(dt[1], 2)
    dd = zfl(dt[2], 2)
    HH = zfl(dt[4], 2)
    MM = zfl(dt[5], 2)
    SS = zfl(dt[6], 2)
    #ss = zfl(dt[7], 6)
    return f'{yyyy}{mm}{dd}{HH}{MM}{SS}'#.{ss}'


def check_exists(path):
    try:
        f = open(path, "r")
        f.close()
        return 1
    except OSError:  # open failed
       return 0


def load_file(path):
    with open(path, 'rb') as f:
        return f.read()
