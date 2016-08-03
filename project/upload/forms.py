from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.images import get_image_dimensions
from django.forms import ImageField, Form, ChoiceField, FileField
from django.forms.widgets import FileInput


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

    This is used only for the frontend of the image upload form,
    not the backend.
    That is, the user selects multiple images in the browser,
    but the images are sent to the server one by one.
    """
    files = MultipleImageField(
        label='Image files',
        widget=MultipleFileInput(),
    )


class ImageUploadForm(Form):
    """
    Takes a single image file.

    This is used only for the backend of the image upload form,
    not the frontend.
    That is, the user selects multiple images in the browser,
    but the images are sent to the server one by one.
    """
    file = ImageField(
        label='Image file',
        widget=FileInput(),
        error_messages={
            'invalid_image': (
                "The file is either a corrupt image,"
                " or in a file format that we don't support."
            ),
        },
    )

    def clean_file(self):
        image_file = self.cleaned_data['file']

        if image_file.content_type not in \
         settings.IMAGE_UPLOAD_ACCEPTED_CONTENT_TYPES:
            raise ValidationError(
                "This image file format isn't supported.",
                code='image_file_format',
            )

        width, height = get_image_dimensions(image_file)
        max_width, max_height = settings.IMAGE_UPLOAD_MAX_DIMENSIONS

        if width > max_width or height > max_height:
            raise ValidationError(
                "Ensure the image dimensions are at most"
                " {w} x {h}.".format(w=max_width, h=max_height),
                code='max_image_dimensions',
            )

        return self.cleaned_data['file']


class CSVImportForm(Form):
    csv_file = FileField(
        label='CSV file',
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
