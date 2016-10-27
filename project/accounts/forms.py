from django.forms import Form, CharField, Textarea, TextInput


class EmailAllForm(Form):
    subject = CharField(
        label="Subject",
        widget=TextInput(attrs=dict(size=50)),
    )
    body = CharField(
        label="Body",
        widget=Textarea(attrs=dict(rows=20, cols=50)),
    )
