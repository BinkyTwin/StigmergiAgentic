import config


def describe(data):
    print "Model data", data
    if data.has_key("count"):
        return data.iteritems()
    return []
