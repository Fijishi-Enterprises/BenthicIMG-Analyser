from django.conf import settings
from django.core.mail import mail_admins
from django.core.mail.message import BadHeaderError
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib import messages
from requests.forms import RequestInviteForm
import urllib2, urllib

def request_invite(request):

     #messages = []

     if request.method == 'POST':
        form = RequestInviteForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data.pop('email')
            username = form.cleaned_data.pop('username')
            firstname = form.cleaned_data.pop('first_name')
            lastname = form.cleaned_data.pop('last_name')
            reason = form.cleaned_data.pop('reason_for_requesting_an_account')
            affiliation = form.cleaned_data.pop('affiliation')
            project_description = form.cleaned_data.pop('project_description')
            how_did_you_hear_about_us = form.cleaned_data.pop('how_did_you_hear_about_us')
            policy_agree = form.cleaned_data.pop('agree_to_data_policy')
            response_field =  request.POST.get("recaptcha_response_field")
            challenge_field = request.POST.get("recaptcha_challenge_field") 
            
            try:
                client_ip = request.META['HTTP_X_FORWARDED_FOR']
            except:
                client_ip = request.META['REMOTE_ADDR']
            print client_ip

            message = 'Email: ' + email + '\n' + \
                      'Username: ' + username + '\n' + \
                      'First name: ' + firstname + '\n' + \
                      'Last name: ' + lastname + '\n' + \
                      'Reason: ' + reason + '\n' + \
                      'affiliation: ' + affiliation + '\n' + \
                      'project_description: ' + project_description +'\n'+\
                      'how_did_you_hear_about_us: ' + how_did_you_hear_about_us + '\n'+\
                      'agree_to_data_policy: ' + str(policy_agree) + '\n'

            params = urllib.urlencode ({
              'privatekey': encode_if_necessary(settings.CAPTCHA_PRIVATE_KEY),
              'remoteip' :  encode_if_necessary(client_ip),
              'challenge':  encode_if_necessary(challenge_field),
              'response' :  encode_if_necessary(response_field),
            })

            captcha_verify = urllib2.Request (
                url = "http://www.google.com/recaptcha/api/verify",
                data = params,
                headers = {
                    "Content-type": "application/x-www-form-urlencoded",
                    "User-agent": "CoralNet"
                }
            )
    
            httpresp = urllib2.urlopen (captcha_verify)
            return_values = httpresp.read ().splitlines ();
            httpresp.close();
            return_code = return_values [0]

            try:
               if (return_code == "true"):
                   mail_admins('User Account Requested', message)
                   messages.success(request, 'Your request was sent!')
                   # messages.append('Your request was sent!')
                   return HttpResponseRedirect(reverse('request_account_confirm'))
               else:
                   messages.error(request, 'Invalid Captcha')
            except BadHeaderError:
                messages.append('Invalid header found.')

        else:
            messages.error(request, 'Make sure all fields are entered and valid.')
     else:
        form = RequestInviteForm()

     
     return render(request, 'requests/request_invite.html', {
        'form': form,
        'public_key': settings.CAPTCHA_PUBLIC_KEY,
    })


def encode_if_necessary(s):
    if isinstance(s, unicode):
        return s.encode('utf-8')
    return s



def request_invite_confirm(request):
    return render(request, 'requests/request_invite_received.html')