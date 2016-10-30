from django.contrib.auth import get_user_model
from django.contrib.auth.forms \
    import AuthenticationForm as DefaultAuthenticationForm
from django.core.validators import validate_email, ValidationError
from django.forms import Form
from django.forms.fields import CharField, EmailField
from django.forms.widgets import Textarea, TextInput
from registration.forms import RegistrationForm as DefaultRegistrationForm


class AuthenticationForm(DefaultAuthenticationForm):
    """
    Django's default authentication form pretty much does what we want,
    since we've set our own auth backend in the Django settings.
    However, our auth backend accepts username OR email in the first field,
    so we need to change some text accordingly.
    """
    error_messages = dict(
        invalid_login="The credentials you entered did not match our records."
                      " Note that both fields may be case-sensitive.",
        inactive="This account is inactive.",
    )

    def __init__(self, request=None, *args, **kwargs):
        super(AuthenticationForm, self).__init__(
            request=request, *args, **kwargs)

        # Set the label for the username field.
        # Although it's slightly inaccurate now, we'll keep the field name
        # as 'username' so we don't have to override too much code.
        self.fields['username'].label = "Username or Email"


class RegistrationForm(DefaultRegistrationForm):

    def clean_username(self):
        username = self.cleaned_data.get('username')
        User = get_user_model()

        # Ensure the username is unique case-insensitively.
        # Django model-fields specified as unique can only do this
        # case-sensitively, so we need to check on our own.
        try:
            # Is there a case-insensitive match?
            User.objects.get(username__iexact=username)
            # Raise the same error that the original form would've raised
            # if there were a case-sensitive match.
            raise ValidationError(
                User._meta.get_field('username').error_messages['unique'],
                code='unique')
        except User.DoesNotExist:
            # Username is not taken; no error
            pass

        # Ensure the username doesn't validate as an email address.
        # Since we allow sign-in with username or email, having a username
        # match an email can create ambiguity at sign-in.
        try:
            validate_email(username)
        except ValidationError:
            # Not a valid email address string. Carry on.
            pass
        else:
            # Valid email address string.
            raise ValidationError(
                "Your username can't be an email address."
                " Note that once you've registered, you'll be able to"
                " sign in with your username or your email address.",
                code='username_is_an_email')
        return username


class ActivationResendForm(Form):
    email = EmailField(
        label="Email address",
        required=True,
    )


class EmailChangeForm(Form):
    email = EmailField(
        label="New email address",
        required=True,
    )


class EmailAllForm(Form):
    subject = CharField(
        label="Subject",
        widget=TextInput(attrs=dict(size=50)),
    )
    body = CharField(
        label="Body",
        widget=Textarea(attrs=dict(rows=20, cols=50)),
    )
