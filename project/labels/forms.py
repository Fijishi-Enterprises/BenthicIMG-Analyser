from itertools import chain

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import validate_comma_separated_integer_list
from django.forms import Form
from django.forms.fields import CharField
from django.forms.models import ModelForm
from django.forms.widgets import CheckboxInput, CheckboxSelectMultiple, \
    TextInput
from django.utils.encoding import force_unicode
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from .models import Label, LabelSet, LocalLabel


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


class LabelForm(ModelForm):
    class Meta:
        model = Label
        fields = ['name', 'default_code', 'group', 'description', 'thumbnail']
        widgets = {
            'default_code': TextInput(attrs={'size': 10}),
        }

    def clean_name(self):
        """
        Add an error if the specified name matches that of an existing label.
        """
        name = self.cleaned_data['name']

        try:
            # Case-insensitive compare
            existing_label = Label.objects.get(name__iexact=name)
        except Label.DoesNotExist:
            # Name is not taken
            pass
        else:
            # Name is taken
            #
            # mark_safe(), along with the |safe template filter,
            # allows HTML in the message.
            msg = mark_safe((
                'There is already a label with the same name:'
                ' <a href="{url}" target="_blank">'
                '{existing_name}</a>').format(
                    url=reverse('label_main', args=[existing_label.pk]),
                    existing_name=existing_label.name,
                ))
            raise ValidationError(msg)

        return name

    # No check for Labels with the same default code. We only care about
    # LabelSets having unique LocalLabel codes.


class LabelSetForm(Form):
    label_ids = CharField(
        validators=[validate_comma_separated_integer_list],
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super(LabelSetForm, self).__init__(*args, **kwargs)

    def clean_label_ids(self):
        # Run through a set to remove dupes, then get a list again
        label_id_list = list(set(
            int(pk) for pk in self.cleaned_data['label_ids'].split(',')))

        # Check if labels of these ids exist
        bad_id_list = []
        for label_id in label_id_list:
            try:
                Label.objects.get(pk=label_id)
            except Label.DoesNotExist:
                bad_id_list.append(label_id)

        if bad_id_list:
            msg = (
                "Could not find labels of ids: {bad_ids}."
                " Either we messed up, or one of the"
                " labels you selected just got deleted."
                " If the problem persists,"
                " please contact the site admins.").format(
                    bad_ids=", ".join(str(n) for n in bad_id_list),
                )
            raise ValidationError(msg)

        # TODO: Check that there's at least 1 valid label id.
        # TODO: Check if any in-use labels are marked for removal.

        # Return the integer list (rather than its string repr).
        return label_id_list

    def save_labelset(self):
        """
        Call this after validation to save the labelset.
        """
        pending_global_ids = set(self.cleaned_data['label_ids'])

        if not self.source.labelset:
            labelset = LabelSet()
            labelset.save()
            self.source.labelset = labelset
            self.source.save()

        labelset = self.source.labelset
        existing_global_ids = set(
            labelset.get_globals().values_list('pk', flat=True))

        global_ids_to_delete = existing_global_ids - pending_global_ids
        local_labels_to_delete = labelset.get_labels().filter(
                global_label__pk__in=global_ids_to_delete)
        local_labels_to_delete.delete()

        global_ids_to_add = pending_global_ids - existing_global_ids
        local_labels_to_add = []
        for global_id in global_ids_to_add:
            global_label = Label.objects.get(pk=global_id)
            local_label = LocalLabel(
                code=global_label.default_code,
                global_label=global_label,
                labelset=labelset,
            )
            local_labels_to_add.append(local_label)
        LocalLabel.objects.bulk_create(local_labels_to_add)
