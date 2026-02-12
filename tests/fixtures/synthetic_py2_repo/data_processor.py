import sys


def process(data):
    output = []
    for key, value in data.iteritems():
        output.append((key, value))

    for index in xrange(2):
        print >> sys.stderr, "idx=%s" % index

    if data.has_key("path"):
        execfile(data["path"])

    return output
