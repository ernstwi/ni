from django.contrib.auth.backends import RemoteUserBackend

class RemoteUserBackendBlockUnknown(RemoteUserBackend):
    create_unknown_user = False
