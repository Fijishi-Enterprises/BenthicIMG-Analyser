from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import Form, ModelForm, BaseModelFormSet
from django.forms.fields import CharField, ChoiceField, FileField, IntegerField
from django.forms.widgets import Select, TextInput, NumberInput

from .models import Source, Metadata, SourceInvite
from .model_utils import PointGen
from .utils import get_aux_label_field_names, aux_label_name_collisions


def validate_aux_meta_field_name(field_name):
    """
    Check if an aux. field is used to denote date, year or similar.
    :return: The passed field name.
    :raise: ValidationError if the name isn't valid.
    """
    date_strings = {'date', 'year', 'time', 'month', 'day'}
    if field_name.lower() in date_strings:
        raise ValidationError(
            "Date of image acquisition is already a default metadata field."
            " Do not use auxiliary metadata fields"
            " to encode temporal information."
        )
    return field_name


class ImageSourceForm(ModelForm):

    class Meta:
        model = Source
        # Some of the fields are handled by separate forms, so this form
        # doesn't have all of the Source model's fields.
        fields = [
            'name', 'visibility', 'description', 'affiliation',
            'key1', 'key2', 'key3', 'key4', 'key5',
            'confidence_threshold',
            'longitude', 'latitude',
        ]
        widgets = {
            'confidence_threshold': NumberInput(attrs={'size': 2}),
            'longitude': TextInput(attrs={'size': 10}),
            'latitude': TextInput(attrs={'size': 10}),
        }

    def __init__(self, *args, **kwargs):

        super(ImageSourceForm, self).__init__(*args, **kwargs)

        if not self.instance.pk:
            # New source form shouldn't have this field.
            del self.fields['confidence_threshold']

        # These aren't required by the model (probably to support old sources)
        # but should be required in the form.
        self.fields['longitude'].required = True
        self.fields['latitude'].required = True

    def clean_key1(self):
        return validate_aux_meta_field_name(self.cleaned_data['key1'])
    def clean_key2(self):
        return validate_aux_meta_field_name(self.cleaned_data['key2'])
    def clean_key3(self):
        return validate_aux_meta_field_name(self.cleaned_data['key3'])
    def clean_key4(self):
        return validate_aux_meta_field_name(self.cleaned_data['key4'])
    def clean_key5(self):
        return validate_aux_meta_field_name(self.cleaned_data['key5'])

    def clean_latitude(self):
        data = self.cleaned_data['latitude']
        try:
            latitude = float(data)
        except:
            raise ValidationError("Latitude is not a number.")
        if latitude < -90 or latitude > 90:
            raise ValidationError("Latitude is out of range.")
        return data

    def clean_longitude(self):
        data = self.cleaned_data['longitude']
        try:
            longitude = float(data)
        except:
            raise ValidationError("Longitude is not a number.")
        if longitude < -180 or longitude > 180:
            raise ValidationError("Longitude is out of range.")
        return data

    def clean(self):
        """
        Check for aux label name collisions with other aux fields or built-in
        metadata fields.
        Since this involves comparing the aux labels with each other,
        it has to be implemented in the form-wide clean function.
        """
        cleaned_data = super(ImageSourceForm, self).clean()

        aux_label_kwargs = dict(
            (n, cleaned_data.get(n))
            for n in get_aux_label_field_names()
            if n in cleaned_data
        )

        # Initialize a dummy Source (which we won't actually save) with the
        # aux label values. We'll just use this to call our function which
        # checks for name collisions.
        dummy_source = Source(**aux_label_kwargs)
        dupe_labels = aux_label_name_collisions(dummy_source)
        if dupe_labels:
            # Add an error to any field which has one of the dupe labels.
            for field_name, field_label in aux_label_kwargs.items():
                if field_label.lower() in dupe_labels:
                    self.add_error(
                        field_name,
                        ValidationError(
                            "This conflicts with either a built-in metadata"
                            " field or another auxiliary field.",
                            code='dupe_label',
                        ))


class SourceChangePermissionForm(Form):

    perm_change = ChoiceField(label='Permission Level', choices=Source._meta.permissions)

    def __init__(self, *args, **kwargs):
        self.source_id = kwargs.pop('source_id')
        user = kwargs.pop('user')
        super(SourceChangePermissionForm, self).__init__(*args, **kwargs)
        source = Source.objects.get(pk=self.source_id)
        members = source.get_members_ordered_by_role()
        memberList = [(member.id,member.username) for member in members]

        # This removes the current user from users that can have their permission changed
        if (user.id,user.username) in memberList:
            memberList.remove((user.id,user.username))
        self.fields['user'] = ChoiceField(label='User', choices=[member for member in memberList], required=True)

class SourceRemoveUserForm(Form):

    def __init__(self, *args, **kwargs):
        self.source_id = kwargs.pop('source_id')
        self.user = kwargs.pop('user')
        super(SourceRemoveUserForm, self).__init__(*args, **kwargs)
        source = Source.objects.get(pk=self.source_id)
        members = source.get_members_ordered_by_role()
        memberList = [(member.id,member.username) for member in members]

        # This removes the current user from users that can have their permission changed
        if (self.user.id,self.user.username) in memberList:
            memberList.remove((self.user.id,self.user.username))
        self.fields['user'] = ChoiceField(label='User', choices=[member for member in memberList], required=True)

class SourceInviteForm(Form):
    # This is not a ModelForm, because a ModelForm would by default
    # make us use a dropdown/radiobutton for the recipient field,
    # and it would validate that the recipient field's value is a
    # foreign key id.  This is a slight pain to work around if we
    # want a text box for the recipient field, so it's easier
    # to just use a Form.

    recipient = CharField(max_length=User._meta.get_field('username').max_length,
                          help_text="The recipient's username.")
    source_perm = ChoiceField(label='Permission level',
                              choices=SourceInvite._meta.get_field('source_perm').choices)

    def __init__(self, *args, **kwargs):
        self.source_id = kwargs.pop('source_id')
        super(SourceInviteForm, self).__init__(*args, **kwargs)

    def clean_recipient(self):
        """
        This method cleans the recipient field of a submitted form.
        It is automatically called during form validation.

        1. Strip spaces.
        2. Check that we have a valid recipient username.
        If so, replace the username with the recipient user's id.
        If not, throw an error.
        """

        recipientUsername = self.cleaned_data['recipient']
        recipientUsername = recipientUsername.strip()

        try:
            User.objects.get(username=recipientUsername)
        except User.DoesNotExist:
            raise ValidationError("There is no user with this username.")

        return recipientUsername

    def clean(self):
        """
        Looking at both the recipient and the source, see if we have an
        error case:
        (1) The recipient is already a member of the source.
        (2) The recipient has already been invited to the source.
        """

        if not self.cleaned_data.has_key('recipient'):
            return super(SourceInviteForm, self).clean()

        recipientUser = User.objects.get(username=self.cleaned_data['recipient'])
        source = Source.objects.get(pk=self.source_id)

        if source.has_member(recipientUser):
            msg = u"%s is already in this Source." % recipientUser.username
            self.add_error('recipient', msg)
            return super(SourceInviteForm, self).clean()

        try:
            SourceInvite.objects.get(recipient=recipientUser, source=source)
        except SourceInvite.DoesNotExist:
            pass
        else:
            msg = u"%s has already been invited to this Source." % recipientUser.username
            self.add_error('recipient', msg)

        super(SourceInviteForm, self).clean()


class MetadataForm(ModelForm):
    """
    Edit metadata of an image.
    """
    class Meta:
        model = Metadata
        fields = Metadata.EDIT_FORM_FIELDS

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super(MetadataForm, self).__init__(*args, **kwargs)

        # Specify aux. fields' labels. These depend on the source,
        # so this must be done during init.
        self.fields['aux1'].label = self.source.key1
        self.fields['aux2'].label = self.source.key2
        self.fields['aux3'].label = self.source.key3
        self.fields['aux4'].label = self.source.key4
        self.fields['aux5'].label = self.source.key5

        # Specify fields' size attributes. This is done during init so that
        # we can modify existing widgets, thus avoiding having to manually
        # re-specify the widget class and attributes besides size.
        field_sizes = dict(
            name=30,
            photo_date=8,
            aux1=10,
            aux2=10,
            aux3=10,
            aux4=10,
            aux5=10,
            height_in_cm=10,
            latitude=10,
            longitude=10,
            depth=10,
            camera=10,
            photographer=10,
            water_quality=10,
            strobes=10,
            framing=16,
            balance=16,
        )
        for field_name, field_size in field_sizes.items():
            self.fields[field_name].widget.attrs['size'] = str(field_size)


class MetadataFormForGrid(MetadataForm):
    """
    Metadata form which is used in the metadata-edit grid view.
    """
    class Meta:
        model = Metadata
        fields = Metadata.EDIT_FORM_FIELDS
        widgets = {
            # Our metadata-edit grid Javascript is wonky with a
            # NumberInput widget.
            #
            # Browser-side checking makes the value not submit
            # if it thinks the input is erroneous, leading to
            # our Ajax returning "This field is required" when the field
            # actually is filled with an erroneous value.
            # Only change this to NumberInput if we have a good solution
            # for this issue.
            'height_in_cm': TextInput(attrs={'size': 10,}),
        }


class BaseMetadataFormSet(BaseModelFormSet):
    def clean(self):
        """
        Checks that no two images in the source have the same name.
        """
        if any(self.errors):
            # Don't bother validating the formset
            # unless each form is valid on its own
            return

        source = self.forms[0].source
        # For some reason, there is an extra form at the end which has
        # no valid values...
        actual_forms = self.forms[:-1]

        # Find dupe image names in the source, taking together the
        # existing names of images not in the forms, and the new names
        # of images in the forms
        pks_in_forms = [f.instance.pk for f in actual_forms]
        names_not_in_forms = list(
            Metadata.objects
            .filter(image__source=source)
            .exclude(pk__in=pks_in_forms)
            .values_list('name', flat=True)
        )
        names_in_forms = [f.cleaned_data['name'] for f in actual_forms]
        all_names = names_not_in_forms + names_in_forms
        dupe_names = [
            name for name in all_names
            if all_names.count(name) > 1
        ]

        for form in actual_forms:
            name = form.cleaned_data['name']
            if name in dupe_names:
                form.add_error(
                    'name',
                    ValidationError(
                        "Same name as another image in"
                        " the source or this form",
                        code='dupe_name',
                    )
                )


class PointGenForm(Form):

    class Media:
        js = (
            # From annotations static directory
            "js/PointGenFormHelper.js",
        )

    MAX_NUM_POINTS = 1000

    point_generation_type = ChoiceField(
        label='Point generation type',
        choices=Source.POINT_GENERATION_CHOICES,
        widget=Select(attrs={'onchange': 'PointGenFormHelper.showOnlyRelevantFields()'}),
    )

    # The following fields may or may not be required depending on the
    # point_generation_type. We'll make all of them required by default,
    # then in clean(), we'll ignore the errors for fields that
    # we decide are not required.

    # For simple random
    simple_number_of_points = IntegerField(
        label='Number of annotation points', required=True,
        min_value=1, max_value=MAX_NUM_POINTS,
        widget=NumberInput(attrs={'size': 3}),
    )

    # For stratified random and uniform grid
    number_of_cell_rows = IntegerField(
        label='Number of cell rows', required=True,
        min_value=1, max_value=MAX_NUM_POINTS,
        widget=NumberInput(attrs={'size': 3}),
    )
    number_of_cell_columns = IntegerField(
        label='Number of cell columns', required=True,
        min_value=1, max_value=MAX_NUM_POINTS,
        widget=NumberInput(attrs={'size': 3}),
    )

    # For stratified random
    stratified_points_per_cell = IntegerField(
        label='Points per cell', required=True,
        min_value=1, max_value=MAX_NUM_POINTS,
        widget=NumberInput(attrs={'size': 3}),
    )

    def __init__(self, *args, **kwargs):
        """
        If a Source is passed in as an argument, then get
        the point generation method of that Source,
        and use that to fill the form fields' initial values.
        """
        if kwargs.has_key('source'):
            source = kwargs.pop('source')
            kwargs['initial'] = PointGen.db_to_args_format(source.default_point_generation_method)

        self.form_help_text = Source._meta.get_field('default_point_generation_method').help_text

        super(PointGenForm, self).__init__(*args, **kwargs)

    def clean(self):
        data = self.cleaned_data
        type = data['point_generation_type']

        # Depending on the point generation type that was picked, different
        # fields are going to be required or not. Identify the required fields
        # (other than the point-gen type).
        additional_required_fields = []
        if type == PointGen.Types.SIMPLE:
            additional_required_fields = ['simple_number_of_points']
        elif type == PointGen.Types.STRATIFIED:
            additional_required_fields = ['number_of_cell_rows', 'number_of_cell_columns', 'stratified_points_per_cell']
        elif type == PointGen.Types.UNIFORM:
            additional_required_fields = ['number_of_cell_rows', 'number_of_cell_columns']

        # Get rid of errors for the fields we don't care about.
        required_fields = ['point_generation_type'] + additional_required_fields
        for key in self._errors.keys():
            if key not in required_fields:
                del self._errors[key]

        # If there are no errors so far, do a final check of
        # the total number of points specified.
        # It should be between 1 and MAX_NUM_POINTS.
        if len(self._errors) == 0:

            num_points = 0
            if type == PointGen.Types.SIMPLE:
                num_points = data['simple_number_of_points']
            elif type == PointGen.Types.STRATIFIED:
                num_points = data['number_of_cell_rows'] * data['number_of_cell_columns'] * data['stratified_points_per_cell']
            elif type == PointGen.Types.UNIFORM:
                num_points = data['number_of_cell_rows'] * data['number_of_cell_columns']

            if num_points > PointGenForm.MAX_NUM_POINTS:
                raise ValidationError("You specified %s points total. Please make it no more than %s." % (num_points, PointGenForm.MAX_NUM_POINTS))

        self.cleaned_data = data
        super(PointGenForm, self).clean()


class LabelImportForm(Form):
    labelset_description = CharField(
        label='Labelset description',
    )

    labels_file = FileField(
        label='Labels file (.txt)',
    )
