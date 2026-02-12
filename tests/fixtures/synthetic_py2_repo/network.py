import urllib2


def fetch(url):
    response = urllib2.urlopen(url)
    return response.read()
