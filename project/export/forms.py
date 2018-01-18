from django.forms import Form
from django.forms.fields import CharField


class CpcPrefsForm(Form):
    local_image_dir = CharField(label="Folder with images", max_length=5000)
    local_code_filepath = CharField(label="Code file", max_length=5000)

    def __init__(self, *args, **kwargs):
        """
        When a page initializes this form for display, it should pass in a
        Source to fill the form fields' initial values
        with the source's CPCe preference values.
        When a page initializes this form for processing, passing a source
        is not needed.
        """
        if kwargs.has_key('source'):
            source = kwargs.pop('source')
            kwargs['initial'] = dict(
                local_image_dir=source.cpce_image_dir,
                local_code_filepath=source.cpce_code_filepath,
            )

        super(CpcPrefsForm, self).__init__(*args, **kwargs)

        # Specify fields' size attributes. This is done during init so that
        # we can modify existing widgets, thus avoiding having to manually
        # re-specify the widget class and attributes besides size.
        field_sizes = dict(
            local_image_dir=50,
            local_code_filepath=50,
        )
        for field_name, field_size in field_sizes.items():
            self.fields[field_name].widget.attrs['size'] = str(field_size)
