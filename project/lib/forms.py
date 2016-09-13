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


def get_one_form_error(form):
    """
    Use this if form validation failed and you just want to get the string for
    one error.
    """
    for field_name, error_messages in form.errors.iteritems():
        if error_messages:
            if len(form.fields) == 1:
                return "Error: {error}".format(
                    error=error_messages[0])
            else:
                return "Error: {field}: {error}".format(
                    field=form[field_name].label,
                    error=error_messages[0])

    return "Unknown error. If the problem persists, please contact the admins."


def get_one_formset_error(formset, get_form_name):
    for form in formset:
        for field_name, error_messages in form.errors.iteritems():
            if error_messages:
                if len(form.fields) == 1:
                    return "Error: {form} - {field}: {error}".format(
                        form=get_form_name(form),
                        field=form[field_name].label,
                        error=error_messages[0])
                else:
                    return "Error: {form}: {error}".format(
                        form=get_form_name(form),
                        error=error_messages[0])

    return "Unknown error. If the problem persists, please contact the admins."
