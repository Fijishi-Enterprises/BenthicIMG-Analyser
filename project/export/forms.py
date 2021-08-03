from django.forms import Form
from django.forms.fields import (
    BooleanField, CharField, ChoiceField, MultipleChoiceField)
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect

from labels.utils import labelset_has_plus_code


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
    plus_notes = BooleanField(
        label="Support CPCe Notes codes using + as a separator",
        required=False,
    )

    def __init__(self, source, *args, **kwargs):
        kwargs['initial'] = dict(
            local_image_dir=source.cpce_image_dir,
            local_code_filepath=source.cpce_code_filepath,
            # Only check the plus notes option by default if the labelset
            # has codes with + in them. Otherwise, the user probably
            # didn't intend to use plus codes, and if there were any
            # previously-uploaded CPC files which contained Notes, those
            # Notes would be excluded from this export.
            plus_notes=(
                source.labelset and labelset_has_plus_code(source.labelset)),
        )

        super().__init__(*args, **kwargs)

        confirmed_and_confident_label = (
            "Confirmed annotations AND Unconfirmed annotations"
            "\nabove the machine confidence threshold of {th}%").format(
                th=source.confidence_threshold)

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

    export_format = ChoiceField(
        label="Export format",
        choices=(
            ('csv', "CSV"),
            ('excel',
             "Excel workbook with meta information"
             " (image search filters, etc.)"),
        ),
        initial='csv',
        widget=RadioSelect,
    )


class ExportImageCoversForm(ExportImageStatsForm):
    pass
