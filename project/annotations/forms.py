from decimal import Decimal
from itertools import chain
import json
from django.core.exceptions import ValidationError, MultipleObjectsReturned
from django.core.mail import mail_admins
from django.core.urlresolvers import reverse
from django import forms
from django.forms import Form
from django.forms.fields import BooleanField, CharField, DecimalField, IntegerField
from django.forms.models import ModelForm
from django.forms.widgets import TextInput, HiddenInput, NumberInput
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from accounts.utils import is_robot_user, get_robot_user
from annotations.model_utils import AnnotationAreaUtils
from annotations.models import Label, LabelSet, Annotation, AnnotationToolSettings
from images.models import Point, Source, Metadata, Image


class CustomCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
   """
   Custom widget to enable multiple checkboxes without outputting a wrongful
   helptext since I'm modifying the widget used to display labels.
   This is a workaround for a bug in Django which associates helptext
   with the view instead of with the widget being used.
   """

   items_per_row = 4 # Number of items per row

   def render(self, name, value, attrs=None, choices=()):
       if value is None: value = []
       has_id = attrs and 'id' in attrs
       final_attrs = self.build_attrs(attrs, name=name)
       output = ['<table><tr>']
       # Normalize to strings
       str_values = set([force_unicode(v) for v in value])
       for i, (option_value, option_label) in enumerate(chain(self.choices, choices)):
           # If an ID attribute was given, add a numeric index as a suffix,
           # so that the checkboxes don't all have the same ID attribute.
           if has_id:
               final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
               label_for = ' for="%s"' % final_attrs['id']
           else:
               label_for = ''

           cb = forms.CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
           option_value = force_unicode(option_value)
           rendered_cb = cb.render(name, option_value)
           option_label = conditional_escape(force_unicode(option_label))
           if i != 0 and i % self.items_per_row == 0:
               output.append('</tr><tr>')
           output.append('<td nowrap><label%s>%s %s</label></td>' % (label_for, rendered_cb, option_label))
       output.append('</tr></table>')
       return mark_safe('\n'.join(output))

class NewLabelForm(ModelForm):
    class Meta:
        model = Label
        fields = ['name', 'code', 'group', 'description', 'thumbnail']
        widgets = {
            'code': TextInput(attrs={'size': 10}),
        }
        
    def clean(self):
        """
        1. Add an error if the specified name or code matches that of an existing label.
        2. Call the parent's clean() to finish up with the default behavior.
        """
        data = self.cleaned_data

        if data.has_key('name'):
            labelsOfSameName = Label.objects.filter(name__iexact=data['name'])
            if len(labelsOfSameName) > 0:
                # mark_safe(), along with the |safe template filter, allows HTML in the message.
                msg = mark_safe('There is already a label with the name %s: <a href="%s" target="_blank">%s</a>' % (
                    data['name'],
                    reverse('label_main', args=[labelsOfSameName[0].id]),
                    labelsOfSameName[0].name,
                ))
                self.add_error('name', msg)

        if data.has_key('code'):
            labelsOfSameCode = Label.objects.filter(code__iexact=data['code'])
            if len(labelsOfSameCode) > 0:
                msg = mark_safe('There is already a label with the short code %s: <a href="%s" target="_blank">%s</a>' % (
                    data['code'],
                    reverse('label_main', args=[labelsOfSameCode[0].id]),
                    labelsOfSameCode[0].name,
                ))
                self.add_error('code', msg)

        self.cleaned_data = data
        super(NewLabelForm, self).clean()

class NewLabelSetForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(NewLabelSetForm, self).__init__(*args, **kwargs)

        # Put the label choices in order
        self.fields['labels'].choices = \
            [(label.id, label) for label in Label.objects.all().order_by('group__id', 'name')]

        # Custom widget for label selection
        self.fields['labels'].widget = CustomCheckboxSelectMultiple(
            choices=self.fields['labels'].choices)
        # Removing "Hold down "Control", or "Command" on a Mac, to select more than one."
        self.fields['labels'].help_text = ''

    class Meta:
        model = LabelSet
        fields = ['labels']

    class Media:
        js = (
            # From this app's static folder
            "js/LabelsetFormHelper.js",
        )


class AnnotationForm(forms.Form):

    def __init__(self, *args, **kwargs):
        image = kwargs.pop('image')
        show_machine_annotations = kwargs.pop('show_machine_annotations')
        super(AnnotationForm, self).__init__(*args, **kwargs)

        labelFieldMaxLength = Label._meta.get_field('code').max_length


        for point in Point.objects.filter(image=image).order_by('point_number'):

            try:
                if show_machine_annotations:
                    existingAnnotation = Annotation.objects.get(point=point)
                else:
                    existingAnnotation = Annotation.objects.exclude(user=get_robot_user()).get(point=point)
            except Annotation.DoesNotExist:
                existingAnnotation = None
            except MultipleObjectsReturned:
                existingAnnotation = None
                mail_admins('Multiple annotations returned for a point object', 'Multiple annotations returned for query: Annotations.objects.get(point=point) for Imageid:' + str(image.id) + ', pointid:' + str(point.id) + '. Please investigate.')

            if existingAnnotation:
                existingAnnoCode = existingAnnotation.label.code
                isRobotAnnotation = is_robot_user(existingAnnotation.user)
            else:
                existingAnnoCode = ''
                isRobotAnnotation = None

            pointNum = point.point_number

            # Create the text field for annotating a point with a label code.
            # label_1 for point 1, label_23 for point 23, etc.
            labelFieldName = 'label_' + str(pointNum)

            self.fields[labelFieldName] = CharField(
                widget=TextInput(attrs=dict(
                    size=6,
                    readonly='',
                )),
                max_length=labelFieldMaxLength,
                label=str(pointNum),
                required=False,
                initial=existingAnnoCode,
            )

            # Create a hidden field to indicate whether a point is robot-annotated or not.
            # robot_1 for point 1, robot_23 for point 23, etc.
            robotFieldName = 'robot_' + str(pointNum)

            self.fields[robotFieldName] = BooleanField(
                widget=HiddenInput(),
                required=False,
                initial=json.dumps(isRobotAnnotation),
            )


class AnnotationToolSettingsForm(ModelForm):

    class Meta:
        model = AnnotationToolSettings
        fields = [
            'point_marker', 'point_marker_size', 'point_marker_is_scaled',
            'point_number_size', 'point_number_is_scaled',
            'unannotated_point_color', 'robot_annotated_point_color',
            'human_annotated_point_color', 'selected_point_color',
            'show_machine_annotations',
        ]

    class Media:
        js = ('jscolor/jscolor.js',
              'js/AnnotationToolSettingsHelper.js',)

    def __init__(self, *args, **kwargs):
        super(AnnotationToolSettingsForm, self).__init__(*args, **kwargs)

        # Make text fields have the appropriate size.
        self.fields['point_marker_size'].widget.attrs.update({'size': 2})
        self.fields['point_number_size'].widget.attrs.update({'size': 2})

        # Make the color fields have class="color" so they use jscolor.
        color_fields = [self.fields[name] for name in
                        ['unannotated_point_color',
                         'robot_annotated_point_color',
                         'human_annotated_point_color',
                         'selected_point_color',]
                       ]
        for field in color_fields:
            field.widget.attrs.update({'class': 'color'})


class AnnotationImageOptionsForm(Form):

    class Media:
        js = ('js/AnnotationToolImageHelper.js',)

    brightness = IntegerField(initial='0', widget=NumberInput(attrs={'size': 3}))
    contrast = DecimalField(initial='0', widget=NumberInput(attrs={'size': 3}))


class AnnotationAreaPercentsForm(Form):

    min_x = DecimalField(label="Left boundary X",
                         required=True, min_value=Decimal(0), max_value=Decimal(100),
                         decimal_places=3, widget=NumberInput(attrs={'size': 3}))
    max_x = DecimalField(label="Right boundary X",
                         required=True, min_value=Decimal(0), max_value=Decimal(100),
                         decimal_places=3, widget=NumberInput(attrs={'size': 3}))
    min_y = DecimalField(label="Top boundary Y",
                         required=True, min_value=Decimal(0), max_value=Decimal(100),
                         decimal_places=3, widget=NumberInput(attrs={'size': 3}))
    max_y = DecimalField(label="Bottom boundary Y",
                         required=True, min_value=Decimal(0), max_value=Decimal(100),
                         decimal_places=3, widget=NumberInput(attrs={'size': 3}))

    def __init__(self, *args, **kwargs):
        """
        If a Source is passed in as an argument, then get
        the annotation area of that Source,
        and use that to fill the form fields' initial values.
        """
        if kwargs.has_key('source'):
            source = kwargs.pop('source')

            if source.image_annotation_area:
                kwargs['initial'] = AnnotationAreaUtils.db_format_to_percentages(source.image_annotation_area)

        self.form_help_text = Source._meta.get_field('image_annotation_area').help_text

        super(AnnotationAreaPercentsForm, self).__init__(*args, **kwargs)


    def clean(self):
        data = self.cleaned_data

        if 'min_x' in data and 'max_x' in data:

            if data['min_x'] >= data['max_x']:
                self.add_error('max_x', "The right boundary x must be greater than the left boundary x.")
                # Also mark min_x as being errored
                del data['min_x']

        if 'min_y' in data and 'max_y' in data:

            if data['min_y'] >= data['max_y']:
                self.add_error('max_y', "The bottom boundary y must be greater than the top boundary y.")
                # Also mark min_y as being errored
                del data['min_y']

        self.cleaned_data = data
        super(AnnotationAreaPercentsForm, self).clean()


class AnnotationAreaPixelsForm(Form):

    class Media:
        js = ("js/AnnotationAreaEditHelper.js",)
        css = {
            'all': ("css/annotation_area_edit.css",)
        }

    # The complete field definitions are in __init__(), because
    # max_value needs to be set dynamically.
    # (We *could* just append the max-value validators dynamically, except
    # that results in some really weird behavior where the error list grows
    # with duplicate errors every time you press submit.)
    min_x = IntegerField()
    max_x = IntegerField()
    min_y = IntegerField()
    max_y = IntegerField()

    def __init__(self, *args, **kwargs):

        image = kwargs.pop('image')

        if image.metadata.annotation_area:
            d = AnnotationAreaUtils.db_format_to_numbers(image.metadata.annotation_area)
            annoarea_type = d.pop('type')
            if annoarea_type == AnnotationAreaUtils.TYPE_PERCENTAGES:
                kwargs['initial'] = AnnotationAreaUtils.percentages_to_pixels(width=image.original_width, height=image.original_height, **d)
            elif annoarea_type == AnnotationAreaUtils.TYPE_PIXELS:
                kwargs['initial'] = d
            elif annoarea_type == AnnotationAreaUtils.TYPE_IMPORTED:
                raise ValueError("Points were imported; annotation area should be un-editable.")

        super(AnnotationAreaPixelsForm, self).__init__(*args, **kwargs)

        self.fields['min_x'] = IntegerField(
            label="Left boundary X", required=False,
            min_value=1, max_value=image.original_width,
            widget=NumberInput(attrs={'size': 3})
        )
        self.fields['max_x'] = IntegerField(
            label="Right boundary X", required=False,
            min_value=1, max_value=image.original_width,
            widget=NumberInput(attrs={'size': 3})
        )
        self.fields['min_y'] = IntegerField(
            label="Top boundary Y", required=False,
            min_value=1, max_value=image.original_height,
            widget=NumberInput(attrs={'size': 3})
        )
        self.fields['max_y'] = IntegerField(
            label="Bottom boundary Y", required=False,
            min_value=1, max_value=image.original_height,
            widget=NumberInput(attrs={'size': 3})
        )

        self.form_help_text = Metadata._meta.get_field('annotation_area').help_text

    def clean(self):
        data = self.cleaned_data

        field_names = ['min_x', 'max_x', 'min_y', 'max_y']
        no_errors_yet = len(filter(lambda key: key not in data, field_names)) == 0

        if no_errors_yet:
            has_empty_fields = len(filter(lambda key: data[key] is None, field_names)) > 0
            all_empty_fields = len(filter(lambda key: data[key] is not None, field_names)) == 0

            if has_empty_fields and not all_empty_fields:
                raise ValidationError("You must fill in all four of the annotation area fields.")

        if 'min_x' in data and 'max_x' in data:

            if data['min_x'] > data['max_x']:
                self.add_error('max_x', "The right boundary x must be greater than or equal to the left boundary x.")
                del data['min_x']
                del data['max_x']

        if 'min_y' in data and 'max_y' in data:

            if data['min_y'] > data['max_y']:
                self.add_error('max_y', "The bottom boundary y must be greater than or equal to the top boundary y.")
                del data['min_y']
                del data['max_y']

        self.cleaned_data = data
        super(AnnotationAreaPixelsForm, self).clean()
