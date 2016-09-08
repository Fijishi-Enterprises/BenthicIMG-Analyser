from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_comma_separated_integer_list
from django.forms import Form
from django.forms.fields import ChoiceField, BooleanField, DateField, \
    MultiValueField, CharField
from django.forms.widgets import HiddenInput, MultiWidget

from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.models import Source, Metadata, Image, Point
from images.utils import get_aux_metadata_form_choices, get_num_aux_fields, get_aux_label, get_aux_field_name
from labels.models import LabelGroup, Label
from visualization.utils import image_search_kwargs_to_queryset


class DateFilterWidget(MultiWidget):

    def __init__(self, date_filter_field, attrs=None):
        widgets = (
            date_filter_field.date_filter_type.widget,
            date_filter_field.year.widget,
            date_filter_field.date.widget,
            date_filter_field.start_date.widget,
            date_filter_field.end_date.widget,
        )
        super(DateFilterWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
            return [
                'year',
                None,
                None,
                None,
                None,
            ]

        queryset_kwargs = value

        if 'metadata__photo_date__year' in queryset_kwargs:
            return [
                'year',
                queryset_kwargs['metadata__photo_date__year'],
                None,
                None,
                None,
            ]

        if 'metadata__photo_date' in queryset_kwargs:
            return [
                'date',
                None,
                queryset_kwargs['metadata__photo_date'],
                None,
                None,
            ]

        if 'metadata__photo_date__range' in queryset_kwargs:
            return [
                'date_range',
                None,
                None,
                queryset_kwargs['metadata__photo_date__range'][0],
                queryset_kwargs['metadata__photo_date__range'][1],
            ]


class DateFilterField(MultiValueField):
    # To be filled in by __init__()
    widget = None

    date_filter_type = ChoiceField(
        choices=[
            ('year', "Year"),
            ('date', "Date"),
            ('date_range', "Date range"),
        ],
        initial='year',
        required=True)
    # To be filled in by __init__()
    year = None
    date = DateField(required=False)
    start_date = DateField(required=False)
    end_date = DateField(required=False)

    def __init__(self, *args, **kwargs):
        self.year = ChoiceField(
            choices=kwargs.pop('year_choices'),
            required=False,
        )
        self.widget = DateFilterWidget(date_filter_field=self)

        self.date.widget.attrs['size'] = 8
        self.date.widget.attrs['placeholder'] = "Select date"
        self.start_date.widget.attrs['size'] = 8
        self.start_date.widget.attrs['placeholder'] = "Start date"
        self.end_date.widget.attrs['size'] = 8
        self.end_date.widget.attrs['placeholder'] = "End date"

        super(DateFilterField, self).__init__(
            fields=[
                self.date_filter_type,
                self.year,
                self.date,
                self.start_date,
                self.end_date,
            ],
            require_all_fields=False, *args, **kwargs)

    def compress(self, data_list):
        date_filter_type, year, date, start_date, end_date = data_list
        queryset_kwargs = dict()

        if date_filter_type == 'year':
            if not year:
                pass
            elif year == '(none)':
                queryset_kwargs['metadata__photo_date'] = None
            else:
                queryset_kwargs['metadata__photo_date__year'] = year
        elif date_filter_type == 'date':
            queryset_kwargs['metadata__photo_date'] = date
        elif date_filter_type == 'date_range':
            queryset_kwargs['metadata__photo_date__range'] = \
                [start_date, end_date]

        return queryset_kwargs


class ImageSearchForm(forms.Form):

    # This field makes it easier to tell which kind of image-specifying
    # form has been submitted.
    # It also ensures there's at least one required field, so checking form
    # validity is also a check of whether the relevant POST data is there.
    image_form_type = forms.CharField(
        widget=HiddenInput(), initial='search', required=True)

    def __init__(self, *args, **kwargs):

        self.source = kwargs.pop('source')
        has_annotation_status = kwargs.pop('has_annotation_status')
        super(ImageSearchForm, self).__init__(*args, **kwargs)

        # Date filter
        metadatas = Metadata.objects.filter(image__source=self.source)
        years = [date.year for date in metadatas.dates('photo_date', 'year')]

        # A value of '' will denote that we're not filtering by year.
        # Basically it's like we're not using this field, so an empty
        # value makes the most sense.
        #
        # A value of '(none)' will denote that we want images that don't
        # specify a year in their metadata.
        # We can't denote this with a Python None value, because that
        # becomes '' in the rendered dropdown, which conflicts with the
        # above.
        year_choices = (
            [('', "All")]
            + [(year, year) for year in years]
            + [('(none)', "(None)")]
        )
        self.fields['date_filter'] = DateFilterField(
            label="Date filter", year_choices=year_choices, required=False)

        # Metadata fields
        metadata_choice_fields = []

        for n in range(1, get_num_aux_fields()+1):
            metadata_choice_fields.append(
                (get_aux_field_name(n), get_aux_label(self.source, n))
            )
        non_aux_fields = [
            'height_in_cm', 'latitude', 'longitude', 'depth',
            'camera', 'photographer', 'water_quality',
            'strobes', 'framing', 'balance',
        ]
        for field_name in non_aux_fields:
            metadata_choice_fields.append(
                (field_name, Metadata._meta.get_field(field_name).verbose_name)
            )

        self.metadata_choice_fields = []

        for field_name, field_label in metadata_choice_fields:
            choices = Metadata.objects.filter(image__source=self.source) \
                .order_by(field_name) \
                .values_list(field_name, flat=True) \
                .distinct()

            if len(choices) <= 1:
                # No point in having a dropdown for this
                continue

            self.fields[field_name] = forms.ChoiceField(
                label=field_label,
                choices=(
                    # Any value
                    [('', "All")]
                    # Non-blank values
                    + [(c, c) for c in choices if c]
                    # Blank value
                    + [('(none)', "(None)")]
                ),
                required=False,
            )

            # Set this for ease of listing the fields in templates.
            # self[field_name] seems to be a different field object from
            # self.fields[field_name], and seems easier to use in templates.
            self.metadata_choice_fields.append(self[field_name])

        # Annotation status
        if has_annotation_status:
            status_choices = [('', "All"), ('confirmed', "Confirmed")]
            if self.source.enable_robot_classifier:
                status_choices.append(('unconfirmed', "Unconfirmed"))
            status_choices.append(('unclassified', "Unclassified"))

            self.fields['annotation_status'] = forms.ChoiceField(
                label="Annotation status",
                choices=status_choices,
                required=False,
            )

    def clean_image_form_type(self):
        value = self.cleaned_data['image_form_type']
        if value != 'search':
            raise ValidationError("Incorrect value")
        return value

    def get_images(self):
        """
        Call this after cleaning the form to get the image search results
        specified by the fields.
        """
        return image_search_kwargs_to_queryset(self.cleaned_data, self.source)

    def get_filters_used_display(self):
        """
        Return a display of the non-blank filters used on the source's images
        based on this form.
        e.g. "height (cm), year, habitat, camera"
        """
        filters_used = []
        for key, value in self.cleaned_data.items():
            if value == '':
                pass
            elif key == 'image_form_type':
                pass
            elif key == 'date_filter':
                if 'metadata__photo_date__year' in value:
                    filters_used.append('year')
                elif 'metadata__photo_date' in value:
                    # This actually encompasses both the date option and
                    # an empty year option, but either way this is
                    # an accurate enough display.
                    filters_used.append('date')
                elif 'metadata__photo_date__range' in value:
                    filters_used.append('date range')
            else:
                filters_used.append(self.fields[key].label.lower())
        return ", ".join(filters_used)


class PatchSearchOptionsForm(forms.Form):

    def __init__(self, *args, **kwargs):

        source = kwargs.pop('source')
        super(PatchSearchOptionsForm, self).__init__(*args, **kwargs)

        # Label
        if source.labelset is None:
            label_choices = Label.objects.none()
        else:
            label_choices = source.labelset.get_globals().order_by('name')
        self.fields['label'] = forms.ModelChoiceField(
            queryset=label_choices,
            required=False,
            empty_label="All",
        )

        # Annotation status
        status_choices = [('', "All"), ('confirmed', "Confirmed")]
        if source.enable_robot_classifier:
            status_choices.append(('unconfirmed', "Unconfirmed"))

        self.fields['annotation_status'] = forms.ChoiceField(
            choices=status_choices,
            required=False,
        )

        # Annotator
        confirmed_annotations = \
            Annotation.objects.filter(source=source) \
            .exclude(user=get_robot_user())
        annotator_choices = \
            User.objects.filter(annotation__in=confirmed_annotations) \
            .order_by('username') \
            .distinct()
        self.fields['annotator'] = forms.ModelChoiceField(
            queryset=annotator_choices,
            required=False,
            empty_label="All",
        )

    def get_patches(self, image_results):
        """
        Call this after cleaning the form to get the patch search results
        specified by the fields, within the specified images.
        """
        data = self.cleaned_data

        # Only get patches corresponding to annotated points of the
        # given images.
        patch_results = \
            Point.objects.filter(image__in=image_results) \
            .exclude(annotation=None)

        # Empty value is None for ModelChoiceFields, '' for other fields.
        # (If we could use None for every field, we would, but there seems to
        # be no way to do that with plain ChoiceFields out of the box.)
        #
        # An empty value for these fields means we're not filtering
        # by the field.

        if data['label'] is not None:
            patch_results = patch_results.filter(
                annotation__label=data['label'])

        if data['annotation_status'] == 'unconfirmed':
            patch_results = patch_results.filter(
                annotation__user=get_robot_user())
        elif data['annotation_status'] == 'confirmed':
            patch_results = patch_results.exclude(
                annotation__user=get_robot_user())

        # This option doesn't really make sense if filtering status as
        # 'unconfirmed', but not a big deal if the user does a search
        # like that. It'll just get 0 results.
        if data['annotator'] is not None:
            patch_results = patch_results.filter(
                annotation__user=data['annotator'])

        return patch_results


class ImageSpecifyByIdForm(forms.Form):

    # This field makes it easier to tell which kind of image-specifying
    # form has been submitted.
    image_form_type = forms.CharField(
        widget=HiddenInput(), initial='ids', required=True)

    ids = forms.CharField(
        widget=HiddenInput(),
        validators=[validate_comma_separated_integer_list],
        required=True)

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super(ImageSpecifyByIdForm,self).__init__(*args, **kwargs)

    def clean_image_form_type(self):
        value = self.cleaned_data['image_form_type']
        if value != 'ids':
            raise ValidationError("Incorrect value")
        return value

    def clean_ids(self):
        id_str_list = self.cleaned_data['ids'].split(',')
        id_list = []

        for img_id in id_str_list:
            try:
                id_num = int(img_id)
            except ValueError:
                # Not an int for some reason. Just skip this faulty id.
                continue

            # Check that these ids correspond to images in the source (not to
            # images of other sources).
            # This ensures that any attempt to forge POST data to specify
            # other sources' image ids will not work.
            try:
                Image.objects.get(pk=id_num, source=self.source)
            except Image.DoesNotExist:
                # The image either doesn't exist or isn't in this source.
                # Skip it.
                continue

            id_list.append(id_num)

        return id_list

    def get_images(self):
        """
        Call this after cleaning the form to get the images
        specified by the fields.
        """
        return Image.objects.filter(
            source=self.source, pk__in=self.cleaned_data['ids'])

    def get_filters_used_display(self):
        return "(Manual selection)"


def post_to_image_filter_form(POST_data, source, has_annotation_status):
    """
    All the browse views and the annotation tool view can use this
    to process image-specification forms.
    """
    image_form = None
    if POST_data.get('image_form_type') == 'search':
        image_form = ImageSearchForm(
            POST_data, source=source,
            has_annotation_status=has_annotation_status)
    elif POST_data.get('image_form_type') == 'ids':
        image_form = ImageSpecifyByIdForm(POST_data, source=source)

    return image_form


class HiddenForm(forms.Form):
    """
    Takes a list of forms as an init parameter, copies the forms'
    submitted data, and adds corresponding fields with HiddenInput widgets.

    This is useful if the previous page load submitted form data,
    and we wish to pass those submitted values to a subsequent request.
    """
    def __init__(self, *args, **kwargs):
        forms = kwargs.pop('forms')
        super(HiddenForm, self).__init__(*args, **kwargs)

        for form in forms:
            for name, field in form.fields.items():
                if isinstance(field, MultiValueField):
                    # Must look in the MultiValueField's attributes
                    # to get the actual rendered input fields.
                    for i, sub_field in enumerate(field.fields):
                        sub_field_name = '{name}_{i}'.format(name=name, i=i)
                        self.fields[sub_field_name] = CharField(
                            initial=form.data.get(
                                sub_field_name, sub_field.initial),
                            widget=HiddenInput(),
                            required=False)
                else:
                    self.fields[name] = CharField(
                        initial=form.data.get(name, field.initial),
                        widget=HiddenInput(),
                        required=False)


# Similar to ImageSearchForm with the difference that
# label selection appears on a multi-select checkbox form
# TODO: Remove parts that are redundant with ImageSearchForm, and use
# ImageSearchForm along with this form in the statistics page

class StatisticsSearchForm(forms.Form):
    class Meta:
        fields = ('aux1', 'aux2', 'aux3',
              'aux4', 'aux5', 'labels', 'groups', 'include_robot')

    def __init__(self,source_id,*args,**kwargs):
        super(StatisticsSearchForm,self).__init__(*args,**kwargs)

        # Grab the source and its labels
        source = Source.objects.filter(id=source_id)[0]
        if source.labelset is None:
            labels = []
        else:
            labels = source.labelset.get_globals().order_by('group__id', 'name')
        groups = LabelGroup.objects.all().distinct()

        # Get the location keys
        for n in range(1, get_num_aux_fields()+1):
            aux_label = get_aux_label(source, n)
            aux_field_name = get_aux_field_name(n)

            choices = [('', 'All')]
            choices += get_aux_metadata_form_choices(source, n)

            self.fields[aux_field_name] = forms.ChoiceField(
                choices,
                label=aux_label,
                required=False,
            )

        # Put the label choices in order
        label_choices = \
            [(label.id, label.name) for label in labels]

        group_choices = \
            [(group.id, group.name) for group in groups]
        
        # Custom widget for label selection
        #self.fields['labels'].widget = CustomCheckboxSelectMultiple(choices=self.fields['labels'].choices)
        self.fields['labels']= forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                         choices=label_choices, required=False)

        self.fields['groups']= forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                                         choices=group_choices, required=False)
        
        self.fields['include_robot'] = BooleanField(required=False)


class CheckboxForm(Form):
    """
    This is used in conjunction with MetadataFormForGrid;
    but since the metadata form is rendered as a form set,
    and we only want one select-all checkbox, this form exists.
    """
    selected = BooleanField(required=False)