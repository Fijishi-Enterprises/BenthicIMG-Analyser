from django.forms import ModelForm
from bug_reporting.models import Feedback
from lib.forms import strip_spaces_from_fields

class FeedbackForm(ModelForm):
    class Meta:
        model = Feedback
        fields = ['type', 'comment']

    def clean(self):
        """
        1. Strip spaces from character fields.
        2. Call the parent's clean() to finish up with the default behavior.
        """

        data = strip_spaces_from_fields(
            self.cleaned_data, self.fields)

        self.cleaned_data = data

        super(FeedbackForm, self).clean()