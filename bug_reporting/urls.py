from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'$', 'bug_reporting.views.feedback_form', name="feedback_form"),
)
