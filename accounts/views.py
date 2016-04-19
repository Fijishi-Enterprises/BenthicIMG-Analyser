from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render

from userena.decorators import secure_required

from accounts.forms import UserAddForm
from lib.decorators import permission_required


@secure_required
@permission_required('auth.add_user')
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
    """Sends an email to all registered users."""
    status = None
    if request.method == 'POST':
        subject = request.REQUEST.get('subject').encode("ascii")
        message = request.REQUEST.get('message').encode("ascii")
        if not subject or not message:
            return render(request, 'accounts/email_all_form.html')
        
        all_users = User.objects.all()
        email_list = []
        for u in all_users:
            if u.email:
                email_list.append(u.email.encode("ascii") )
        email = EmailMessage(subject, message, settings.SERVER_EMAIL,
        [], bcc=email_list )
  
        email.send(fail_silently=True)
        status = "Successfully Sent Emails"

    return render(request, 'accounts/email_all_form.html', {
        'status': status,
    })
