from itertools import chain
from django.core.urlresolvers import reverse
from django.forms.models import ModelForm
from django.forms.widgets import CheckboxInput, CheckboxSelectMultiple, \
    TextInput
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from .models import Label, LabelSet


class CustomCheckboxSelectMultiple(CheckboxSelectMultiple):
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
        for i, (option_value, option_label) in enumerate \
                (chain(self.choices, choices)):
            # If an ID attribute was given, add a numeric index as a suffix,
            # so that the checkboxes don't all have the same ID attribute.
            if has_id:
                final_attrs = dict(final_attrs, id='%s_%s' % (attrs['id'], i))
                label_for = ' for="%s"' % final_attrs['id']
            else:
                label_for = ''

            cb = CheckboxInput(final_attrs, check_test=lambda value: value in str_values)
            option_value = force_unicode(option_value)
            rendered_cb = cb.render(name, option_value)
            option_label = conditional_escape(force_unicode(option_label))
            if i != 0 and i % self.items_per_row == 0:
                output.append('</tr><tr>')
            output.append('<td nowrap><label%s>%s %s</label></td>' %
            (label_for, rendered_cb, option_label))
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
                msg = mark_safe(
                    'There is already a label with the name %s: <a href="%s" target="_blank">%s</a>' % (
                        data['name'],
                        reverse('label_main', args=[labelsOfSameName[0].id]),
                        labelsOfSameName[0].name,
                    ))
                self.add_error('name', msg)

        if data.has_key('code'):
            labelsOfSameCode = Label.objects.filter(code__iexact=data['code'])
            if len(labelsOfSameCode) > 0:
                msg = mark_safe(
                    'There is already a label with the short code %s: <a href="%s" target="_blank">%s</a>' % (
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
            [(label.id, label) for label in
             Label.objects.all().order_by('group__id', 'name')]

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
