from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

from userena.decorators import secure_required

from .forms import UserAddForm, EmailAllForm


@secure_required
@permission_required('is_superuser')
def user_add(request):
    """
    Add a user using a subclass of Userena's SignupForm,
    which takes care of Profile creation, adding necessary
    user permissions, password generation, and sending an
    activation email.

    The only reason this doesn't use userena.views.signup is
    that userena.views.signup logs out the current user (the
    admin user) after a user is added. (That makes sense for
    creating an account for yourself, but not for creating
    someone else's account.)
    """
    form = UserAddForm(request_host=request.get_host())
    
    if request.method == 'POST':
        form = UserAddForm(
            request.POST, request.FILES, request_host=request.get_host())
        if form.is_valid():
            user = form.save()

            redirect_to = reverse(
                'userena_signup_complete',
                kwargs={'username': user.username}
            )
            return redirect(redirect_to)

    return render(request, 'accounts/user_add_form.html', {
        'form': form,
    })


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


def userena_password_change(request, username):
    return HttpResponseRedirect(reverse('password_change'))


def userena_password_change_done(request, username):
    return HttpResponseRedirect(reverse('password_change_done'))