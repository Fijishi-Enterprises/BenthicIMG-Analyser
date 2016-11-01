from labels.models import LocalLabel
from django import forms

class TreshForm(forms.Form):
    confidence_threshold = forms.IntegerField(min_value=0, max_value=100)    
    labelmode = forms.ChoiceField((('full', 'Labels'), ('func', 'Functional Groups')))
        



