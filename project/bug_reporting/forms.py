from django.forms import ModelForm
from bug_reporting.models import Feedback

class FeedbackForm(ModelForm):
    class Meta:
        model = Feedback
        fields = ['type', 'comment']