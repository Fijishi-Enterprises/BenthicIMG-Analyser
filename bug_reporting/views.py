from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render

from bug_reporting.forms import FeedbackForm
from bug_reporting.models import Feedback

@login_required
def feedback_form(request):
    """
    Feedback form.
    Get here either from a link from the 500 error page, or from
    the feedback link that's on any page when the user's logged in.
    """

    if request.method == 'POST':

        f = Feedback(user=request.user, url=str(request.GET.get('ref', '')))
        # Later, might also auto-set browser, OS, etc. here
        form = FeedbackForm(request.POST, instance=f)

        if form.is_valid():
            form.save()
            return render(request, 'bug_reporting/thanks.html')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Just reached this form page
        form = FeedbackForm()
    return render(request, 'bug_reporting/feedback_form.html', {
        'form': form,
    })
