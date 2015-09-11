from halonrest.handlers import base

url_patterns = [
        (r'/login', base.LoginHandler),
        (r'/.*', base.AutoHandler),
]
