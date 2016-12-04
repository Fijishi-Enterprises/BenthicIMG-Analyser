from labels.models import LocalLabel
from django import forms

class TreshForm(forms.Form):
    confidence_threshold = forms.IntegerField(min_value=0, max_value=100)    
    labelmode = forms.ChoiceField((('full', 'Labels'), ('func', 'Functional Groups')))
        
class CmTestForm(forms.Form):
    nlabels = forms.IntegerField(min_value=0, max_value=200)    
    namelength = forms.IntegerField(min_value=10, max_value=100)



