from django.forms import Form
from django.forms.fields import CharField, IntegerField


class CpcPrefsForm(Form):
    local_image_dir = CharField(label="Folder with images", max_length=5000)
    local_code_filepath = CharField(label="Code file", max_length=5000)
    # TODO: Figure out what are the minimum width/height considered valid
    # in CPCe
    display_width = IntegerField(label="Image display width (pixels)")
    display_height = IntegerField(label="Image display height (pixels)")
