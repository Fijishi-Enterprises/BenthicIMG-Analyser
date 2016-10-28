from django.forms import Form
from django.forms.fields import CharField, EmailField
from django.forms.widgets import Textarea, TextInput


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
