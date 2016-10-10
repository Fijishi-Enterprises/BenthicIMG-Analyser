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


def get_one_form_error(form, include_field_name=True):
    """
    Use this if form validation failed and you just want to get the string for
    one error.
    """
    for field_name, error_messages in form.errors.iteritems():
        if error_messages:
            if not include_field_name:
                # Requested not to include the field name in the message
                return error_messages[0]
            elif field_name == '__all__':
                # Non-field error
                return error_messages[0]
            else:
                # Include the field name
                return "{field}: {error}".format(
                    field=form[field_name].label,
                    error=error_messages[0])

    # This function was called under the assumption that there was a
    # form error, but if we got here, then we couldn't find that form error.
    return "Unknown error. If the problem persists, please contact the admins."


def get_one_formset_error(formset, get_form_name, include_field_name=True):
    for form in formset:
        error_message = get_one_form_error(form, include_field_name)

        if not error_message.startswith("Unknown error"):
            # Found an error in this form
            return "{form}: {error}".format(
                form=get_form_name(form),
                error=error_message)

    for error_message in formset.non_form_errors():
        return error_message

    return "Unknown error. If the problem persists, please contact the admins."
