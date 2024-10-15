from .cryovacTIC500 import CryovacTIC500


def main():
    import sys
    import tango.server

    args = ["cryovacTIC500"] + sys.argv[1:]
    tango.server.run((CryovacTIC500,), args=args)