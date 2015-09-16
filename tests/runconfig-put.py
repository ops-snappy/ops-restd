# NOTE: Run using Python3

import urllib, httplib2
import json
from pprint import pprint

'''
test script for saving a new DB configuration using REST.
json.data file contains the JSON of all ovsdb tables that
are to be saved to OVSDB
'''
with open('json.data') as data_file:
        _data = json.loads(data_file.read())
http = httplib2.Http()

_headers = { "Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
url = 'http://172.17.0.39:8091/rest/v1/system/full-configuration?type=running'

_headers = { "Content-type": "multipart/form-data", "Accept": "text/plain"}
response, content = http.request(url, 'PUT', headers=_headers, body=json.dumps(_data))
print(response)
print(content)
