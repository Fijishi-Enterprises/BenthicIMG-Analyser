# Tests for non-app-specific pages.
from unittest import skipIf

from django.conf import settings
from django.core import mail
from django.core.urlresolvers import reverse
from django.shortcuts import resolve_url
from django.utils.html import escape
from django.test.utils import override_settings

from .test_utils import BaseTest, ClientTest
from .utils import direct_s3_write, direct_s3_read


class IndexTest(ClientTest):
    """
    Test the site index page.
    """
    def test_load_page_anonymous(self):
        response = self.client.get(reverse('index'))
        self.assertTemplateUsed(response, 'lib/index.html')


@skipIf(not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3', "Can't run backend tests locally")
class DirectS3Test(BaseTest):
    """
    Test the direct s3 read and write tests.
    """
    @classmethod
    def setUpTestData(cls):
        super(DirectS3Test, cls).setUpTestData()

    def test_write_and_read(self):
        var = {'A':10, 'B':20}
        for enc in ['json', 'pickle']:
            direct_s3_write('testkey', enc, var)
            var_recovered = direct_s3_read('testkey', enc)
            self.assertEqual(var, var_recovered)


@override_settings(
    ADMINS=[
        ('Admin One', 'admin1@example.com'),
        ('Admin Two', 'admin2@example.com'),
    ],
    EMAIL_SUBJECT_PREFIX="[Sample prefix] "
)
class ContactTest(ClientTest):
    """
    Test the Contact Us page.
    """
    @classmethod
    def setUpTestData(cls):
        super(ContactTest, cls).setUpTestData()

        cls.user = cls.create_user(username='sample_user')

    def test_load_page_anonymous(self):
        response = self.client.get(reverse('contact'))
        self.assertTemplateUsed(response, 'lib/contact.html')

    def test_load_page_registered(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('contact'))
        self.assertTemplateUsed(response, 'lib/contact.html')

    def test_send_email_as_user(self):
        """
        Logged-in user successfully sends a contact email.
        """
        self.client.force_login(self.user)

        # Submit the form
        subject = "Subject goes here"
        message = "Message\ngoes here."
        response = self.client.post(
            reverse('contact'),
            dict(subject=subject, message=message),
        )

        # Check that we get redirected to the index page now.
        # This might redirect somewhere else. We really don't care here, but
        # assertRedirects() does care, so the code looks a bit weird.
        try:
            self.assertRedirects(response, reverse('index'))
        except AssertionError:
            self.assertRedirects(
                response, reverse('index'), target_status_code=302)

        # Check that 1 email was sent.
        self.assertEqual(len(mail.outbox), 1)
        contact_email = mail.outbox[0]

        # Check that the email's "to" field is equal to settings.ADMINS.
        self.assertListEqual(
            contact_email.to,
            ['admin1@example.com', 'admin2@example.com'])

        # Check the subject.
        self.assertEqual(
            contact_email.subject,
            "[Sample prefix] Contact Us - sample_user - Subject goes here")

        # Check the message/body.
        self.assertIn('sample_user', contact_email.body)
        self.assertIn(self.user.email, contact_email.body)
        self.assertIn(message, contact_email.body)

    def test_send_email_as_guest(self):
        """
        Non-logged-in user successfully sends a contact email.
        """
        # Submit the form
        subject = "Subject goes here"
        message = "Message\ngoes here."
        email = 'email@goeshere.com'
        response = self.client.post(
            reverse('contact'),
            dict(subject=subject, message=message, email=email),
        )

        try:
            self.assertRedirects(response, reverse('index'))
        except AssertionError:
            self.assertRedirects(
                response, reverse('index'), target_status_code=302)

        # Check that 1 email was sent.
        self.assertEqual(len(mail.outbox), 1)
        contact_email = mail.outbox[0]

        # Check that the email's "to" field is equal to settings.ADMINS.
        self.assertListEqual(
            contact_email.to,
            ['admin1@example.com', 'admin2@example.com'])

        # Check the subject.
        self.assertEqual(
            contact_email.subject,
            "[Sample prefix] Contact Us - [A guest] - Subject goes here")

        # Check the message/body.
        self.assertIn('[A guest]', contact_email.body)
        self.assertIn('email@goeshere.com', contact_email.body)
        self.assertIn(message, contact_email.body)

    def test_success_message(self):
        # As guest.
        response = self.client.post(
            reverse('contact'),
            dict(subject="A", message="A", email='a@a.com'),
            follow=True,
        )
        self.assertContains(response, "Your email was sent to the admins!")

        # As registered user.
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('contact'),
            dict(subject="A", message="A"),
            follow=True,
        )
        self.assertContains(response, "Your email was sent to the admins!")

    def test_contact_error_required_fields(self):
        # Message is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="A", message="", email='email@goeshere.com',
        ))
        # Should be back on the form page with an error.
        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(response, "This field is required.")

        # Subject is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="", message="A", email='email@goeshere.com',
        ))
        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(response, "This field is required.")

        # Email is missing.
        response = self.client.post(reverse('contact'), dict(
            subject="A", message="A", email='',
        ))
        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(response, "This field is required.")

    def test_contact_error_char_limit(self):
        self.client.force_login(self.user)

        # Subject too long.
        response = self.client.post(reverse('contact'), dict(
            subject="1"*56, message="A",
            email='email@goeshere.com',
        ))
        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(
            response,
            "Ensure this value has at most 55 characters (it has 56).")

        # Message too long.
        response = self.client.post(reverse('contact'), dict(
            subject="A", message="1"*5001,
            email='email@goeshere.com',
        ))
        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(
            response,
            "Ensure this value has at most 5000 characters (it has 5001).")

    def test_contact_no_html_escaping(self):
        """
        We had a problem before where characters like quotes and angle
        brackets would become HTML entities like &#39; - in a plain-text email.
        Here we check that this doesn't happen.
        """
        self.client.force_login(self.user)
        self.client.post(reverse('contact'), dict(
            subject="""'test' "test" <test>""",
            message="""'test2' "test2" <test2>""",
            email='email@goeshere.com',
        ))

        contact_email = mail.outbox[0]
        self.assertIn(
            """'test' "test" <test>""",
            contact_email.subject)
        self.assertIn(
            """'test2' "test2" <test2>""",
            contact_email.body)

    def test_bad_header_error(self):
        """Test for a BadHeaderError case."""
        self.client.force_login(self.user)

        response = self.client.post(reverse('contact'), dict(
            subject="Subject goes here\ncc:spamvictim@example.com",
            message="Message goes here",
        ))

        self.assertTemplateUsed(response, 'lib/contact.html')
        self.assertContains(
            response, escape(
                "Sorry, the email could not be sent."
                " It didn't pass a security check."
            ))


class GoogleAnalyticsTest(ClientTest):
    """
    Testing the google analytics java script plugin.
    """
    @classmethod
    def setUpTestData(cls):
        super(GoogleAnalyticsTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.source = cls.create_source(cls.user)
    
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
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('about'))
        self.assertContains(response, 'Goggle Analytics not included because you are a staff user!')

    @override_settings(GOOGLE_ANALYTICS_CODE = 'dummy-gacode')
    def test_in_source(self):
        """
        Make sure the ga plugin renders on a source page
        """
        self.client.force_login(self.user)
        response = self.client.get(resolve_url('browse_images', self.source.pk))
        self.assertContains(response, 'google-analytics.com/ga.js')
