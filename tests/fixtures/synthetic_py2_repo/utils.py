def to_pairs(data):
    items = []
    for key, value in data.iteritems():
        items.append((key, value))

    if data.has_key("active"):
        return items
    return []
