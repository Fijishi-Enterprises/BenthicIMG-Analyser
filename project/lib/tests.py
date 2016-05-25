# Tests for non-app-specific pages.
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail, validators
from django.core.urlresolvers import reverse
from lib import msg_consts, str_consts
from lib.forms import ContactForm
from lib.test_utils import ClientTest
from images.models import Source
from django.test.utils import override_settings

class IndexTest(ClientTest):
    """
    Test the site index page.
    """
    fixtures = ['test_users.yaml']

    def test_index(self):
        response = self.client.get(reverse('index'))
        self.assertStatusOK(response)


class ContactTest(ClientTest):
    """
    Test the Contact Us page.
    """
    fixtures = ['test_users.yaml']

    def test_access_page(self):
        """
        Access the page without errors.
        """
        response = self.client.get(reverse('contact'))
        self.assertStatusOK(response)

    def test_send_email_as_user(self):
        """
        Logged-in user successfully sends a contact email.
        """
        username = 'user2'
        user_email = User.objects.get(username='user2').email
        self.client.login(username=username, password='secret')

        # Reach the page
        response = self.client.get(reverse('contact'))
        self.assertStatusOK(response)

        # Submit the form
        subject = "Subject goes here"
        message = "Message\ngoes here."
        response = self.client.post(
            reverse('contact'),
            dict(subject=subject, message=message),
        )

        # Check that we get redirected to the index page now.
        # This WILL redirect to another page. We won't take further steps to
        # test which page that is. That's the index logic, not the contact logic.
        self.assertRedirects(response, reverse('index'), target_status_code=302)

        # Check that 1 email was sent.
        self.assertEqual(len(mail.outbox), 1)
        contact_email = mail.outbox[0]

        # Check that the email's "to" field is equal to settings.ADMINS.
        self.assertEqual(len(contact_email.to), len(settings.ADMINS))
        for admin_name, admin_email in settings.ADMINS:
            self.assertIn(admin_email, contact_email.to)

        # Check the subject.
        self.assertEqual(
            contact_email.subject,
            "{prefix}{unprefixed_subject}".format(
                prefix=settings.EMAIL_SUBJECT_PREFIX,
                unprefixed_subject=str_consts.CONTACT_EMAIL_SUBJECT_FMTSTR.format(
                    username=username,
                    base_subject=subject,
                )
            ),
        )
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Email subject:\n{subject}".format(subject=contact_email.subject)

        # Check the message/body.
        self.assertEqual(
            contact_email.body,
            str_consts.CONTACT_EMAIL_MESSAGE_FMTSTR.format(
                username=username,
                user_email=user_email,
                base_message=message,
            ),
        )
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Email message:\n{message}".format(message=contact_email.body)

    def test_send_email_as_guest(self):
        """
        Non-logged-in user successfully sends a contact email.
        """
        # Reach the page
        response = self.client.get(reverse('contact'))
        self.assertStatusOK(response)

        # Submit the form
        subject = "Subject goes here"
        message = "Message\ngoes here."
        email = "email@goeshere.com"
        response = self.client.post(
            reverse('contact'),
            dict(subject=subject, message=message, email=email),
        )

        # Check that we get redirected to the index page now.
        self.assertRedirects(response, reverse('index'), target_status_code=200)

        # Check that 1 email was sent.
        self.assertEqual(len(mail.outbox), 1)
        contact_email = mail.outbox[0]

        # Check that the email's "to" field is equal to settings.ADMINS.
        self.assertEqual(len(contact_email.to), len(settings.ADMINS))
        for admin_name, admin_email in settings.ADMINS:
            self.assertIn(admin_email, contact_email.to)

        # Check the subject.
        self.assertEqual(
            contact_email.subject,
            "{prefix}{unprefixed_subject}".format(
                prefix=settings.EMAIL_SUBJECT_PREFIX,
                unprefixed_subject=str_consts.CONTACT_EMAIL_SUBJECT_FMTSTR.format(
                    username="[A guest]",
                    base_subject=subject,
                )
            ),
        )
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Email subject:\n{subject}".format(subject=contact_email.subject)

        # Check the message/body.
        self.assertEqual(
            contact_email.body,
            str_consts.CONTACT_EMAIL_MESSAGE_FMTSTR.format(
                username="[A guest]",
                user_email=email,
                base_message=message,
            ),
        )
        if settings.UNIT_TEST_VERBOSITY >= 1:
            print "Email message:\n{message}".format(message=contact_email.body)

    def test_success_message(self):
        """
        After sending the form, check for a top-of-page message indicating success.
        """
        # Reach the page
        response = self.client.get(reverse('contact'))
        self.assertStatusOK(response)

        # Submit the form
        subject = "Subject goes here"
        message = "Message\ngoes here."
        email = "email@goeshere.com"
        response = self.client.post(
            reverse('contact'),
            dict(subject=subject, message=message, email=email),
            # Ensure we get the response after the final redirect. This way we'll
            # have access to response.context's messages.
            follow=True,
        )

        # Check that we got the expected top-of-page message.
        self.assertMessages(
            response,
            [msg_consts.CONTACT_EMAIL_SENT],
        )

    def test_contact_error_required(self):
        """
        'field is required' errors.
        """
        # Message is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="Subject goes here",
            message="",
            email="email@goeshere.com",
        ))
        self.assertStatusOK(response)
        self.assertMessages(response, [msg_consts.FORM_ERRORS])
        self.assertFormErrors(response, 'contact_form', {
            'message': [forms.Field.default_error_messages['required']],
        })

        # Subject is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="",
            message="Message\ngoes here.",
            email="email@goeshere.com",
        ))
        self.assertStatusOK(response)
        self.assertMessages(response, [msg_consts.FORM_ERRORS])
        self.assertFormErrors(response, 'contact_form', {
            'subject': [forms.Field.default_error_messages['required']],
        })

        # Email is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="Subject goes here",
            message="Message\ngoes here.",
            email="",
        ))
        self.assertStatusOK(response)
        self.assertMessages(response, [msg_consts.FORM_ERRORS])
        self.assertFormErrors(response, 'contact_form', {
            'email': [forms.Field.default_error_messages['required']],
        })

    def test_contact_error_char_limit(self):
        """
        'ensure at most x chars' errors.
        """
        self.client.login(username='user2', password='secret')

        subject_max_length = ContactForm.base_fields['subject'].max_length
        message_max_length = ContactForm.base_fields['message'].max_length

        # Subject and message are too long.
        response = self.client.post(reverse('contact'), dict(
            subject="1"*(subject_max_length+1),
            message="1"*(message_max_length+1),
        ))
        self.assertStatusOK(response)
        self.assertMessages(response, [msg_consts.FORM_ERRORS])
        self.assertFormErrors(response, 'contact_form', {
            'subject': [validators.MaxLengthValidator.message % {
                'limit_value': subject_max_length,
                'show_value': subject_max_length+1,
            }],
            'message': [validators.MaxLengthValidator.message % {
                'limit_value': message_max_length,
                'show_value': message_max_length+1,
            }],
        })

class GoogleAnalyticsTest(ClientTest):
    """
    Testing the google analytics java script plugin.
    """
    fixtures = ['test_users.yaml', 'test_sources.yaml']
    
    @override_settings(GOOGLE_ANALYTICS_CODE = 'dummy-gacode')
    def test_simple(self):
        """
        Test that ga code is being generated. And that it contains the GOOGLE_ANALYTICS_CODE.
        """
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'google-analytics.com/ga.js')
        self.assertContains(response, settings.GOOGLE_ANALYTICS_CODE)

    @override_settings(GOOGLE_ANALYTICS_CODE = '')
    def test_missing(self):
        """
        Test what happens if the GOOGLE_ANALYTICS_CODE is not set
        """
        del settings.GOOGLE_ANALYTICS_CODE
        response = self.client.get(reverse('about'))
        self.assertContains(response, "Goggle Analytics not included because you haven't set the settings.GOOGLE_ANALYTICS_CODE variable!")

    
    @override_settings(DEBUG=True)
    def test_debug(self):
        """
        Do not include google analytics if in DEBUG mode.
        """
        response = self.client.get(reverse('about'))
        self.assertContains(response, 'Goggle Analytics not included because you are in Debug mode!')

    def test_staffuser(self):
        """
        Do not inlude google analytics if in superuser mode.
        """
        self.client.login(username='superuser_user', password='secret')
        response = self.client.get(reverse('about'))
        self.assertContains(response, 'Goggle Analytics not included because you are a staff user!')

    @override_settings(GOOGLE_ANALYTICS_CODE = 'dummy-gacode')
    def test_in_source(self):
        """
        Make sure the ga plugin renders on a source page
        """
        source_id = Source.objects.get(name='private1').pk
        self.client.login(username='user2', password='secret')
        response = self.client.get(reverse('visualize_source', kwargs=dict(source_id = source_id)))
        self.assertContains(response, 'google-analytics.com/ga.js')


    # TODO: How to test for a BadHeaderError?
    # Putting a newline in the subject isn't getting such an error.

#        self.client.login(username='user2', password='secret')
#
#        response = self.client.post(reverse('contact'), dict(
#            subject="Subject goes here\ncc:spamvictim@example.com",
#            message="Message goes here",
#        ))
#
#        self.assertStatusOK(response)
#        self.assertMessages(response, [msg_consts.EMAIL_BAD_HEADER])