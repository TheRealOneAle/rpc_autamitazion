class PrefixMiddleware:
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix.rstrip('/') if prefix else ''

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        if self.prefix and path_info.startswith(self.prefix):
            environ['SCRIPT_NAME'] = self.prefix
            environ['PATH_INFO'] = path_info[len(self.prefix):]
        elif self.prefix and path_info == '/':
            environ['SCRIPT_NAME'] = self.prefix
        return self.app(environ, start_response)
