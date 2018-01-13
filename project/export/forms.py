from django.forms import Form
from django.forms.fields import CharField


class CpcPrefsForm(Form):
    local_image_dir = CharField(label="Folder with images", max_length=5000)
    local_code_filepath = CharField(label="Code file", max_length=5000)
