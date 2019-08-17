from __future__ import unicode_literals

from django.conf import settings
from django.core import mail
from django.urls import reverse

from lib.test_utils import ClientTest


class EmailAllTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EmailAllTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.inactive_user = cls.create_user(activate=False)

    def test_load_page_anonymous(self):
        """Load page while logged out -> login page."""
        response = self.client.get(reverse('emailall'))
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL)+'?next='+reverse('emailall'),
        )

    def test_load_page_normal_user(self):
        """Load page as normal user -> login page."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('emailall'))
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL)+'?next='+reverse('emailall'),
        )

    def test_load_page_superuser(self):
        """Load page as superuser -> page loads normally."""
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('emailall'))
        self.assertTemplateUsed(response, 'accounts/email_all_form.html')

    def test_submit(self):
        """Test submitting the form."""
        self.client.force_login(self.superuser)
        self.client.post(reverse('emailall'), data=dict(
            subject="Subject goes here",
            body="Body\ngoes here.",
        ))

        # Check that an email was sent.
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[-1]

        # Check that the email has the expected recipients:
        # the superuser and the active user.
        # The inactive user, and special users like robot, should be excluded.
        self.assertSetEqual(
            set(sent_email.bcc),
            {self.user.email, self.superuser.email})

        # Check subject and message.
        self.assertEqual(sent_email.subject, "Subject goes here")
        self.assertEqual(sent_email.body, "Body\ngoes here.")
