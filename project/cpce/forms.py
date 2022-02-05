from django.core.exceptions import ValidationError
from django.forms import Form
from django.forms.fields import BooleanField, CharField, ChoiceField
from django.forms.widgets import RadioSelect

from upload.forms import MultipleFileField, MultipleFileInput
from upload.utils import text_file_to_unicode_stream
from .utils import labelset_has_plus_code


class CpcImportForm(Form):
    cpc_files = MultipleFileField(
        label='CPC files',
        # Multi-file input whose dialog only allows selecting .cpc
        widget=MultipleFileInput(attrs=dict(accept='.cpc')),
        error_messages=dict(required="Please select one or more CPC files."),
    )
    plus_notes = BooleanField(
        label="Support CPCe Notes codes using + as a separator",
        required=False,
    )

    def __init__(self, source, *args, **kwargs):
        kwargs['initial'] = dict(
            # Only check the plus notes option by default if the labelset
            # has codes with + in them. Otherwise, the uploader probably
            # didn't intend to use plus codes, and any Notes present in the
            # CPC files would make the upload fail.
            plus_notes=(
                source.labelset and labelset_has_plus_code(source.labelset)),
        )
        super().__init__(*args, **kwargs)

    def clean_cpc_files(self):
        """
        Check for extensions of .cpc. This isn't foolproof, but it can
        catch simple file selection mistakes.
        """
        cpc_files = self.cleaned_data['cpc_files']

        for cpc_file in cpc_files:
            if not cpc_file.name.endswith('.cpc'):
                raise ValidationError(
                    "This is not a CPC file: {fn}".format(fn=cpc_file.name))

        return self.cleaned_data['cpc_files']

    def get_cpc_names_and_streams(self):
        cpc_names_and_streams = []
        for cpc_file in self.cleaned_data['cpc_files']:
            cpc_unicode_stream = text_file_to_unicode_stream(cpc_file)
            cpc_names_and_streams.append((cpc_file.name, cpc_unicode_stream))
        return cpc_names_and_streams


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
