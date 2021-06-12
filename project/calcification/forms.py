from django.forms import Form
from django.forms.fields import ChoiceField, MultipleChoiceField
from django.forms.widgets import CheckboxSelectMultiple

from calcification.utils import get_default_calcify_tables


def get_calcify_table_choices():
    default_tables = get_default_calcify_tables()
    choices = [
        (table.pk, table.name)
        for table in default_tables]

    return choices


class ExportCalcifyStatsForm(Form):
    rate_table_id = ChoiceField(
        label="Label rates to use",
        choices=get_calcify_table_choices)

    optional_columns = MultipleChoiceField(
        widget=CheckboxSelectMultiple, required=False)

    def __init__(self, source, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # TODO: The best thing to do is to remove all possibility of
        # initializing this form without a labelset, and then remove this
        # conditional.
        if source.labelset:
            labelset_size = source.labelset.get_labels().count()
        else:
            labelset_size = 0

        self.fields['optional_columns'].choices = (
            ('per_label_mean',
             "Per-label contributions to mean rate"
             f" (adds {labelset_size} columns)"),
            ('per_label_bounds',
             "Per-label contributions to confidence bounds"
             f" (adds {labelset_size * 2} columns)"),
        )
