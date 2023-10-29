from django import forms
from django.forms import fields
from django.forms.renderers import TemplatesSetting


class GridFormRenderer(TemplatesSetting):
    """
    Based off of TemplatesSetting, for overriding built-in widget templates:
    https://docs.djangoproject.com/en/dev/ref/forms/renderers/#templatessetting
    """
    form_template_name = 'lib/forms/grid.html'


class RowsFormRenderer(TemplatesSetting):
    form_template_name = 'lib/forms/rows.html'


class BoxFormRenderer(TemplatesSetting):
    form_template_name = 'lib/forms/box.html'


class EnhancedForm(forms.Form):
    """
    Form subclass with our own additions:

    - Allows grouping fields into fieldsets, which can be recognized
    in renderer templates for visually grouping related fields.
    """
    fieldsets_keys: list

    def get_context(self):
        """
        Context for the form-renderer template.
        """
        context = super().get_context()
        if not self.fieldsets_keys:
            # No fieldsets have been defined in the Form
            return context

        field_dict = {
            field.name: (field, errors)
            for (field, errors) in context['fields']
        }

        # Two levels of fieldsets are supported: fieldsets and subfieldsets.
        # If you only need one level, then put your fieldsets in another pair
        # of brackets [] to define it as subfieldsets of a single fieldset.
        fieldsets = []
        for fieldset_keys in self.fieldsets_keys:
            fieldset = []

            for subfieldset_keys in fieldset_keys:
                subfieldset = []

                for key in subfieldset_keys:
                    if key in field_dict:
                        subfieldset.append(field_dict[key])

                if subfieldset:
                    fieldset.append(subfieldset)

            if fieldset:
                fieldsets.append(fieldset)

        context['fieldsets'] = fieldsets
        return context


class DummyForm(forms.Form):
    """
    Dummy form that can be used for Javascript tests
    in place of any other form, to keep those tests simple.
    """
    def __init__(self, **field_values):
        super().__init__()

        if not field_values:
            field_values['field1'] = 'value1'
        for field_name, field_value in field_values.items():
            self.fields[field_name] = fields.CharField(
                required=False, initial=field_value)


def get_one_form_error(form, include_field_name=True):
    """
    Use this if form validation failed and you just want to get the string for
    one error.
    """
    for field_name, error_messages in form.errors.items():
        if error_messages:
            if not include_field_name:
                # Requested not to include the field name in the message
                return error_messages[0]
            elif field_name == '__all__':
                # Non-field error
                return error_messages[0]
            else:
                # Include the field name
                return "{field}: {error}".format(
                    field=form[field_name].label,
                    error=error_messages[0])

    # This function was called under the assumption that there was a
    # form error, but if we got here, then we couldn't find that form error.
    return (
        "Unknown error. If the problem persists, please let us know on the"
        " forum.")


def get_one_formset_error(formset, get_form_name, include_field_name=True):
    for form in formset:
        error_message = get_one_form_error(form, include_field_name)

        if not error_message.startswith("Unknown error"):
            # Found an error in this form
            return "{form}: {error}".format(
                form=get_form_name(form),
                error=error_message)

    for error_message in formset.non_form_errors():
        return error_message

    return (
        "Unknown error. If the problem persists, please let us know on the"
        " forum.")
