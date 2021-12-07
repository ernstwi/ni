from django.contrib.auth.middleware import RemoteUserMiddleware

class RemoteUserMiddlewareHTTP(RemoteUserMiddleware):
    header = 'HTTP_X_REMOTE_USER'
