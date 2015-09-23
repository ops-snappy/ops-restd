# NOTE: run using Python3
import urllib, httplib2
import json

'''
Test script to GET running configuration of OVSDB.
'''
http = httplib2.Http()

_headers = { "Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
# GET to fetch system info from the DB
url = 'http://172.17.0.39:8091/rest/v1/system/full-configuration?type=running'
response, content = http.request(url, 'GET', headers=_headers)
print(response)
print(content)
