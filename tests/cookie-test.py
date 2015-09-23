import urllib, httplib2
import json

'''
A simple test script to test authentication using the 'userauth' module.
This is a 2 step test.

Step 1: POST to /login to send username/password combination to fetch the secret cookie.
step 2: Use the secret cookie to use authenticated session to GET /system information from the database.
'''

# POST to fetch cookie
http = httplib2.Http()
url = 'http://172.17.0.10:8091/login'
body = {'username' : 'root', 'password' : ''}
headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
response, content = http.request(url, 'POST', headers=headers, body=urllib.parse.urlencode(body))
print(response)
print(content)

# set the cookie header before doing a GET
headers = {'Cookie' : response['set-cookie']}

# GET to fetch system info from the DB
url = 'http://172.17.0.10:8091/rest/v1/system'
response, content = http.request(url, 'GET', headers=headers)
print(response)
print(content)
