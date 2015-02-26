hostFormats = {
    131: ['B', 'I', 'H'],  # "FIND AXES MINIMUMS",
    132: ['B', 'I', 'H'],  # "FIND AXES MAXIMUMS",
    133: ['I'],  # "DELAY",
    134: ['B'],  # CHANGE TOOL,
    135: ['B', 'H', 'H'],  # "WAIT FOR TOOL READY",
    136: ['B', 'B', 'B'],  # "TOOL ACTION COMMAND",
    137: ['B'],  # "ENABLE AXES",
    139: ['i', 'i', 'i', 'i', 'i', 'I'],  # "QUEUE EXTENDED POINT",
    140: ['i', 'i', 'i', 'i', 'i'],  # "SET EXTENDED POSITION",
    141: ['B', 'H', 'H'],  # "WAIT FOR PLATFORM READY",
    142: ['i', 'i', 'i', 'i', 'i', 'I', 'B'],  # "QUEUE EXTENDED POINT NEW",
    143: ['B'],  # "STORE HOME OFFSETS",
    144: ['B'],  # "RECALL HOME OFFSETS",
    145: ['B', 'B'],  # "SET POT VALUE",
    146: ['B', 'B', 'B', 'B', 'B'],  # "SET RGB LED",
    147: ['H', 'H', 'B'],  # "SET BEEP",
    148: ['B', 'H', 'B'],  # "WAIT FOR BUTTON",
    149: ['B', 'B', 'B', 'B', 's'],  # "DISPLAY MESSAGE",
    150: ['B', 'B'],  # "SET BUILD PERCENT",
    151: ['B'],  # "QUEUE SONG",
    152: ['B'],  # "RESET TO FACTORY",
    153: ['I', 's'],  # "BUILD START NOTIFICATION",
    154: ['B'],  # "BUILD END NOTIFICATION"
    155: ['i', 'i', 'i', 'i', 'i', 'I', 'B', 'f', 'h'],  # Queue Extended Point Accelerated
    157: ['B', 'B', 'B', 'I', 'H', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B'],
}
slaveFormats = {
    1: [],  # "INIT"
    3: ['h'],  # "SET TOOLHEAD TARGET TEMP",
    4: ['B'],
    6: ['I'],  # "SET MOTOR 1 SPED RPM",
    10: ['B'],  # "TOGGLE MOTOR 1",
    12: ['B'],  # "TOGGLE FAN",
    13: ['B'],  # "TOGGLE EXTRA OUTPUT",
    14: ['B'],  # "SET SERVO 1 POSITION",
    23: [],  # "PAUSE"
    24: [],  # "ABORT"
    31: ['h'],  # "SET PLATFORM TEMP",
}

structFormats = {
    'c': 1,
    'b': 1,  # Signed
    'B': 1,  # Unsigned
    '?': 1,
    'h': 2,  # Signed
    'H': 2,  # Unsigned
    'i': 4,  # Signed
    'I': 4,  # Unsigned
    'l': 8,  # Signed
    'L': 8,  # Unsigned
    'f': 4,
    'd': 8,
    's': -1,
}
