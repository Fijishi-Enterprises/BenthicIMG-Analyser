from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.validators import validate_email, ValidationError

UserModel = get_user_model()


class UsernameOrEmailModelBackend(ModelBackend):
    """
    Like Django's default backend, but authentication accepts
    username OR email instead of just username.

    The authentication implementation is pretty similar to that of
    userena's auth backend.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):

        # The default authentication form just passes the first field as
        # 'username', but we'll interpret it as username or email.
        username_or_email = username

        try:
            validate_email(username_or_email)
            # Valid email address string, so we'll interpret it as an email.
            try:
                # Check against database emails case-sensitively. We allow
                # case-sensitive email distinction because some
                # email domains support that (unfortunately).
                # http://stackoverflow.com/questions/9807909/
                user = UserModel.objects.get(email=username_or_email)
            except UserModel.DoesNotExist:
                user = None
        except ValidationError:
            # Not a valid email address string, so we'll interpret it as
            # a username.
            # In order for this to not have any possibility for weird
            # behavior, users shouldn't be allowed to register usernames
            # that validate as email address strings.
            try:
                # Check against database usernames case-insensitively. We
                # don't allow case-sensitive username distinction because it
                # can cause confusion when usernames are displayed on the site.
                user = UserModel.objects.get(
                    username__iexact=username_or_email)
            except UserModel.DoesNotExist:
                user = None

        if user is not None:
            # If the password is good for this user, return the user.
            if user.check_password(password):
                return user
        else:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user.
            # Django's default backend does this too.
            UserModel().set_password(password)
