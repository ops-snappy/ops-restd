from halonrest.handlers import base

url_patterns = [
        (r'/.*', base.AutoHandler),
]
