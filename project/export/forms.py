from django.forms import Form
from django.forms.fields import ChoiceField, MultipleChoiceField
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
