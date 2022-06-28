from django.contrib.auth.backends import RemoteUserBackend

class XRemoteUserBackend(RemoteUserBackend):
    create_unknown_user = False
