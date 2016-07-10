from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import Form, ModelForm
from django.forms.fields import CharField, ChoiceField, FileField, IntegerField
from django.forms.widgets import  Select, TextInput, NumberInput
from .models import Source, Image, Metadata, SourceInvite
from .model_utils import PointGen
from .utils import get_aux_metadata_form_choices, get_aux_metadata_max_length, get_num_aux_fields, get_aux_label, get_aux_field_name


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
            'image_height_in_cm', 'alleviate_threshold',
            'longitude', 'latitude',
        ]
        widgets = {
            'image_height_in_cm': NumberInput(attrs={'size': 3}),
            'alleviate_threshold': NumberInput(attrs={'size': 2}),
            'longitude': TextInput(attrs={'size': 10}),
            'latitude': TextInput(attrs={'size': 10}),
        }

    def __init__(self, *args, **kwargs):

        super(ImageSourceForm, self).__init__(*args, **kwargs)

        # This is used to make longitude and latitude required
        self.fields['longitude'].required = True
        self.fields['latitude'].required = True

        # For use in templates.  Can iterate over fieldsets instead of the entire form.
        self.fieldsets = {'general_info': [self[name] for name in ['name', 'visibility', 'affiliation', 'description']],
                          'image_height_in_cm': [self[name] for name in ['image_height_in_cm']],
                          'alleviate_threshold': [self[name] for name in ['alleviate_threshold']],
                          'world_location': [self[name] for name in ['latitude', 'longitude']]}

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


class ImageDetailForm(ModelForm):
    class Meta:
        model = Metadata
        fields = [
            'name', 'photo_date', 'latitude', 'longitude', 'depth',
            'height_in_cm', 'camera', 'photographer', 'water_quality',
            'strobes', 'framing', 'balance', 'comments',
            'aux1', 'aux2', 'aux3', 'aux4', 'aux5',
        ]
        widgets = {
            'height_in_cm': NumberInput(attrs={'size': 3}),
            'longitude': TextInput(attrs={'size': 10}),
            'latitude': TextInput(attrs={'size': 10}),
            'depth': TextInput(attrs={'size': 10}),
        }

    class Media:
        js = (
            # Collected from app-specific static directory
            "js/ImageDetailFormHelper.js",
        )

    def __init__(self, *args, **kwargs):
        """
        Dynamically generate the labels for the location value
        fields (the labels should be the Source's location keys).
        Remove value fields that aren't used by this source.
        """
        source = kwargs.pop('source')
        super(ImageDetailForm, self).__init__(*args, **kwargs)

        valueFields = []

        for n in range(1, get_num_aux_fields()+1):
            aux_label = get_aux_label(source, n)
            aux_field_name = get_aux_field_name(n)

            # Create a choices iterable of all of this Source's values as
            # well as an 'Other' value
            #
            # Not sure why I need to specify the '' choice here;
            # I thought required=False for the ChoiceField would
            # automatically create this... -Stephen
            choices = [('', '(None)')]
            choices += get_aux_metadata_form_choices(source, n)
            choices.append(('Other', 'Other (Specify)'))

            self.fields[aux_field_name] = ChoiceField(
                choices,
                label=aux_label,
                required=False,
            )

            # Add a text input field for specifying the Other choice
            self.fields[aux_field_name+'_other'] = CharField(
                label='Other',
                max_length=get_aux_metadata_max_length(),
                required=False,
            )

            valueFields += [aux_field_name, aux_field_name+'_other']

        # For use in templates.
        # Can iterate over fieldsets instead of the entire form.
        self.fieldsets = {
            'keys': [self[name] for name in (['photo_date'] + valueFields)],
            'other_info': [self[name] for name in [
                'name', 'latitude', 'longitude', 'depth',
                'camera', 'photographer', 'water_quality', 'strobes',
                'framing', 'balance', 'comments']
            ],
        }

    def clean(self):
        """
        1. Handle the location values.
        2. Call the parent's clean() to finish up with the default behavior.
        """
        data = self.cleaned_data

        image = Image.objects.get(metadata=self.instance)
        source = image.source

        # Right now, the valueN field's value is the integer id
        # of a ValueN object. We want the ValueN object.
        for n in range(1, get_num_aux_fields()+1):
            aux_label = get_aux_label(source, n)
            aux_field_name = get_aux_field_name(n)

            if not data[aux_field_name] == 'Other':
                continue

            # "Other" was chosen.
            otherValue = data[aux_field_name+'_other']
            if not otherValue:
                # Error
                error_message = (
                    "Since you selected Other, you must use this text box"
                    " to specify the {aux_label}.".format(
                        aux_label=aux_label))
                self.add_error(aux_field_name+'_other', error_message)
            else:
                data[aux_field_name] = otherValue
            
        self.cleaned_data = data
        super(ImageDetailForm, self).clean()


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
