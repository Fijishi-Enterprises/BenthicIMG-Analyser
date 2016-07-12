from django import forms
from django.core.exceptions import ValidationError
from django.forms import ImageField, Form, ChoiceField, FileField, CharField
from django.forms.widgets import FileInput
from django.utils.translation import ugettext_lazy as _
from images.utils import get_aux_metadata_max_length, get_num_aux_fields, get_aux_label, get_aux_labels, get_aux_field_name
from upload.utils import metadata_to_filename
from images.models import Source, Metadata


class MultipleFileInput(FileInput):
    """
    Modifies the built-in FileInput widget by allowing validation of multi-file input.
    (When FileInput takes multiple files, it only validates the last one.)
    """
    def __init__(self, attrs=None):
        # Include the attr multiple = 'multiple' by default.
        # (For reference, TextArea.__init__ adds default attrs in the same way.)
        default_attrs = {'multiple': 'multiple'}
        if attrs is not None:
            default_attrs.update(attrs)
        super(MultipleFileInput, self).__init__(attrs=default_attrs)

    def value_from_datadict(self, data, files, name):
        """
        FileInput's method only uses get() here, which means only 1 file is gotten.
        We need getlist to get all the files.
        """
        if not files:
            # files is the empty dict {} instead of a MultiValueDict.
            # That will happen if the files parameter passed into the
            # form is an empty MultiValueDict, because Field.__init__()
            # has the code 'self.files = files or {}'.
            return []
        else:
            # In any other case, we'll have a MultiValueDict, which has
            # the method getlist() to get the values as a list.
            return files.getlist(name)


class MultipleImageField(ImageField):
    """
    Modifies the built-in ImageField by allowing validation of multi-file input.
    (When ImageField takes multiple files, it only validates the last one.)

    Must be used with the MultipleFileInput widget.
    """

    def to_python(self, data):
        """
        Checks that each file of the file-upload field data contains a valid
        image (GIF, JPG, PNG, possibly others -- whatever the Python Imaging
        Library supports).
        """
        data_out = []

        for list_item in data:
            try:
                f = super(MultipleImageField, self).to_python(list_item)
            except ValidationError, err:
                raise ValidationError(err.messages[0])
            data_out.append(f)

        return data_out


class MultiImageUploadForm(Form):
    """
    Takes multiple image files.

    This is used only for the frontend of the image upload form.
    """
    files = MultipleImageField(
        label='Image files',
        widget=MultipleFileInput(),
    )

    def __init__(self, *args, **kwargs):
        """
        - Add extra_help_text to the file field.
        """
        super(MultiImageUploadForm, self).__init__(*args, **kwargs)

        # This field's help text will go in a separate template, which
        # can be displayed in a modal dialog.
        self.fields['files'].dialog_help_text_template = \
            'upload/help_image_files.html'


class ImageUploadForm(Form):
    """
    Takes a single image file.

    This is used only for the backend of the image upload form.
    """
    file = ImageField(
        label='Image file',
        widget=FileInput(),
        error_messages={
            'invalid_image': _(u"The file is either a corrupt image, or in a file format that we don't support."),
        },
    )

# Remnants of an attempt at a progress bar...

# Upload id field for tracking the upload progress.
#
# Might need to ensure the input element's name is X-Progress-ID in
# order to get this working with UploadProgressCacheHandler, which
# demands that exact name.  Not sure where UPCH got that name came
# from, but it might have something to do with nginx.
#
# Is it even necessary to have this upload id in the form class?
# It seems that UploadProgressCachedHandler.handle_raw_input() looks
# for the upload id as a GET parameter only (and Django fields are only
# needed for POST parameters).
# http://www.laurentluce.com/posts/upload-to-django-with-progress-bar-using-ajax-and-jquery/#comment-1192

#    ajax_upload_id = CharField(
#        label='',
#        widget=HiddenInput(),
#    )


class ImageUploadOptionsForm(Form):
    """
    Helper form for the ImageUploadForm.
    """

    specify_metadata = ChoiceField(
        label='Specify image metadata',
        help_text='',  # To be filled in by the form's __init__()
        choices=(
            ('after', 'Later (after upload)'),
            ('filenames', 'In the image filenames'),
            ('csv', 'From a CSV file')
        ),
        initial='after',
        required=True
    )

    def __init__(self, *args, **kwargs):

        source = kwargs.pop('source')
        super(ImageUploadOptionsForm, self).__init__(*args, **kwargs)

        # Dynamically generate a source-specific string for the metadata
        # field's help text.
        filename_format_args = dict(year='YYYY', month='MM', day='DD')
        source_keys = get_aux_labels(source)
        filename_format_args['values'] = source_keys

        self.fields['specify_metadata'].source_specific_filename_format =\
        metadata_to_filename(**filename_format_args)

        # This field's help text will go in a separate template, which
        # can be displayed in a modal dialog.
        self.fields['specify_metadata'].dialog_help_text_template = \
            'upload/help_specify_metadata.html'


class AnnotationImportForm(Form):
    annotations_file = FileField(
        label='Points/Annotations file (.txt)',
    )

    def __init__(self, *args, **kwargs):
        """
        Add extra_help_text to the file field.
        """
        super(AnnotationImportForm, self).__init__(*args, **kwargs)

        # This field's help text will go in a separate template, which
        # can be displayed in a modal dialog.
        self.fields['annotations_file'].dialog_help_text_template = \
            'upload/help_annotations_file.html'

    def clean_annotations_file(self):
        anno_file = self.cleaned_data['annotations_file']

        # Naively validate that the file is a text file through
        # (1) given MIME type, or (2) file extension.  Either of them
        # can be faked though.
        #
        # For the file extension check, would be more "correct" to use:
        # mimetypes.guess_type(csv_file.name).startswith('text/')
        # but the mimetypes module doesn't recognize csv for
        # some reason.
        if anno_file.content_type.startswith('text/'):
            pass
        elif anno_file.name.endswith('.txt'):
            pass
        else:
            raise ValidationError("This file is not a plain text file.")

        return self.cleaned_data['annotations_file']


class AnnotationImportOptionsForm(Form):
    """
    Helper form for the AnnotationImportForm, containing import options.
    """
    is_uploading_points_or_annotations = forms.fields.BooleanField(
        required=False,
    )

    is_uploading_annotations_not_just_points = ChoiceField(
        label='Data',
        choices=(
            ('yes', "Points and annotations"),
            ('no', "Points only"),
        ),
        initial='yes',
    )

    def __init__(self, *args, **kwargs):
        """
        Add extra_help_text to the file field.
        """
        source = kwargs.pop('source')
        super(AnnotationImportOptionsForm, self).__init__(*args, **kwargs)

        if source.labelset is None:
            self.fields['is_uploading_annotations_not_just_points'].choices = (
                ('no', "Points only"),
            )
            self.fields['is_uploading_annotations_not_just_points'].initial = 'no'
            self.fields['is_uploading_annotations_not_just_points'].help_text = (
                "This source doesn't have a labelset yet, so you can't upload annotations."
            )

    def clean_is_uploading_annotations_not_just_points(self):
        field_name = 'is_uploading_annotations_not_just_points'
        option = self.cleaned_data[field_name]

        if option == 'yes':
            self.cleaned_data[field_name] = True
        elif option == 'no':
            self.cleaned_data[field_name] = False
        else:
            raise ValidationError("Unknown value for {field_name}".format(field_name=field_name))

        return self.cleaned_data[field_name]


class MetadataImportForm(forms.ModelForm):
    """
    Form used to import metadata from CSV.

    This need not be completely different from MetadataFormForGrid, which is
    used to edit metadata in a formset. Perhaps there is enough overlap in
    these forms' functionality that they can share fields/attributes in a
    superclass.
    """
    class Meta:
        model = Metadata
        fields = ['photo_date', 'aux1', 'aux2', 'aux3', 'aux4',
                  'aux5', 'height_in_cm', 'latitude', 'longitude',
                  'depth', 'camera', 'photographer', 'water_quality',
                  'strobes', 'framing', 'balance']

    # TODO: (Possibly) Remove when aux metadata are simple string fields
    # AND assuming all 5 aux fields are always used
    def __init__(self, source_id, save_new_values, *args, **kwargs):

        super(MetadataImportForm, self).__init__(*args, **kwargs)
        self.source = Source.objects.get(pk=source_id)
        self.save_new_values = save_new_values

        # Replace location value fields to make them CharFields instead of
        # ModelChoiceFields. Also, remove location value fields that
        # the source doesn't need.
        #
        # The main reason we still specify the value fields in Meta.fields is
        # to make it easy to specify the fields' ordering.
        for n in range(1, get_num_aux_fields()+1):
            aux_label = get_aux_label(self.source, n)
            aux_field_name = get_aux_field_name(n)

            self.fields[aux_field_name] = CharField(
                required=False,
                label=aux_label,
                max_length=get_aux_metadata_max_length(),
            )


class CSVImportForm(Form):
    csv_file = FileField(
        label='CSV file',
    )

    def __init__(self, *args, **kwargs):
        """
        Add extra_help_text to the file field.
        """
        super(CSVImportForm, self).__init__(*args, **kwargs)

        self.fields['csv_file'].dialog_help_text_template =\
            'upload/help_csv_file.html'

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']

        # Naively validate that the file is a CSV file through
        # (1) given MIME type, or (2) file extension.  Either of them
        # can be faked though.
        #
        # For the file extension check, would be more "correct" to use:
        # mimetypes.guess_type(csv_file.name) == 'text/csv'
        # but the mimetypes module doesn't recognize csv for
        # some reason.
        if csv_file.content_type == 'text/csv':
            pass
        elif csv_file.name.endswith('.csv'):
            pass
        else:
            raise ValidationError("This file is not a CSV file.")

        return self.cleaned_data['csv_file']




class ImportArchivedAnnotationsForm(Form):
    csv_file = FileField(
        label='CSV file TEST',
    )
    is_uploading_annotations_not_just_points = ChoiceField(
        label='Data',
        choices=(
            (True, "Points and annotations"),
            (False, "Points only"),
        ),
        initial=True,
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']

        # Naively validate that the file is a CSV file through
        # (1) given MIME type, or (2) file extension.  Either of them
        # can be faked though.
        #
        # For the file extension check, would be more "correct" to use:
        # mimetypes.guess_type(csv_file.name) == 'text/csv'
        # but the mimetypes module doesn't recognize csv for
        # some reason.
        if csv_file.content_type == 'text/csv':
            pass
        elif csv_file.name.endswith('.csv'):
            pass
        else:
            raise ValidationError("This file is not a CSV file.")

        return self.cleaned_data['csv_file']
