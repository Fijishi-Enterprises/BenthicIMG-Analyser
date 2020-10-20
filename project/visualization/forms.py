import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_comma_separated_integer_list
from django.forms import Form
from django.forms.fields import (
    BooleanField, CharField, ChoiceField, DateField, MultiValueField)
from django.forms.widgets import HiddenInput, MultiWidget
from django.utils import timezone

from accounts.utils import (
    get_alleviate_user, get_imported_user, get_robot_user)
from annotations.models import Annotation
from images.models import Source, Metadata, Image
from images.utils import (
    get_aux_field_name, get_aux_label, get_aux_metadata_form_choices,
    get_num_aux_fields)
from labels.models import LabelGroup, Label
from .utils import get_annotation_tool_users, image_search_kwargs_to_queryset

tz = timezone.get_current_timezone()


class DateFilterWidget(MultiWidget):

    def __init__(self, date_filter_field, attrs=None):
        self.date_lookup = date_filter_field.date_lookup
        self.is_datetime_field = date_filter_field.is_datetime_field
        widgets = [
            getattr(date_filter_field, field_name).widget
            for field_name in date_filter_field.field_order]
        super(DateFilterWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
            return [
                None,
                None,
                None,
                None,
                None,
            ]

        queryset_kwargs = value

        if self.date_lookup + '__year' in queryset_kwargs:
            return [
                'year',
                queryset_kwargs[self.date_lookup + '__year'],
                None,
                None,
                None,
            ]

        if self.date_lookup in queryset_kwargs:
            if queryset_kwargs[self.date_lookup] is None:
                return [
                    '(none)',
                    None,
                    None,
                    None,
                    None,
                ]
            else:
                return [
                    'date',
                    None,
                    queryset_kwargs[self.date_lookup],
                    None,
                    None,
                ]

        if self.date_lookup + '__range' in queryset_kwargs:
            if self.is_datetime_field:
                return [
                    'date_range',
                    None,
                    None,
                    queryset_kwargs[self.date_lookup + '__range'][0],
                    queryset_kwargs[self.date_lookup + '__range'][1]
                    - datetime.timedelta(days=1),
                ]
            else:
                return [
                    'date_range',
                    None,
                    None,
                    queryset_kwargs[self.date_lookup + '__range'][0],
                    queryset_kwargs[self.date_lookup + '__range'][1],
                ]


class DateFilterField(MultiValueField):
    # To be filled in by __init__()
    widget = None

    # Fields to be filled in by __init__()
    date_filter_type = None
    year = None

    date = DateField(required=False)
    start_date = DateField(required=False)
    end_date = DateField(required=False)

    field_order = [
        'date_filter_type', 'year', 'date', 'start_date', 'end_date']

    def __init__(self, *args, **kwargs):
        # This field class is used in a search box, and the search action has
        # a primary model whose objects are being filtered by the search.
        # date_lookup describes how to go from that primary model to the
        # date value that this field is interested in, for purposes of
        # queryset filtering usage.
        # For example, if the primary model is Image, then the
        # date_lookup might be 'metadata__photo_date'.
        self.date_lookup = kwargs.pop('date_lookup')
        self.is_datetime_field = kwargs.pop('is_datetime_field', False)
        self.none_option = kwargs.pop('none_option', True)

        date_filter_type_choices = [
            # A value of '' will denote that we're not filtering by date.
            # Basically it's like we're not using this field, so an empty
            # value makes the most sense.
            ('', "Any"),
            ('year', "Year"),
            ('date', "Exact date"),
            ('date_range', "Date range"),
        ]
        if self.none_option:
            # A value of '(none)' will denote that we want objects that have no
            # date specified.
            # We can't denote this with a Python None value, because that
            # becomes '' in the rendered dropdown, which conflicts with the
            # above.
            date_filter_type_choices.append(('(none)', "(None)"))
        self.date_filter_type = ChoiceField(
            choices=date_filter_type_choices,
            initial='',
            required=False,
        )

        self.year = ChoiceField(
            choices=kwargs.pop('year_choices'),
            required=False,
        )
        self.widget = DateFilterWidget(date_filter_field=self)

        self.date.widget.attrs['size'] = 10
        self.date.widget.attrs['placeholder'] = "Select date"
        self.start_date.widget.attrs['size'] = 10
        self.start_date.widget.attrs['placeholder'] = "Start date"
        self.end_date.widget.attrs['size'] = 10
        self.end_date.widget.attrs['placeholder'] = "End date"

        # Define how the filter type field value controls the visibility
        # of the other fields.
        date_filter_type_index = str(
            self.field_order.index('date_filter_type'))
        self.year.widget.attrs['data-visibility-condition'] = \
            date_filter_type_index + '=year'
        self.date.widget.attrs['data-visibility-condition'] = \
            date_filter_type_index + '=date'
        self.start_date.widget.attrs['data-visibility-condition'] = \
            date_filter_type_index + '=date_range'
        self.end_date.widget.attrs['data-visibility-condition'] = \
            date_filter_type_index + '=date_range'

        # Define fields which should have datepickers.
        # `True` specifies an HTML5 boolean attribute, where it just has the
        # attribute name without any value.
        self.date.widget.attrs['data-has-datepicker'] = True
        self.start_date.widget.attrs['data-has-datepicker'] = True
        self.end_date.widget.attrs['data-has-datepicker'] = True

        super(DateFilterField, self).__init__(
            fields=[
                getattr(self, field_name) for field_name in self.field_order],
            require_all_fields=False, *args, **kwargs)

    def compress(self, data_list):
        # Unsure why data_list is an empty list sometimes, but one
        # case is when you get to Browse via a GET link which only has
        # image_search_type and annotation_status kwargs.
        if not data_list:
            return dict()

        date_filter_type, year, date, start_date, end_date = data_list
        queryset_kwargs = dict()

        if date_filter_type == '':
            # Not filtering on this date field
            pass

        elif date_filter_type == '(none)':
            # Objects with no date specified
            queryset_kwargs[self.date_lookup] = None

        elif date_filter_type == 'year':
            try:
                int(year)
            except ValueError:
                raise ValidationError("Must specify a year.")
            queryset_kwargs[self.date_lookup + '__year'] = year

        elif date_filter_type == 'date':
            if date is None:
                raise ValidationError("Must specify a date.")
            if self.is_datetime_field:
                # Matching `date` alone just matches exactly 00:00:00 on that
                # date, so we need to make a range for the entire 24 hours of
                # the date instead.
                dt = datetime.datetime(
                    date.year, date.month, date.day, tzinfo=tz)
                queryset_kwargs[self.date_lookup + '__range'] = [
                    dt, dt + datetime.timedelta(days=1)]
            else:
                queryset_kwargs[self.date_lookup] = date

        elif date_filter_type == 'date_range':
            if start_date is None:
                raise ValidationError("Must specify a start date.")
            if end_date is None:
                raise ValidationError("Must specify an end date.")
            if self.is_datetime_field:
                # Accept anything from the start of the start date to the end
                # of the end date.
                start_dt = datetime.datetime(
                    start_date.year, start_date.month, start_date.day,
                    tzinfo=tz)
                end_dt = datetime.datetime(
                    end_date.year, end_date.month, end_date.day, tzinfo=tz)
                queryset_kwargs[self.date_lookup + '__range'] = [
                    start_dt, end_dt + datetime.timedelta(days=1)]
            else:
                queryset_kwargs[self.date_lookup + '__range'] = \
                    [start_date, end_date]

        return queryset_kwargs


class AnnotatorFilterWidget(MultiWidget):

    def __init__(self, annotator_filter_field, attrs=None):
        self.annotator_lookup = annotator_filter_field.annotator_lookup
        widgets = [
            getattr(annotator_filter_field, field_name).widget
            for field_name in annotator_filter_field.field_order]
        super(AnnotatorFilterWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value is None:
            return [
                None,
                None,
                None,
                None,
                None,
            ]

        queryset_kwargs = value

        annotator = queryset_kwargs[self.annotator_lookup]

        if annotator.pk == get_alleviate_user().pk:
            return [
                'alleviate',
                None,
            ]

        elif annotator.pk == get_imported_user().pk:
            return [
                'imported',
                None,
            ]

        elif annotator.pk == get_robot_user().pk:
            return [
                'machine',
                None,
            ]

        else:
            return [
                'annotation_tool',
                annotator,
            ]


class AnnotatorFilterField(MultiValueField):
    # To be filled in by __init__()
    widget = None

    annotation_method = ChoiceField(
        choices=[
            ('', "Any"),
            ('annotation_tool', "Annotation Tool"),
            ('alleviate', "Alleviate"),
            ('imported', "Importing"),
            ('machine', "Machine"),
        ],
        required=False)

    # To be filled in by __init__()
    annotation_tool_user = None

    field_order = ['annotation_method', 'annotation_tool_user']

    def __init__(self, *args, **kwargs):
        source = kwargs.pop('source')

        # annotator_lookup describes how to go from the search's primary
        # model to the annotator value that this field is interested in,
        # for purposes of queryset filtering usage.
        self.annotator_lookup = kwargs.pop('annotator_lookup')

        self.annotation_tool_user = forms.ModelChoiceField(
            queryset=get_annotation_tool_users(source),
            required=False,
            empty_label="Any user",
        )

        # Define how the annotation method field value controls the
        # visibility of the other fields.
        annotation_method_index = str(
            self.field_order.index('annotation_method'))
        self.annotation_tool_user.widget.attrs['data-visibility-condition'] = \
            annotation_method_index + '=annotation_tool'

        self.widget = AnnotatorFilterWidget(annotator_filter_field=self)

        super(AnnotatorFilterField, self).__init__(
            fields=[
                getattr(self, field_name) for field_name in self.field_order],
            require_all_fields=False, *args, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return dict()

        annotation_method, annotation_tool_user = data_list
        queryset_kwargs = dict()

        if annotation_method == 'annotation_tool':
            if annotation_tool_user:
                queryset_kwargs[self.annotator_lookup] = annotation_tool_user
            else:
                # Any annotation tool user
                user_field = self.fields[
                    self.field_order.index('annotation_tool_user')]
                queryset_kwargs[self.annotator_lookup + '__in'] = \
                    user_field.queryset
        elif annotation_method == 'alleviate':
            queryset_kwargs[self.annotator_lookup] = get_alleviate_user()
        elif annotation_method == 'imported':
            queryset_kwargs[self.annotator_lookup] = get_imported_user()
        elif annotation_method == 'machine':
            queryset_kwargs[self.annotator_lookup] = get_robot_user()

        return queryset_kwargs


class ImageSearchForm(forms.Form):

    # This field makes it easier to tell which kind of image-specifying
    # form has been submitted.
    # It also ensures there's at least one required field, so checking form
    # validity is also a check of whether the relevant POST data is there.
    image_form_type = forms.CharField(
        widget=HiddenInput(), initial='search', required=True)

    # Search by image name.
    image_name = forms.CharField(label="Image name contains", required=False)

    def __init__(self, *args, **kwargs):

        self.source = kwargs.pop('source')
        for_browse_patches = kwargs.pop('for_browse_patches', False)
        for_edit_metadata = kwargs.pop('for_edit_metadata', False)
        super(ImageSearchForm, self).__init__(*args, **kwargs)

        # Date filter
        metadatas = Metadata.objects.filter(image__source=self.source)
        image_years = [
            date.year for date in metadatas.dates('photo_date', 'year')]
        image_year_choices = [(str(year), str(year)) for year in image_years]

        self.fields['photo_date'] = DateFilterField(
            label="Photo date", year_choices=image_year_choices,
            date_lookup='metadata__photo_date', required=False)

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
                    [('', "Any")]
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

        if not for_browse_patches:

            # Annotation status

            status_choices = [('', "Any"), ('confirmed', "Confirmed")]
            if self.source.enable_robot_classifier:
                status_choices.append(('unconfirmed', "Unconfirmed"))
            status_choices.append(('unclassified', "Unclassified"))

            self.fields['annotation_status'] = forms.ChoiceField(
                label="Annotation status",
                choices=status_choices,
                required=False,
            )

            # Last annotated

            annotation_years = range(
                self.source.create_date.year, timezone.now().year + 1)
            annotation_year_choices = [
                (str(year), str(year)) for year in annotation_years]
            self.fields['last_annotated'] = DateFilterField(
                label="Last annotation date",
                year_choices=annotation_year_choices,
                date_lookup='last_annotation__annotation_date',
                is_datetime_field=True, required=False)

            # Last annotator

            self.fields['last_annotator'] = AnnotatorFilterField(
                label="By",
                source=self.source,
                annotator_lookup='last_annotation__user',
                required=False)
            # 'verbose name' separate from the label, for use by
            # get_applied_search_display().
            self.fields['last_annotator'].verbose_name = "Last annotator"

        if not for_edit_metadata and not for_browse_patches:

            # Sort options

            self.fields['sort_method'] = forms.ChoiceField(
                label="Sort by",
                choices=(
                    ('name', "Name"),
                    ('upload_date', "Upload date"),
                    ('photo_date', "Photo date"),
                    ('last_annotation_date', "Last annotation date"),
                ),
                required=True)

            self.fields['sort_direction'] = forms.ChoiceField(
                label="Direction",
                choices=(
                    ('asc', "Ascending"),
                    ('desc', "Descending"),
                ),
                required=True)

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

    def get_choice_verbose(self, field_name):
        choices = self.fields[field_name].choices
        return dict(choices)[self.cleaned_data[field_name]]

    def get_sort_method_verbose(self):
        return self.get_choice_verbose('sort_method')

    def get_sort_direction_verbose(self):
        return self.get_choice_verbose('sort_direction')

    def get_applied_search_display(self):
        """
        Return a display of the form's specified filters and sort method
        e.g. "Filtering by height (cm), year, habitat, camera; Sorting by
        upload date, descending"
        """
        filters_used = []
        for key, value in self.cleaned_data.items():
            if value == '' or value == dict():
                # Not filtering by this field. '' is the basic field case,
                # dict() is the MultiValueField case.
                pass
            elif key in ['image_form_type', 'sort_method', 'sort_direction']:
                pass
            else:
                field = self.fields[key]
                if hasattr(field, 'verbose_name'):
                    # For some fields, we may specify a verbose name which is
                    # different from the label used on the form.
                    filters_used.append(field.verbose_name.lower())
                else:
                    filters_used.append(field.label.lower())

        sorting_by_str = "Sorting by {}, {}".format(
            self.get_sort_method_verbose().lower(),
            self.get_sort_direction_verbose().lower(),
        )

        if filters_used:
            return "Filtering by {}; {}".format(
                ", ".join(filters_used), sorting_by_str)
        else:
            return sorting_by_str


class PatchSearchOptionsForm(Form):

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
            empty_label="Any",
        )

        # Annotation status

        status_choices = [('', "Any"), ('confirmed', "Confirmed")]
        if source.enable_robot_classifier:
            status_choices.append(('unconfirmed', "Unconfirmed"))

        self.fields['annotation_status'] = forms.ChoiceField(
            choices=status_choices,
            required=False,
        )

        # Annotation date

        annotation_years = range(
            source.create_date.year, timezone.now().year + 1)
        annotation_year_choices = [
            (str(year), str(year)) for year in annotation_years]
        self.fields['annotation_date'] = DateFilterField(
            label="Annotation date", year_choices=annotation_year_choices,
            date_lookup='annotation_date',
            is_datetime_field=True, none_option=False, required=False)

        # Annotator

        self.fields['annotator'] = AnnotatorFilterField(
            label="Annotated by",
            source=source,
            annotator_lookup='user',
            required=False)

    def get_annotations(self, image_results):
        """
        Call this after cleaning the form to get the annotation search results
        specified by the fields, within the specified images.

        In the patches view, we care more about the points than the
        annotations, but it's more efficient to get a queryset of annotations
        and then just grab the few points that we want to display on the page.
        """
        data = self.cleaned_data

        # Only get patches corresponding to annotated points of the
        # given images.
        results = Annotation.objects.filter(image__in=image_results)

        # Empty value is None for ModelChoiceFields, '' for other fields.
        # (If we could use None for every field, we would, but there seems to
        # be no way to do that with plain ChoiceFields out of the box.)
        #
        # An empty value for these fields means we're not filtering
        # by the field.

        if data['label'] is not None:
            results = results.filter(label=data['label'])

        if data['annotation_status'] == 'unconfirmed':
            results = results.filter(user=get_robot_user())
        elif data['annotation_status'] == 'confirmed':
            results = results.exclude(user=get_robot_user())

        # For multi-value fields, the search kwargs are the cleaned data.
        for field_name in ['annotation_date', 'annotator']:
            field_kwargs = data.get(field_name, None)
            if field_kwargs:
                results = results.filter(**field_kwargs)

        return results


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
            # Should already be validated as an integer string.
            id_num = int(img_id)

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
        # TODO: If coming from Browse Images, the ordering specified in Browse
        # isn't preserved, which can be confusing.
        return self.source.image_set.filter(pk__in=self.cleaned_data['ids']) \
            .order_by('metadata__name', 'pk')

    def get_applied_search_display(self):
        return "Filtering to a specific set of images"


def create_image_filter_form(
        data, source, for_edit_metadata=False, for_browse_patches=False):
    """
    All the browse views and the annotation tool view can use this
    to process image-specification forms.
    """
    image_form = None
    if data.get('image_form_type') == 'search':
        image_form = ImageSearchForm(
            data, source=source,
            for_edit_metadata=for_edit_metadata,
            for_browse_patches=for_browse_patches)
    elif data.get('image_form_type') == 'ids':
        image_form = ImageSpecifyByIdForm(data, source=source)

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
