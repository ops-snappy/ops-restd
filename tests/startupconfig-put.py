# NOTE: run using Python3
import urllib, httplib2
import json
from pprint import pprint

'''
Test script to save a new startup configuration data into OVSDB.

json.data is a file containing the tables that are to be saved to DB.
'''


with open('json.data') as data_file:
        _data = json.loads(data_file.read())
http = httplib2.Http()

_headers = { "Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
url = 'http://172.17.0.9:8091/rest/v1/system/full-configuration?type=startup'

_headers = { "Content-type": "multipart/form-data", "Accept": "text/plain"}
response, content = http.request(url, 'PUT', headers=_headers, body=json.dumps(_data))
print(response)
print(content)
