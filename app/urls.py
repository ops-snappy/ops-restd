from handlers import base

url_patterns = [
        (r'/.*', base.AutoHandler),
]
