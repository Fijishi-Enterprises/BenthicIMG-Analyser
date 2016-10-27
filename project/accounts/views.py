from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.shortcuts import render

from .forms import EmailAllForm


@permission_required('is_superuser')
def email_all(request):
    """View for sending an email to all registered users."""
    if request.method == 'POST':
        form = EmailAllForm(request.POST)

        if form.is_valid():
            all_users = User.objects.all()
            email_list = []
            for u in all_users:
                if u.email:
                    email_list.append(u.email)

            email = EmailMessage(
                subject=form.cleaned_data['subject'],
                body=form.cleaned_data['body'],
                # BLIND-cc the users to not reveal
                # everyone's emails to everyone else.
                bcc=email_list,
            )
            email.send()

            messages.success(request, "Successfully sent emails.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EmailAllForm()

    return render(request, 'accounts/email_all_form.html', {
        'form': form,
    })
