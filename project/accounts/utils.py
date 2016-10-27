from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

def get_imported_user():
    return User.objects.get(username=settings.IMPORTED_USERNAME)
def get_robot_user():
    return User.objects.get(username=settings.ROBOT_USERNAME)
def get_alleviate_user():
    return User.objects.get(username=settings.ALLEVIATE_USERNAME)

def is_imported_user(user):
    return user.username == settings.IMPORTED_USERNAME
def is_robot_user(user):
    return user.username == settings.ROBOT_USERNAME
def is_alleviate_user(user):
    return user.username == settings.ALLEVIATE_USERNAME
