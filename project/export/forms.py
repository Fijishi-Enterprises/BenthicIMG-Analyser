from django.forms import Form
from django.forms.fields import CharField, ChoiceField, MultipleChoiceField
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect


class ExportAnnotationsForm(Form):
    optional_columns_choices = (
        ('annotator_info', "Annotator info"),
        ('machine_suggestions', "Machine suggestions"),
        ('metadata_date_aux', "Image metadata - date and auxiliary fields"),
        ('metadata_other', "Image metadata - other fields"),
    )
    optional_columns = MultipleChoiceField(
        widget=CheckboxSelectMultiple, choices=optional_columns_choices,
        required=False)


class CpcPrefsForm(Form):
    annotation_filter = None  # See __init__()
    local_image_dir = CharField(label="Folder with images", max_length=5000)
    local_code_filepath = CharField(label="Code file", max_length=5000)

    def __init__(self, *args, **kwargs):
        """
        When a non-Ajax view initializes this form, it's for display and user
        interaction. It should pass in a Source to
        1. initialize the CPCe environment values with the source's values, and
        2. show the source's confidence threshold in one of the field labels.

        When an Ajax view initializes this form, it's purely for processing
        submitted values. Passing a source is not needed.
        """
        if 'source' in kwargs:
            source = kwargs.pop('source')
            kwargs['initial'] = dict(
                local_image_dir=source.cpce_image_dir,
                local_code_filepath=source.cpce_code_filepath,
            )
        else:
            source = None

        super().__init__(*args, **kwargs)

        if source:
            confirmed_and_confident_label = (
                "Confirmed annotations AND Unconfirmed annotations"
                "\nabove the machine confidence threshold of {th}%").format(
                    th=source.confidence_threshold)
        else:
            # The field shouldn't even be visible in this case, but may as well
            # give a sensible label
            confirmed_and_confident_label = (
                "Confirmed annotations AND Unconfirmed annotations"
                "\nabove the machine confidence threshold")

        self.fields['annotation_filter'] = ChoiceField(
            choices=(
                ('confirmed_only', "Confirmed annotations only"),
                ('confirmed_and_confident', confirmed_and_confident_label),
            ),
            initial='confirmed_only',
            widget=RadioSelect,
        )

        # Specify fields' size attributes. This is done during init so that
        # we can modify existing widgets, thus avoiding having to manually
        # re-specify the widget class and attributes besides size.
        field_sizes = dict(
            local_image_dir=50,
            local_code_filepath=50,
        )
        for field_name, field_size in field_sizes.items():
            self.fields[field_name].widget.attrs['size'] = str(field_size)


class ExportImageStatsForm(Form):
    """Form for ImageStatsExportView."""
    label_display = ChoiceField(
        label="Label displays in column headers",
        choices=(
            ('code', "Short code"),
            ('name', "Full name"),
        ),
        initial='code',
        widget=RadioSelect,
    )


class ExportImageCoversForm(ExportImageStatsForm):
    pass
