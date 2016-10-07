import codecs
from collections import defaultdict, OrderedDict
import csv

from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import validate_comma_separated_integer_list
from django.forms import Form
from django.forms.fields import CharField
from django.forms.models import ModelForm, BaseModelFormSet
from django.forms.widgets import TextInput, HiddenInput
from django.utils.html import escape

from lib.exceptions import FileProcessError
from lib.forms import get_one_form_error
from .models import Label, LabelSet, LocalLabel


def csv_to_dict(
        csv_file, required_columns, optional_columns,
        key_column, multiple_rows_per_key):
    # splitlines() is to do system-agnostic handling of newline characters.
    # The csv module can't do that by default (fails on CR only).
    reader = csv.reader(csv_file.read().splitlines(), dialect='excel')

    # Read the first row, which should have column headers.
    column_headers = next(reader)
    # There could be a UTF-8 BOM character at the start of the file.
    # Strip it in that case.
    column_headers[0] = column_headers[0].lstrip(codecs.BOM_UTF8)
    # Strip whitespace in general.
    column_headers = [h.strip() for h in column_headers]

    # Ensure column header recognition is case insensitive.
    column_headers = [h.lower() for h in column_headers]
    required_column_headers = [h.lower() for key, h in required_columns]
    # Map column text headers to string keys we want in the result dict.
    # Ignore columns we don't recognize. We'll indicate this by making the
    # column key None.
    recognized_columns = required_columns + optional_columns
    column_headers_to_keys = dict(
        (h.lower(), key) for key, h in recognized_columns)
    column_keys = [
        column_headers_to_keys.get(h, None)
        for h in column_headers
    ]

    # Use these later.
    required_column_keys = [key for key, header in required_columns]
    column_keys_to_headers = dict(
        (k, h) for k, h in recognized_columns)

    # Enforce required column headers.
    for h in required_column_headers:
        if h not in column_headers:
            raise FileProcessError(
                "CSV must have a column called {h}".format(h=h))

    csv_data = OrderedDict()

    # Read the data rows.
    for row_number, row in enumerate(reader, start=2):
        # strip() removes leading/trailing whitespace from the CSV value.
        # A column key of None indicates that we're ignoring that column.
        row_data = OrderedDict(
            (k, value.strip())
            for (k, value) in zip(column_keys, row)
            if k is not None
        )

        # Enforce presence of a value for each required column.
        for k in required_column_keys:
            if row_data[k] == '':
                raise FileProcessError(
                    "CSV row {n}: Must have a value for {h}".format(
                        n=row_number, h=column_keys_to_headers[k]))

        data_key = row_data[key_column]

        if multiple_rows_per_key:
            # A defaultdict could make this a bit cleaner, but there's no
            # ordered AND default dict built into Python.
            if data_key not in csv_data:
                csv_data[data_key] = []
            csv_data[data_key].append(row_data)
        else:
            # Only one data value allowed per key.
            if data_key in csv_data:
                raise FileProcessError(
                    "More than one row with the same {key_header}:"
                    " {value}".format(
                        key_header=column_keys_to_headers[key_column],
                        value=data_key))
            csv_data[data_key] = row_data

    return csv_data


def labels_csv_process(csv_file, source):
    csv_data = csv_to_dict(
        csv_file=csv_file,
        required_columns=[
            ('global_label_id', "Label ID"),
            ('code', "Short code"),
        ],
        optional_columns=[],
        key_column='global_label_id',
        multiple_rows_per_key=False,
    )

    local_labels = OrderedDict()

    if source.labelset:
        # Fill local_labels with the currently existing labels.
        for local_label in source.labelset.get_labels():
            local_labels[local_label.global_label.pk] = local_label

    for global_pk_str, label_data in csv_data.items():
        try:
            global_pk = int(global_pk_str)
            Label.objects.get(pk=global_pk)
        except (ValueError, Label.DoesNotExist):
            raise FileProcessError(
                "CSV has non-existent label id: {pk}".format(pk=global_pk_str))

        if global_pk in local_labels:
            # Exists in labelset; we'll use the same local label object
            # but update the fields
            form = LocalLabelForm(label_data, instance=local_labels[global_pk])
        else:
            # New to labelset
            form = LocalLabelForm(label_data)

        if not form.is_valid():
            raise FileProcessError("Row with id {pk} - {error}".format(
                pk=global_pk, error=get_one_form_error(form)))

        # Replace existing local_labels entries with new ones.
        # This gets us the set of local labels we'd have if we decided to
        # save the user's input.
        local_labels[global_pk] = form.instance
        # The form doesn't have the global label info, so set that.
        local_labels[global_pk].global_label_id = label_data['global_label_id']

    # Dict -> flat iterable.
    local_labels = local_labels.values()

    try:
        detect_dupe_label_codes(local_labels)
    except ValidationError as e:
        raise FileProcessError(e.message)

    # Remember to set the local labels' labelset fields later.
    # Other than that, they should be ready for saving.
    return local_labels


def detect_dupe_label_codes(local_labels):
    codes = [local_label.code.lower() for local_label in local_labels]
    dupe_codes = [
        code for code in codes
        if codes.count(code) > 1
    ]

    if not dupe_codes:
        return

    raise ValidationError(
        "The resulting labelset would have multiple labels with the code"
        " '{code}' (non case sensitive). This is not allowed.".format(
            code=dupe_codes[0]),
        # The following is a validation-error code used by
        # Django for error IDing, not a label code!
        code='dupe_code',
    )


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
            msg = (
                'There is already a label with the same name:'
                ' <a href="{url}" target="_blank">'
                '{existing_name}</a>').format(
                    url=reverse('label_main', args=[existing_label.pk]),
                    # Use escape to prevent XSS, since label names are in
                    # general user defined
                    existing_name=escape(existing_label.name),
                )
            raise ValidationError(msg)

        return name

    def clean_default_code(self):
        """
        Add an error if the specified name matches that of an existing label.
        """
        default_code = self.cleaned_data['default_code']

        try:
            # Case-insensitive compare
            existing_label = Label.objects.get(
                default_code__iexact=default_code)
        except Label.DoesNotExist:
            # Default code is not taken
            pass
        else:
            # Default code is taken
            msg = (
                'There is already a label with the same default code:'
                ' <a href="{url}" target="_blank">'
                '{existing_code}</a>').format(
                    url=reverse('label_main', args=[existing_label.pk]),
                    # Use escape to prevent XSS, since label codes are in
                    # general user defined
                    existing_code=escape(existing_label.default_code),
                )
            raise ValidationError(msg)

        return default_code


class LabelSetForm(Form):
    label_ids = CharField(
        validators=[validate_comma_separated_integer_list],
        required=True,
        widget=HiddenInput(),
        error_messages=dict(required="You must select one or more labels."),
    )

    labelset_ids = CharField(
        validators=[validate_comma_separated_integer_list],
        required=False,
        widget=HiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        self.source = kwargs.pop('source')
        super(LabelSetForm, self).__init__(*args, **kwargs)

        if not self.is_bound:
            if self.source.labelset:
                # Initialize with the source labelset's label ids
                global_ids = self.source.labelset.get_globals() \
                    .values_list('pk', flat=True)
                self.initial['label_ids'] = ','.join(
                    str(pk) for pk in global_ids)

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
        # These things won't happen in the absence of Javascript mistakes,
        # race conditions, and forged POST data; but defensive coding is good.

        # Return the integer list (rather than its string repr).
        return label_id_list

    def clean(self):
        """
        Detect label code conflicts in the labelset.

        Also, for convenience, set some info about the label changes
        since we have to figure it out here anyway.
        """
        if any(self.errors):
            # Don't bother with these checks unless the other fields
            # are valid so far.
            return

        pending_global_ids = set(self.cleaned_data['label_ids'])

        if self.source.labelset:
            # Editing a labelset
            existing_locals = self.source.labelset.get_labels()
        else:
            # Creating a labelset
            existing_locals = LocalLabel.objects.none()

        existing_global_ids = set(
            existing_locals.values_list('global_label_id', flat=True))
        self.global_ids_to_delete = existing_global_ids - pending_global_ids
        global_ids_to_add = pending_global_ids - existing_global_ids
        global_ids_to_keep = existing_global_ids - self.global_ids_to_delete

        self.locals_to_add = []

        # If a single labelset was chosen to copy from, copy that labelset's
        # local labels.
        # If multiple labelsets were chosen, then don't bother; the user
        # probably just wanted to grab some labels without following one
        # particular labelset's details too closely.
        #
        # Existing local labels in the target labelset take priority. The
        # copied labelset's entries are only used for newly added labels.
        if len(self.cleaned_data['labelset_ids']) == 1:
            copied_labelset = \
                LabelSet.objects.get(pk=self.cleaned_data['labelset_ids'][0])
            labels = copied_labelset.get_labels()
            global_ids = set(labels.values_list('global_label_id', flat=True))

            global_ids_to_copy = global_ids_to_add & global_ids
            global_ids_to_add_from_scratch = \
                global_ids_to_add - global_ids

            for global_id in global_ids_to_copy:
                # Grab the local label from the copied labelset.
                local_label = labels.get(global_label_id=global_id)
                # Ensure we are making a copy.
                local_label.pk = None
                # We'll be setting the labelset field later in save_labelset().
                self.locals_to_add.append(local_label)
        else:
            global_ids_to_add_from_scratch = global_ids_to_add.copy()

        for global_id in global_ids_to_add_from_scratch:
            local_label = LocalLabel(
                global_label_id=global_id,
                code=Label.objects.get(pk=global_id).default_code
            )
            self.locals_to_add.append(local_label)

        # Detect dupe codes (case-insensitively) in the pending labelset.
        codes_to_names = defaultdict(list)
        # Add entries for labels that will be added.
        for local_label in self.locals_to_add:
            codes_to_names[local_label.code.lower()].append(local_label.name)
        # Add entries for labels that will be kept.
        for global_id in global_ids_to_keep:
            local_label = existing_locals.get(global_label_id=global_id)
            codes_to_names[local_label.code.lower()].append(local_label.name)

        for code, names in codes_to_names.items():
            if len(names) >= 2:
                raise ValidationError(
                    "If this operation were completed,"
                    " the label code \"{code}\" would be used by"
                    " multiple labels in your labelset: {names}"
                    "\nThis is not allowed.".format(
                        code=code, names=', '.join(names)))

    def save_labelset(self):
        """
        Call this after validation to save the labelset.
        """
        labelset_was_created = False

        if not self.source.labelset:
            labelset = LabelSet()
            labelset.save()
            self.source.labelset = labelset
            self.source.save()
            labelset_was_created = True

        labelset = self.source.labelset

        local_labels_to_delete = labelset.get_labels() \
            .filter(global_label__pk__in=self.global_ids_to_delete)
        local_labels_to_delete.delete()

        for local_label in self.locals_to_add:
            local_label.labelset = labelset
        LocalLabel.objects.bulk_create(self.locals_to_add)

        return labelset_was_created


class LocalLabelForm(ModelForm):
    class Meta:
        model = LocalLabel
        fields = ['code']
        widgets = {
            'code': TextInput(attrs={'size': 10}),
        }


class BaseLocalLabelFormSet(BaseModelFormSet):
    def clean(self):
        """
        Checks that no two labels in the formset have the same short code
        (case-insensitive).
        """
        if any(self.errors):
            # Don't bother validating the formset
            # unless each form is valid on its own
            return

        codes_in_forms = [f.cleaned_data['code'].lower() for f in self.forms]
        dupe_codes = [
            code for code in codes_in_forms
            if codes_in_forms.count(code) > 1
        ]

        for form in self.forms:
            code = form.cleaned_data['code'].lower()
            if code in dupe_codes:
                form.add_error(
                    'code',
                    ValidationError(
                        "More than one label with the code '{code}'".format(
                            code=code),
                        # The following is a validation-error code used by
                        # Django for error IDing, not a label code!
                        code='dupe_code',
                    )
                )
