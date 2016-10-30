import time
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.urlresolvers import reverse
from django.utils.html import escape
from lib.test_utils import ClientTest

User = get_user_model()


class SignInTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(SignInTest, cls).setUpTestData()

        cls.user = cls.create_user(
            username='testUsername', password='testPassword',
            email='tester@example.org')

    def test_load_page(self):
        response = self.client.get(reverse('auth_login'))
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_load_page_when_signed_in(self):
        """
        Can still reach the sign-in page as a signed in user. There's not
        a major use case, but nothing inherently wrong with it either.
        """
        self.client.force_login(self.user)
        response = self.client.get(reverse('auth_login'))
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_sign_in_by_username(self):
        response = self.client.post(reverse('auth_login'), dict(
            username='testUsername', password='testPassword',
        ))

        # We should be past the sign-in page now.
        self.assertTemplateNotUsed(response, 'registration/login.html')

        # Check that we're signed in as the expected user.
        # From http://stackoverflow.com/a/6013115
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_sign_in_by_email(self):
        response = self.client.post(reverse('auth_login'), dict(
            username='tester@example.org', password='testPassword',
        ))

        # We should be past the sign-in page now.
        self.assertTemplateNotUsed(response, 'registration/login.html')

        # Check that we're signed in as the expected user.
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_nonexistent_username(self):
        response = self.client.post(reverse('auth_login'), dict(
            username='notAUsername', password='testPassword',
        ))
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(
            response,
            "The credentials you entered did not match our records."
            " Note that both fields may be case-sensitive.")

    def test_username_case_insensitive(self):
        # Different case on username = still succeeds.
        response = self.client.post(reverse('auth_login'), dict(
            username='TESTUSERNAME', password='testPassword',
        ))
        self.assertTemplateNotUsed(response, 'registration/login.html')

        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.user.pk)

    def test_nonexistent_email(self):
        response = self.client.post(reverse('auth_login'), dict(
            username='notanemail@example.org', password='testPassword',
        ))
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(
            response,
            "The credentials you entered did not match our records."
            " Note that both fields may be case-sensitive.")

    def test_email_case_sensitive(self):
        # Different case on email = failure.
        response = self.client.post(reverse('auth_login'), dict(
            username='TESTER@example.org', password='testPassword',
        ))
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(
            response,
            "The credentials you entered did not match our records."
            " Note that both fields may be case-sensitive.")

    def test_wrong_password(self):
        response = self.client.post(reverse('auth_login'), dict(
            username='testUsername', password='testPassWORD',
        ))
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(
            response,
            "The credentials you entered did not match our records."
            " Note that both fields may be case-sensitive.")

    def test_sign_in_fail_if_user_inactive(self):
        # Register but don't activate.
        self.client.post(reverse('registration_register'), dict(
            username='alice',
            email='alice123@example.com',
            password1='GreatBarrier',
            password2='GreatBarrier',
        ))

        # Attempt to sign in as the new user.
        response = self.client.post(reverse('auth_login'), dict(
            username='alice',
            password='GreatBarrier',
        ))
        # Should not work (we should still be at the login page with an error).
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(response, "This account is inactive.")

    # TODO: Add tests for getting redirected to the expected page
    # (about sources, source list, or whatever was in the 'next' URL
    # parameter).


class BaseRegisterTest(ClientTest):

    default_post = dict(
        username='alice',
        email='alice123@example.com',
        password1='GreatBarrier',
        password2='GreatBarrier',
    )

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(BaseRegisterTest, cls).setUpTestData()

        cls.user = cls.create_user()

    def register_and_get_activation_link(self):
        """Shortcut function for tests focusing on the activation step."""
        self.client.post(reverse('registration_register'), self.default_post)

        activation_email = mail.outbox[-1]
        # Activation link: should be the first link (first "word" with '://')
        # in the activation email.
        activation_link = None
        for word in activation_email.body.split():
            if '://' in word:
                activation_link = word
                break
        self.assertIsNotNone(activation_link)

        return activation_link


class RegisterTest(BaseRegisterTest):

    def test_load_page(self):
        response = self.client.get(reverse('registration_register'))
        self.assertTemplateUsed(response, 'registration/registration_form.html')

    def test_load_page_when_signed_in(self):
        """
        Can still reach the register page as a signed in user. There's not
        a major use case, but nothing inherently wrong with it either.
        """
        self.client.force_login(self.user)
        response = self.client.get(reverse('registration_register'))
        self.assertTemplateUsed(response, 'registration/registration_form.html')

    def test_success(self):
        response = self.client.post(
            reverse('registration_register'), self.default_post, follow=True)
        self.assertTemplateUsed(
            response, 'registration/registration_complete.html')

        # Check that an activation email was sent.
        self.assertEqual(len(mail.outbox), 1)
        # Check that the intended recipient is the only recipient.
        activation_email = mail.outbox[-1]
        self.assertEqual(len(activation_email.to), 1)
        self.assertEqual(activation_email.to[0], 'alice123@example.com')

        # Check that the new user exists, but is inactive.
        user = User.objects.get(username='alice', email='alice123@example.com')
        self.assertFalse(user.is_active)

    def test_username_already_exists(self):
        # Register once.
        self.client.post(reverse('registration_register'), self.default_post)
        # Register again with the same username, but different other fields.
        response = self.client.post(reverse('registration_register'), dict(
            username='alice',
            email='alice456@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        ))

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(response, 'registration/registration_form.html')
        self.assertContains(
            response, "A user with that username already exists.")

    def test_username_existence_case_insensitive(self):
        self.client.post(reverse('registration_register'), self.default_post)
        # 'Alice' still matches 'alice'.
        response = self.client.post(reverse('registration_register'), dict(
            username='Alice',
            email='alice456@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        ))

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(response, 'registration/registration_form.html')
        self.assertContains(
            response, "A user with that username already exists.")

    def test_username_must_not_validate_as_email_address(self):
        self.client.post(reverse('registration_register'), self.default_post)
        response = self.client.post(reverse('registration_register'), dict(
            username='alice@ucsd.edu',
            email='alice456@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        ))

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(response, 'registration/registration_form.html')
        self.assertContains(
            response, escape(
                "Your username can't be an email address."
                " Note that once you've registered, you'll be able to"
                " sign in with your username or your email address."))

    def test_email_already_exists(self):
        # Register once.
        self.client.post(reverse('registration_register'), self.default_post)
        # Register again with the same email, but different other fields.
        response = self.client.post(
            reverse('registration_register'),
            dict(
                username='alice123',
                email='alice123@example.com',
                password1='GBRAustralia',
                password2='GBRAustralia',
            ),
            follow=True)
        # Should not get an error.
        self.assertTemplateUsed(
            response, 'registration/registration_complete.html')

        # 2 emails should've been sent: 1 for first registration and
        # 1 for second registration attempt.
        self.assertEqual(len(mail.outbox), 2)

        # Check that no new user exists.
        self.assertFalse(User.objects.filter(username='alice123').exists())

    def test_email_existence_case_sensitive(self):
        self.client.post(reverse('registration_register'), self.default_post)
        # Capitalizing the A in the email makes it register as different.
        # There do exist email systems that register accounts differing only
        # by capitalization (unfortunately).
        response = self.client.post(
            reverse('registration_register'),
            dict(
                username='alice123',
                email='Alice123@example.com',
                password1='GBRAustralia',
                password2='GBRAustralia',
            ),
            follow=True)
        # Should not get an error.
        self.assertTemplateUsed(
            response, 'registration/registration_complete.html')

        # 2 emails, 1 for each registration (notably, the 2nd registration
        # went through).
        self.assertEqual(len(mail.outbox), 2)
        # For the latest registration, check that the intended recipient
        # is the only recipient.
        activation_email = mail.outbox[-1]
        self.assertEqual(len(activation_email.to), 1)
        self.assertEqual(activation_email.to[0], 'Alice123@example.com')

        # Check that the new user exists, but is inactive.
        user = User.objects.get(
            username='alice123', email='Alice123@example.com')
        self.assertFalse(user.is_active)

    def test_email_already_exists_email_details(self):
        self.client.post(reverse('registration_register'), self.default_post)
        self.client.post(reverse('registration_register'), dict(
            username='alice123',
            email='alice123@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        ))

        already_exists_email = mail.outbox[-1]
        # Check that the intended recipient is the only recipient.
        self.assertEqual(len(already_exists_email.to), 1)
        self.assertEqual(already_exists_email.to[0], 'alice123@example.com')
        # Should mention the existing username somewhere in the email.
        existing_user = User.objects.get(email='alice123@example.com')
        self.assertIn(existing_user.username, already_exists_email.body)
        # Sanity check that this is the correct email template.
        self.assertIn("already", already_exists_email.body)

    def test_password_fields_do_not_match(self):
        response = self.client.post(reverse('registration_register'), dict(
            username='alice',
            email='alice123@example.com',
            password1='GreatBarrier',
            password2='greatBarrier',
        ))

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(response, 'registration/registration_form.html')
        self.assertContains(
            response, escape("The two password fields didn't match."))

    def test_password_too_short(self):
        """
        There are other password related errors too. For now we'll just
        check that at least one is working.
        """
        response = self.client.post(reverse('registration_register'), dict(
            username='alice',
            email='alice123@example.com',
            password1='GBR',
            password2='GBR',
        ))

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(response, 'registration/registration_form.html')
        self.assertContains(
            response, "This password is too short.")


class ActivateTest(BaseRegisterTest):

    def test_success(self):
        activation_link = self.register_and_get_activation_link()

        # Navigate to the activation link.
        response = self.client.get(activation_link, follow=True)
        self.assertTemplateUsed(
            response, 'registration/activation_complete.html')

        # The user should be active.
        user = User.objects.get(username='alice')
        self.assertTrue(user.is_active)

    def test_bad_key(self):
        activation_link = self.register_and_get_activation_link()

        # Chop characters off of the end of the URL to get an invalid key.
        # (Note that the last char is a slash, so must chop at least 2.)
        response = self.client.get(activation_link[:-3], follow=True)
        # Should get the activation failure template.
        self.assertTemplateUsed(response, 'registration/activate.html')

        # The user should still be inactive.
        user = User.objects.get(username='alice')
        self.assertFalse(user.is_active)

    def test_expired_key(self):
        # Have an activation-key expiration time of 0.5 seconds
        with self.settings(ACCOUNT_ACTIVATION_DAYS=(0.5 / 86400.0)):
            activation_link = self.register_and_get_activation_link()

            # Wait 1 second before using the confirmation link
            time.sleep(1)
            response = self.client.get(activation_link, follow=True)
            self.assertTemplateUsed(response, 'registration/activate.html')

        # The user should still be inactive.
        user = User.objects.get(username='alice')
        self.assertFalse(user.is_active)

    def test_already_activated(self):
        activation_link = self.register_and_get_activation_link()

        # Activate.
        self.client.get(activation_link, follow=True)

        # The user should now be active.
        user = User.objects.get(username='alice')
        self.assertTrue(user.is_active)

        # Attempt to activate again. Should get the failure template because
        # the user is already active. (This is django-registration's behavior.)
        response = self.client.get(activation_link, follow=True)
        self.assertTemplateUsed(response, 'registration/activate.html')


class ActivationResendTest(BaseRegisterTest):

    def test_load_page(self):
        response = self.client.get(reverse('activation_resend'))
        self.assertTemplateUsed(
            response, 'registration/activation_resend_form.html')

    def test_success(self):
        # Register. This sends an email.
        self.client.post(reverse('registration_register'), self.default_post)

        # Re-send activation email.
        response = self.client.post(
            reverse('activation_resend'),
            dict(email=self.default_post['email']), follow=True)
        self.assertTemplateUsed(
            response, 'registration/activation_resend_complete.html')

        # Should have 2 emails now.
        self.assertEqual(len(mail.outbox), 2)
        # Check the latest email.
        latest_activation_email = mail.outbox[-1]
        # Check that the intended recipient is the only recipient.
        self.assertEqual(len(latest_activation_email.to), 1)
        self.assertEqual(latest_activation_email.to[0], 'alice123@example.com')

        # Activate with this email's activation link.
        activation_link = None
        for word in latest_activation_email.body.split():
            if '://' in word:
                activation_link = word
                break
        self.assertIsNotNone(activation_link)
        self.client.get(activation_link)
        # The user should be active.
        user = User.objects.get(username='alice')
        self.assertTrue(user.is_active)


class EmailChangeTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EmailChangeTest, cls).setUpTestData()

        cls.user = cls.create_user(
            username='sampleUsername', password='samplePassword',
            email='old.email.address@example.com')
        cls.user2 = cls.create_user()

    def submit_and_get_confirmation_link(self):
        """Shortcut function for tests focusing on the confirmation step."""
        self.client.force_login(self.user)
        self.client.post(reverse('email_change'), dict(
            email='new.email.address@example.com'))

        confirmation_email = mail.outbox[-2]
        # Confirmation link: should be the first link (first "word" with '://')
        # in the confirmation email.
        confirmation_link = None
        for word in confirmation_email.body.split():
            if '://' in word:
                confirmation_link = word
                break
        self.assertIsNotNone(confirmation_link)
        return confirmation_link

    def test_load_submit_page_signed_out(self):
        """Load page while logged out -> login page."""
        response = self.client.get(reverse('email_change'))
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL)+'?next='+reverse('email_change'),
        )

    def test_load_submit_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('email_change'))
        self.assertTemplateUsed(response, 'accounts/email_change_form.html')

    def test_submit(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('email_change'),
            dict(email='new.email.address@example.com'), follow=True)
        self.assertTemplateUsed(response, 'accounts/email_change_done.html')

        # 2 emails should've been sent: 1 to new address and 1 to old address.
        self.assertEqual(len(mail.outbox), 2)

    def test_submit_confirmation_email_details(self):
        self.client.force_login(self.user)
        self.client.post(reverse('email_change'), dict(
            email='new.email.address@example.com'))

        confirmation_email = mail.outbox[-2]
        self.assertListEqual(
            confirmation_email.to, ['new.email.address@example.com'])
        self.assertIn(self.user.username, confirmation_email.body)
        self.assertIn(
            "{h} hours".format(h=settings.EMAIL_CHANGE_CONFIRMATION_HOURS),
            confirmation_email.body)

    def test_submit_notice_email_details(self):
        self.client.force_login(self.user)
        self.client.post(reverse('email_change'), dict(
            email='new.email.address@example.com'))

        notice_email = mail.outbox[-1]
        self.assertListEqual(
            notice_email.to, ['old.email.address@example.com'])
        self.assertIn(self.user.username, notice_email.body)
        self.assertIn('new.email.address@example.com', notice_email.body)
        self.assertIn(
            "{h} hours".format(h=settings.EMAIL_CHANGE_CONFIRMATION_HOURS),
            notice_email.body)

    def test_confirm(self):
        confirmation_link = self.submit_and_get_confirmation_link()

        # Navigate to the confirmation link.
        response = self.client.get(confirmation_link, follow=True)
        self.assertTemplateUsed(response, 'accounts/email_change_complete.html')

        # Check that the email has changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new.email.address@example.com')

    def test_submit_invalid_email(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('email_change'), dict(
            email='not.an.email.address*AT*example.com'))
        self.assertTemplateUsed(response, 'accounts/email_change_form.html')
        self.assertContains(response, "Enter a valid email address.")

    def test_submit_email_already_exists(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('email_change'),
            dict(email=self.user2.email), follow=True)
        # Should not get an error.
        self.assertTemplateUsed(response, 'accounts/email_change_done.html')

        # Only 1 email should've been sent, to the new address.
        self.assertEqual(len(mail.outbox), 1)

        already_exists_email = mail.outbox[-1]
        # Check that the intended recipient is the only recipient.
        self.assertEqual(len(already_exists_email.to), 1)
        self.assertEqual(already_exists_email.to[0], self.user2.email)
        # Should mention the existing username somewhere in the email.
        self.assertIn(self.user2.username, already_exists_email.body)
        # Sanity check that this is the correct email template.
        self.assertIn("already", already_exists_email.body)

    def test_confirm_signed_out(self):
        confirmation_link = self.submit_and_get_confirmation_link()
        # We'll assume the key is between the last two slashes
        # of the confirm URL.
        confirmation_key = confirmation_link.split('/')[-2]

        # Navigate to the confirmation link while signed out.
        # Should show sign-in page.
        self.client.logout()
        sign_in_url = (
            reverse(settings.LOGIN_URL) + '?next='
            + reverse('email_change_confirm', args=[confirmation_key])
                .replace(':', '%3A'))
        response = self.client.get(confirmation_link)
        self.assertRedirects(response, sign_in_url)
        # The email should not have changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old.email.address@example.com')

        # Now sign in. Should complete the process.
        response = self.client.post(
            sign_in_url,
            dict(username='sampleUsername', password='samplePassword'),
            follow=True,
        )
        self.assertTemplateUsed(response, 'accounts/email_change_complete.html')
        # The email should have changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new.email.address@example.com')

    def test_confirm_invalid_key(self):
        confirmation_link = self.submit_and_get_confirmation_link()

        # Chop characters off of the end of the URL to get an invalid key.
        # (Note that the last char is a slash, so must chop at least 2.)
        response = self.client.get(confirmation_link[:-3], follow=True)
        self.assertTemplateUsed(response, 'accounts/email_change_confirm.html')
        # The email should not have changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old.email.address@example.com')

    def test_confirm_expired_key(self):
        # Have a confirmation-key expiration time of 0.5 seconds
        with self.settings(EMAIL_CHANGE_CONFIRMATION_HOURS=(0.5 / 3600.0)):
            confirmation_link = self.submit_and_get_confirmation_link()

            # Wait 1 second before using the confirmation link
            time.sleep(1)
            response = self.client.get(confirmation_link, follow=True)
            self.assertTemplateUsed(
                response, 'accounts/email_change_confirm.html')

        # The email should not have changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old.email.address@example.com')

    def test_confirm_signed_in_as_other_user(self):
        confirmation_link = self.submit_and_get_confirmation_link()

        # Attempt to confirm as a different user.
        self.client.force_login(self.user2)
        response = self.client.get(confirmation_link)
        self.assertTemplateUsed(response, 'accounts/email_change_confirm.html')
        # The email should not have changed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'old.email.address@example.com')


class EmailAllTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(EmailAllTest, cls).setUpTestData()

        cls.user = cls.create_user()

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
        # Check that the email has the expected number of recipients:
        # the number of users with an email address.
        # (Special users like 'robot' don't have emails.)
        num_of_users = User.objects.all().exclude(email='').count()
        self.assertEqual(len(mail.outbox[-1].bcc), num_of_users)

        # TODO: Check the emails in more detail: subject, message, and
        # possibly checking at least some of the bcc addresses.
