from django import forms


class ContactForm(forms.Form):
    """
    Allows a user to send a general email to the site admins.
    """
    email = forms.EmailField(
        label='Your email address',
        help_text="Enter your email address so we can reply to you.",
    )
    subject = forms.CharField(
        label='Subject',
        # Total length of the subject (including any auto-added prefix)
        # should try not to exceed 78 characters.
        # http://stackoverflow.com/questions/1592291/
        max_length=55,
    )
    message = forms.CharField(
        label='Message/Body',
        max_length=5000,
        widget=forms.Textarea(
            attrs={'class': 'large'},
        ),
    )

    def __init__(self, user, *args, **kwargs):
        super(ContactForm, self).__init__(*args, **kwargs)
        if user.is_authenticated():
            del self.fields['email']