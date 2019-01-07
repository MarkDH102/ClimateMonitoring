# ============================================================================
# Mechanism for defining constants
# ============================================================================
def constant(f):
    def fset(self, value):
        raise TypeError
    def fget(self):
        return f()
    return property(fget, fset)

class _Const(object):
    @constant
    def ATTIC_COLOUR():
        return "blue"
    @constant
    def HOUSE_COLOUR():
        return "yellow"
    @constant
    def SUMMERHOUSE_COLOUR():
        return "brown"
    @constant
    def CPU_COLOUR():
        return "green"
    @constant
    def LIGHT_COLOUR():
        return "orange"
    @constant
    def BACKGROUND_COLOUR():
        return "black"
    @constant
    def EMAIL_ADDRESS_TO_SEND_TO():
        return "youremail"
    @constant
    def EMAIL_ADDRESS_TO_SEND_FROM():
        return "youremail"
    @constant
    def FIRST_LEVEL_SHED_ALARM_VAL():
        return 25
    @constant
    def SECOND_LEVEL_SHED_ALARM_VAL():
        return 35
    @constant
    def BLUE():
        return 0
    @constant
    def RED():
        return 1
    @constant
    def GREEN():
        return 2
    @constant
    def YELLOW():
        return 3
    @constant
    def ORANGE():
        return 4
    @constant
    def BLACK():
        return 5
    @constant
    def WHITE():
        return 5
    @constant
    def TOUCHSCREEN_RESET():
        return 17
    @constant
    def WIRECLK():
        return 18
    @constant
    def WIRERESET():
        return 22
    @constant
    def WIREDATA():
        return 27
