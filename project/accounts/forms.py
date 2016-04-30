from django.conf import settings
from django.contrib.auth.models import User
from django.forms import Form, CharField, Textarea, TextInput
from userena.forms import SignupForm
from userena.models import UserenaSignup

from .utils import send_activation_email_with_password

class UserAddForm(SignupForm):

    def __init__(self, *args, **kwargs):
        # The host name of the request; used for rendering activation emails.
        self.request_host = kwargs.pop('request_host')

        super(UserAddForm, self).__init__(*args, **kwargs)

        # The password will be auto-generated; no need for password fields.
        del self.fields['password1']
        del self.fields['password2']

    def clean(self):
        # Password field checking doesn't apply.
        pass

    def save(self):
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        password = User.objects.make_random_password(
            length=settings.MINIMUM_PASSWORD_LENGTH)

        new_user = UserenaSignup.objects.create_user(
            username, email, password, active=False, send_email=False)

        # Send the activation email. Include the generated password.
        userena_signup_obj = UserenaSignup.objects.get(user__username=username)
        send_activation_email_with_password(
            self.request_host, userena_signup_obj, password)

        return new_user


class EmailAllForm(Form):
    subject = CharField(
        label="Subject",
        widget=TextInput(attrs=dict(size=50)),
    )
    body = CharField(
        label="Body",
        widget=Textarea(attrs=dict(rows=20, cols=50)),
    )