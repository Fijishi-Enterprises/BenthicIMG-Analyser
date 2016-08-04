from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.mail import mail_admins
from django.core.mail.message import BadHeaderError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import render, get_object_or_404
from django.template import loader, TemplateDoesNotExist, Context

from annotations.models import Point
from images.models import Image, Source
from images.utils import get_map_sources, get_random_public_images
from lib.forms import ContactForm
from lib import msg_consts, str_consts

def contact(request):
    """
    Page with a contact form, which allows the user to send a general
    purpose email to the site admins.
    """
    if request.method == 'POST':
        contact_form = ContactForm(request.user, request.POST)

        if contact_form.is_valid():
            # Set up the subject and message.
            if request.user.is_authenticated():
                username = request.user.username
                base_subject = contact_form.cleaned_data['subject']
                user_email = request.user.email
                base_message = contact_form.cleaned_data['message']
            else:
                username = "[A guest]"
                base_subject = contact_form.cleaned_data['subject']
                user_email = contact_form.cleaned_data['email']
                base_message = contact_form.cleaned_data['message']

            subject = str_consts.CONTACT_EMAIL_SUBJECT_FMTSTR.format(
                username=username,
                base_subject=base_subject,
            )
            message = str_consts.CONTACT_EMAIL_MESSAGE_FMTSTR.format(
                username=username,
                user_email=user_email,
                base_message=base_message,
            )

            # Send the mail.
            try:
                mail_admins(
                    subject=subject,
                    message=message,
                )
            except BadHeaderError:
                messages.error(
                    request,
                    "Sorry, the email could not be sent. It didn't pass a security check."
                )
            else:
                messages.success(request, msg_consts.CONTACT_EMAIL_SENT)
                return HttpResponseRedirect(reverse('index'))
        else:
            messages.error(request, msg_consts.FORM_ERRORS)

    else: # GET
        contact_form = ContactForm(request.user)

    return render(request, 'lib/contact.html', {
        'contact_form': contact_form,
    })

def index(request):
    """
    This view renders the front page.
    """

    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('source_list'))

    # Here we get the map sources
    map_sources = get_map_sources()

    list_thumbnails = []
    # Here we get a list of a list of images, these will be displayed
    # within each of the description windows.
    # the latest images source will not be passed into the javascript functions
    for source in map_sources:
        list_thumbnails.append((source["latest_images"],source["id"]))
        del source["latest_images"]

    # and here we get 5 random public images
    images = get_random_public_images()

    # Gather some stats
    total_sources = Source.objects.all().count()
    total_images = Image.objects.all().count()
    human_annotations = Point.objects.filter(image__status__annotatedByHuman=True).count()
    robot_annotations = Point.objects.filter(image__status__annotatedByRobot=True).count()
    total_annotations = human_annotations + robot_annotations

    return render(request, 'lib/index.html', {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'map_sources': map_sources,
        'total_sources': total_sources,
        'total_images': total_images,
        'total_annotations': total_annotations,
        'human_annotations': human_annotations,
        'robot_annotations' : robot_annotations,
        'images': images,
        'list_thumbnails': list_thumbnails,
    })

def handler500(request, template_name='500.html'):
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        return HttpResponseServerError('<h1>Server Error (500)</h1>', content_type='text/html')
    return HttpResponseServerError(template.render({
        'request': request,
    }))


@permission_required('is_superuser')
def nav_test(request, source_id):
    """
    Test page for a new navigation header layout.
    """
    source = get_object_or_404(Source, id=source_id)
    return render(request, 'lib/nav_test.html', {
        'source': source,
    })