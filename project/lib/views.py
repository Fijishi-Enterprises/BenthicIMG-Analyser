from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.mail import mail_admins
from django.core.mail.message import BadHeaderError
from django.http import HttpResponseRedirect, HttpResponseServerError
from django.shortcuts import render, get_object_or_404
from django.template import loader, TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe

from annotations.utils import get_sitewide_annotation_count
from images.models import Image, Source
from images.utils import get_map_sources, get_carousel_images
from lib.forms import ContactForm


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

            # We will send a plain-text email.
            # So when passing the subject and message as template variables,
            # we have to use mark_safe() so that characters like quote marks
            # don't get HTML-escaped.
            subject = render_to_string('lib/contact_subject.txt', dict(
                username=username,
                base_subject=mark_safe(base_subject),
            ))
            message = render_to_string('lib/contact_email.txt', dict(
                username=username,
                user_email=user_email,
                base_message=mark_safe(base_message),
            ))

            # Send the mail.
            try:
                mail_admins(
                    subject=subject,
                    message=message,
                )
            except BadHeaderError:
                messages.error(
                    request,
                    "Sorry, the email could not be sent."
                    " It didn't pass a security check."
                )
            else:
                messages.success(request, "Your email was sent to the admins!")
                return HttpResponseRedirect(reverse('index'))
        else:
            messages.error(request, "Please correct the errors below.")

    else:  # GET
        contact_form = ContactForm(request.user)

    return render(request, 'lib/contact.html', {
        'contact_form': contact_form,
    })


def index(request):
    """
    This view renders the front page.
    """
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('source_list'))

    map_sources = get_map_sources()
    carousel_images = get_carousel_images()

    # Gather some stats
    total_sources = Source.objects.all().count()
    total_images = Image.objects.all().count()
    total_annotations = get_sitewide_annotation_count()

    return render(request, 'lib/index.html', {
        'map_sources': map_sources,
        'total_sources': total_sources,
        'total_images': total_images,
        'total_annotations': total_annotations,
        'carousel_images': carousel_images,
    })


def handler500(request, template_name='500.html'):
    try:
        template = loader.get_template(template_name)
    except TemplateDoesNotExist:
        return HttpResponseServerError(
            '<h1>Server Error (500)</h1>', content_type='text/html')
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
