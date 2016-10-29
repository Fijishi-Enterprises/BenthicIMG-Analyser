from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView

from registration.backends.hmac.views \
    import RegistrationView as BaseRegistrationView

from lib.forms import LoginRequiredMixin
from .forms import EmailChangeForm, EmailAllForm

User = get_user_model()


class RegistrationView(BaseRegistrationView):
    success_url = 'registration_complete'

    def form_valid(self, form):
        email = form.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            existing_user = User.objects.get(email=email)
            self.send_already_exists_email(existing_user, email)
        else:
            self.register(form)

        return redirect(self.success_url)

    def send_already_exists_email(self, existing_user, email_address):
        context = dict(username=existing_user.username)

        subject = render_to_string(
            'registration/registration_email_exists_subject.txt', context)
        # Force subject to a single line to avoid header-injection issues.
        subject = ''.join(subject.splitlines())
        message = render_to_string(
            'registration/registration_email_exists_email.txt', context)

        already_exists_email = EmailMessage(
            subject=subject,
            body=message,
            to=[email_address],
        )
        already_exists_email.send()


class EmailChangeView(LoginRequiredMixin, FormView):
    form_class = EmailChangeForm
    success_url = 'email_change_done'
    template_name = 'accounts/email_change_form.html'

    def form_valid(self, form):
        self.send_confirmation_email(form.cleaned_data['email'])
        self.send_notice_email_to_old_address(form.cleaned_data['email'])
        return redirect(self.success_url)

    def send_confirmation_email(self, pending_email_address):
        confirmation_key = self.get_confirmation_key(
            self.request.user, pending_email_address)
        context = dict(
            username=self.request.user.username,
            confirmation_key=confirmation_key,
            expiration_hours=settings.EMAIL_CHANGE_CONFIRMATION_HOURS,
            site=get_current_site(self.request),
        )

        subject = render_to_string(
            'accounts/email_change_confirmation_subject.txt', context)
        # Force subject to a single line to avoid header-injection issues.
        subject = ''.join(subject.splitlines())

        message = render_to_string(
            'accounts/email_change_confirmation_email.txt', context)

        confirmation_email = EmailMessage(
            subject=subject,
            body=message,
            to=[pending_email_address],
        )
        confirmation_email.send()

    def get_confirmation_key(self, user, pending_email_address):
        return signing.dumps(obj=dict(
            pk=user.pk,
            email=pending_email_address,
        ))

    def send_notice_email_to_old_address(self, pending_email_address):
        context = dict(
            username=self.request.user.username,
            pending_email_address=pending_email_address,
            expiration_hours=settings.EMAIL_CHANGE_CONFIRMATION_HOURS,
            site=get_current_site(self.request),
        )

        subject = render_to_string(
            'accounts/email_change_notice_subject.txt', context)
        # Force subject to a single line to avoid header-injection issues.
        subject = ''.join(subject.splitlines())

        message = render_to_string(
            'accounts/email_change_notice_email.txt', context)

        confirmation_email = EmailMessage(
            subject=subject,
            body=message,
            to=[self.request.user.email],
        )
        confirmation_email.send()


class EmailChangeConfirmView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/email_change_confirm.html'
    success_url = 'email_change_complete'

    def get(self, *args, **kwargs):
        confirmed = self.confirm_email_change(*args, **kwargs)
        if confirmed:
            return redirect(self.success_url)
        return super(EmailChangeConfirmView, self).get(*args, **kwargs)

    def confirm_email_change(self, *args, **kwargs):
        new_email_address = self.validate_key(kwargs.get('confirmation_key'))
        if new_email_address is not None:
            user = self.request.user
            user.email = new_email_address
            user.save()
            return True
        return False

    def validate_key(self, confirmation_key):
        try:
            obj = signing.loads(
                confirmation_key,
                max_age=settings.EMAIL_CHANGE_CONFIRMATION_HOURS * 60 * 60,
            )
        # SignatureExpired is a subclass of BadSignature, so this will
        # catch either one.
        except signing.BadSignature:
            return None

        # Check that the signed-in user is the same as the user who sent
        # the email change request.
        if self.request.user.pk != obj['pk']:
            return None

        # Return the new email address (which we got by un-signing the
        # confirmation key).
        return obj['email']


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
