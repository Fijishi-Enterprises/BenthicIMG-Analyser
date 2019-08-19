from __future__ import unicode_literals

from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils.html import escape

from lib.test_utils import ClientTest


class SignOutTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(SignOutTest, cls).setUpTestData()

        cls.user = cls.create_user()

    def test_load_page_anonymous(self):
        response = self.client.get(reverse('logout'), follow=True)
        self.assertTemplateUsed(
            response, 'registration/logged_out.html',
            "Can still visit the signout page while already signed out; it"
            " just doesn't do anything")

    def test_sign_out(self):
        self.client.force_login(self.user)
        # Signed in
        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.get(reverse('logout'), follow=True)
        self.assertTemplateUsed(response, 'registration/logged_out.html')
        # Signed out
        self.assertNotIn('_auth_user_id', self.client.session)


class PasswordChangeTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(PasswordChangeTest, cls).setUpTestData()

        cls.user = cls.create_user('sampleUsername', 'oldPassword')

    def test_load_page_anonymous(self):
        """The view only makes sense for registered users."""
        response = self.client.get(reverse('password_change'), follow=True)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_load_page_signed_in(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('password_change'), follow=True)
        self.assertTemplateUsed(
            response, 'registration/password_change_form.html')

    def test_change_success(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('password_change'),
            dict(
                old_password='oldPassword',
                new_password1='newPassword',
                new_password2='newPassword',
            ),
            follow=True,
        )
        self.assertTemplateUsed(
            response, 'registration/password_change_done.html')

        # Check that the password has changed: attempt to log in with the
        # new password, and check that we're signed in as the expected user.
        self.client.logout()
        self.client.login(username='sampleUsername', password='newPassword')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_old_password_incorrect(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('password_change'),
            dict(
                old_password='OLDPASSWORD',
                new_password1='newPassword',
                new_password2='newPassword',
            ),
            follow=True,
        )
        self.assertTemplateUsed(
            response, 'registration/password_change_form.html')
        self.assertContains(
            response,
            "Your old password was entered incorrectly."
            " Please enter it again.")

        # Check that the password has not changed: the old password still
        # works.
        self.client.logout()
        self.client.login(username='sampleUsername', password='oldPassword')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_new_password_mismatch(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('password_change'),
            dict(
                old_password='oldPassword',
                new_password1='newPassword',
                new_password2='newPassWORD',
            ),
            follow=True,
        )
        self.assertTemplateUsed(
            response, 'registration/password_change_form.html')
        self.assertContains(
            response,
            escape("The two password fields didn't match."))

        # Check that the password has not changed.
        self.client.logout()
        self.client.login(username='sampleUsername', password='oldPassword')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_invalid_new_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('password_change'),
            dict(
                old_password='oldPassword',
                new_password1='newPass',
                new_password2='newPass',
            ),
            follow=True,
        )
        self.assertTemplateUsed(
            response, 'registration/password_change_form.html')
        self.assertContains(
            response,
            "This password is too short. It must contain at least"
            " 10 characters.")

        # Check that the password has not changed.
        self.client.logout()
        self.client.login(username='sampleUsername', password='oldPassword')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)


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
