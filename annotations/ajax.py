from dajaxice.decorators import dajaxice_register
from django.utils import simplejson
from annotations.forms import AnnotationToolSettingsForm
from annotations.models import AnnotationToolSettings


@dajaxice_register
def ajax_save_settings(request, submitted_settings_form):

    settings_obj = AnnotationToolSettings.objects.get(user=request.user)
    submitted_settings_form = dict([ (d['name'], d['value']) for d in submitted_settings_form ])

    settings_form = AnnotationToolSettingsForm(submitted_settings_form, instance=settings_obj)

    if settings_form.is_valid():
        settings_form.save()
        return simplejson.dumps(dict(success=True))
    else:
        # Some form values weren't correct.
        # This can happen if the form's JavaScript input checking isn't
        # foolproof, or if the user messed with form values using FireBug.
        return simplejson.dumps(dict(success=False))
