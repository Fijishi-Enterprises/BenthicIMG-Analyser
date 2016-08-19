from django import forms
from django.contrib.auth.models import User
from django.core.validators import validate_comma_separated_integer_list
from django.forms import Form
from django.forms.fields import ChoiceField, BooleanField
from django.forms.widgets import HiddenInput

from accounts.utils import get_robot_user
from annotations.models import LabelGroup, Label, Annotation
from images.models import Source, Metadata, Image, Point
from images.utils import get_aux_metadata_form_choices, get_num_aux_fields, get_aux_label, get_aux_field_name


class ImageSearchForm(forms.Form):

    def __init__(self, *args, **kwargs):

        self.source = kwargs.pop('source')
        has_annotation_status = kwargs.pop('has_annotation_status')
        super(ImageSearchForm, self).__init__(*args, **kwargs)

        # Year
        metadatas = Metadata.objects.filter(image__source=self.source)
        years = [date.year for date in metadatas.dates('photo_date', 'year')]

        self.fields['year'] = ChoiceField(
            # A value of '' will denote that we're not filtering by year.
            # Basically it's like we're not using this field, so an empty
            # value makes the most sense.
            #
            # A value of '(none)' will denote that we want images that don't
            # specify a year in their metadata.
            # We can't denote this with a Python None value, because that
            # becomes '' in the rendered dropdown, which conflicts with the
            # above.
            # So we'll use the value '(all)', which seems reasonably unlikely
            # to conflict with other values in these dropdowns.
            choices=(
                [('', "All")]
                + [(year,year) for year in years]
                + [('(none)', "(None)")]
            ),
            required=False
        )

        # Aux1, Aux2, etc.
        for n in range(1, get_num_aux_fields()+1):
            aux_label = get_aux_label(self.source, n)
            aux_field_name = get_aux_field_name(n)

            choices = (
                [('', "All")]
                + get_aux_metadata_form_choices(self.source, n)
                + [('(none)', "(None)")]
            )

            self.fields[aux_field_name] = forms.ChoiceField(
                choices=choices,
                label=aux_label,
                required=False,
            )

        # Annotation status
        if has_annotation_status:
            status_choices = [('', "All"), ('confirmed', "Confirmed")]
            if self.source.enable_robot_classifier:
                status_choices.append(('unconfirmed', "Unconfirmed"))
            status_choices.append(('unclassified', "Unclassified"))

            self.fields['annotation_status'] = forms.ChoiceField(
                choices=status_choices,
                required=False,
            )

    def get_images(self):
        """
        Call this after cleaning the form to get the image search results
        specified by the fields.
        """
        data = self.cleaned_data
        queryset_kwargs = dict()

        # Year
        if data['year'] == '':
            # Don't filter by year
            pass
        elif data['year'] == '(none)':
            # Get images with no photo date specified
            queryset_kwargs['metadata__photo_date'] = None
        else:
            # Filter by the given year
            queryset_kwargs['metadata__photo_date__year'] = int(data['year'])

        # Aux1, Aux2, etc.
        for n in range(1, get_num_aux_fields() + 1):
            aux_field_name = get_aux_field_name(n)

            if data[aux_field_name] == '':
                # Don't filter by this aux field
                pass
            elif data[aux_field_name] == '(none)':
                # Get images with an empty aux value
                queryset_kwargs['metadata__' + aux_field_name] = ''
            else:
                # Filter by the given non-empty aux value
                queryset_kwargs['metadata__' + aux_field_name] = \
                    data[aux_field_name]

        # Annotation status
        if 'annotation_status' in data:
            if data['annotation_status'] == '':
                # Don't filter
                pass
            elif data['annotation_status'] == 'confirmed':
                queryset_kwargs['status__annotatedByHuman'] = True
            elif data['annotation_status'] == 'unconfirmed':
                queryset_kwargs['status__annotatedByHuman'] = False
                queryset_kwargs['status__annotatedByRobot'] = True
            elif data['annotation_status'] == 'unclassified':
                queryset_kwargs['status__annotatedByHuman'] = False
                queryset_kwargs['status__annotatedByRobot'] = False

        image_results = \
            Image.objects.filter(source=self.source, **queryset_kwargs)

        return image_results


class PatchSearchOptionsForm(forms.Form):

    def __init__(self, *args, **kwargs):

        source = kwargs.pop('source')
        super(PatchSearchOptionsForm, self).__init__(*args, **kwargs)

        # Label
        if source.labelset is None:
            label_choices = Label.objects.none()
        else:
            label_choices = source.labelset.labels.all()
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

    ids = forms.CharField(
        widget=HiddenInput(),
        validators=[validate_comma_separated_integer_list])

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super(ImageSpecifyByIdForm,self).__init__(*args, **kwargs)

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


# TODO: Figure out what to do with these
class ImageBatchDeleteForm(ImageSearchForm):
    pass
class ImageBatchDownloadForm(ImageSearchForm):
    pass


# Similar to VisualizationSearchForm with the difference that
# label selection appears on a multi-select checkbox form
# TODO: Merge with VisualizationSearchForm to remove redundancy

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
            labels = source.labelset.labels.all().order_by('group__id', 'name')
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