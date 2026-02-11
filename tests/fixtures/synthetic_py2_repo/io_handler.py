import sys


def report_error(message):
    text = "ERR: %s" % message
    print >> sys.stderr, text
