from django.contrib.auth.middleware import RemoteUserMiddleware

class XRemoteUserMiddleware(RemoteUserMiddleware):
    header = 'HTTP_X_REMOTE_USER'
