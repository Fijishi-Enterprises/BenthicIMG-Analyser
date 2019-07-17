# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import hashlib
import time
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.urlresolvers import reverse
from django.shortcuts import resolve_url
from django.utils.html import escape
from lib.test_utils import ClientTest, sample_image_as_file

User = get_user_model()


class BaseRegisterTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(BaseRegisterTest, cls).setUpTestData()

        cls.user = cls.create_user()

    def register(self, username='alice', email='alice123@example.com',
                 password1='GreatBarrier', password2='GreatBarrier',
                 first_name="Alice", last_name="Baker",
                 affiliation="Testing Society",
                 reason_for_registering="Trying labeling tools",
                 project_description="Labeling corals",
                 how_did_you_hear_about_us="Colleagues",
                 agree_to_data_policy=True,
                 username2=''):
        data = dict(
            username=username, email=email,
            password1=password1, password2=password2,
            first_name=first_name, last_name=last_name,
            affiliation=affiliation,
            reason_for_registering=reason_for_registering,
            project_description=project_description,
            how_did_you_hear_about_us=how_did_you_hear_about_us,
            agree_to_data_policy=agree_to_data_policy,
            username2=username2)
        response = self.client.post(
            reverse('registration_register'), data, follow=True)
        return response

    def register_and_get_activation_link(self):
        """Shortcut function for tests focusing on the activation step."""
        self.register()

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


class SignInTest(BaseRegisterTest):

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
        self.register(
            username='alice',
            email='alice123@example.com',
            password1='GreatBarrier',
            password2='GreatBarrier',
        )

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
        response = self.register()
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
        self.register()
        # Register again with the same username, but different other fields.
        response = self.register(
            username='alice',
            email='alice456@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, "A user with that username already exists.")

    def test_username_existence_case_insensitive(self):
        self.register()
        # 'Alice' still matches 'alice'.
        response = self.register(
            username='Alice',
            email='alice456@example.com',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, "A user with that username already exists.")

    def test_username_must_not_validate_as_email_address(self):
        response = self.register(
            username='alice@ucsd.edu',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, escape(
                "Your username can't be an email address."
                " Note that once you've registered, you'll be able to"
                " sign in with your username or your email address."))

    def test_username_reject_non_ascii(self):
        """
        Reject non-ASCII Unicode characters in usernames. First/last name
        fields can be more flexible, but usernames should be simple and easy
        to read/type/differentiate for everyone.
        """
        response = self.register(
            username='Béatrice',
            email='beatrice123@example.com',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, escape("Enter a valid username."))

    def test_username_reject_unicode_confusables(self):
        """
        Reject Unicode characters which are 'confusable', i.e. often look
        the same as other characters.
        This should be default behavior in django-registration 2.3+, even if
        Unicode characters were generally allowed.
        """
        response = self.register(
            # The 'a' in 'alice' here is a CYRILLIC SMALL LETTER A
            username='аlice123',
            email='alice123@example.com',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, escape("Enter a valid username."))

    def test_email_already_exists(self):
        # Register once.
        self.register()
        # Register again with the same email, but different other fields.
        response = self.register(
            username='alice123',
            email='alice123@example.com',
            password1='GBRAustralia',
            password2='GBRAustralia',
        )
        # Should not get an error.
        self.assertTemplateUsed(
            response, 'registration/registration_complete.html')

        # 2 emails should've been sent: 1 for first registration and
        # 1 for second registration attempt.
        self.assertEqual(len(mail.outbox), 2)

        # Check that no new user exists.
        self.assertFalse(User.objects.filter(username='alice123').exists())

    def test_email_existence_case_sensitive(self):
        self.register()
        # Capitalizing the A in the email makes it register as different.
        # There do exist email systems that register accounts differing only
        # by capitalization (unfortunately).
        response = self.register(
            username='alice123',
            email='Alice123@example.com',
        )
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
        self.register()
        self.register(
            username='alice123',
            email='alice123@example.com',
        )

        already_exists_email = mail.outbox[-1]
        # Check that the intended recipient is the only recipient.
        self.assertEqual(len(already_exists_email.to), 1)
        self.assertEqual(already_exists_email.to[0], 'alice123@example.com')
        # Should mention the existing username somewhere in the email.
        existing_user = User.objects.get(email='alice123@example.com')
        self.assertIn(existing_user.username, already_exists_email.body)
        # Sanity check that this is the correct email template.
        self.assertIn("already", already_exists_email.body)

    def test_email_reject_unicode_confusables(self):
        """
        Reject Unicode characters which are 'confusable', i.e. often look
        the same as other characters.
        This should be default behavior in django-registration 2.3+, even if
        Unicode characters were generally allowed.
        """
        response = self.register(
            username='alice123',
            # The 'a' in 'alice' here is a CYRILLIC SMALL LETTER A
            email='аlice123@example.com',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, escape("Enter a valid email address."))

    def test_password_fields_do_not_match(self):
        response = self.register(
            password1='GreatBarrier',
            password2='greatBarrier',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, escape("The two password fields didn't match."))

    def test_password_too_short(self):
        """
        There are other password related errors too. For now we'll just
        check that at least one is working.
        """
        response = self.register(
            password1='GBR',
            password2='GBR',
        )

        # We should still be at the registration page with an error.
        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response, "This password is too short.")

    def test_first_name_required(self):
        response = self.register(first_name='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_last_name_required(self):
        response = self.register(last_name='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_affiliation_required(self):
        response = self.register(affiliation='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_reason_for_registering_required(self):
        response = self.register(reason_for_registering='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_project_description_required(self):
        response = self.register(project_description='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_how_did_you_hear_about_us_required(self):
        response = self.register(how_did_you_hear_about_us='')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_did_not_agree_to_policy(self):
        response = self.register(agree_to_data_policy=False)

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(response, "This field is required.")

    def test_honeypot(self):
        response = self.register(username2='a')

        self.assertTemplateUsed(
            response, 'registration/registration_form.html')
        self.assertContains(
            response,
            escape("If you're human, don't fill in the hidden trap field."))

    def test_provided_fields_saved_to_database(self):
        self.register()
        user = User.objects.get(username='alice')
        self.assertEqual(user.first_name, "Alice")
        self.assertEqual(user.last_name, "Baker")
        self.assertEqual(user.profile.affiliation, "Testing Society")
        self.assertEqual(
            user.profile.reason_for_registering, "Trying labeling tools")
        self.assertEqual(user.profile.project_description, "Labeling corals")
        self.assertEqual(user.profile.how_did_you_hear_about_us, "Colleagues")

    def test_email_based_gravatar_defaults_to_false(self):
        self.register()
        user = User.objects.get(username='alice')
        self.assertFalse(user.profile.use_email_gravatar)


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
        self.register(email='alice123@example.com')

        # Re-send activation email.
        response = self.client.post(
            reverse('activation_resend'),
            dict(email='alice123@example.com'), follow=True)
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


class ProfileListTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(ProfileListTest, cls).setUpTestData()

        cls.url = resolve_url('profile_list')

    @classmethod
    def create_user_with_privacy(cls, privacy_value):
        user = cls.create_user()
        user.profile.privacy = privacy_value
        user.profile.save()
        return user

    def test_visibility_anonymous(self):
        user_private = self.create_user_with_privacy('closed')
        user_registered = self.create_user_with_privacy('registered')
        user_public = self.create_user_with_privacy('open')

        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_list.html')
        self.assertNotContains(response, user_private.username)
        self.assertNotContains(response, user_registered.username)
        self.assertContains(response, user_public.username)

    def test_visibility_registered(self):
        user_private = self.create_user_with_privacy('closed')
        user_registered = self.create_user_with_privacy('registered')
        user_public = self.create_user_with_privacy('open')

        self.client.force_login(user_public)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_list.html')
        self.assertNotContains(response, user_private.username)
        self.assertContains(response, user_registered.username)
        self.assertContains(response, user_public.username)

    def test_visibility_own_private_profile(self):
        user_private = self.create_user_with_privacy('closed')
        user_registered = self.create_user_with_privacy('registered')
        user_public = self.create_user_with_privacy('open')

        self.client.force_login(user_private)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_list.html')
        self.assertContains(response, user_private.username)
        self.assertContains(response, user_registered.username)
        self.assertContains(response, user_public.username)

    def test_no_visible_profiles(self):
        user_private = self.create_user_with_privacy('closed')

        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_list.html')
        self.assertNotContains(response, user_private.username)
        self.assertContains(response, "No profiles to display.")

    # TODO: Test pagination. A 'results per page' setting like the one for
    # Browse would probably help.


class ProfileDetailTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(ProfileDetailTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.other_user = cls.create_user()
        cls.url = resolve_url('profile_detail', cls.user.pk)

    @classmethod
    def set_privacy(cls, privacy_value):
        cls.user.profile.privacy = privacy_value
        cls.user.profile.save()

    def test_private_profile_anonymous(self):
        self.set_privacy('closed')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'permission_denied.html')
        self.assertContains(
            response, escape("You don't have permission to view this profile."))

    def test_private_profile_other_user(self):
        self.set_privacy('closed')
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'permission_denied.html')
        self.assertContains(
            response, escape("You don't have permission to view this profile."))

    def test_private_profile_same_user(self):
        self.set_privacy('closed')
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, "Edit your profile")

    def test_registered_only_profile_anonymous(self):
        self.set_privacy('registered')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'permission_denied.html')
        self.assertContains(
            response, escape("You don't have permission to view this profile."))

    def test_registered_only_profile_other_user(self):
        self.set_privacy('registered')
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertNotContains(response, "Edit your profile")

    def test_registered_only_profile_same_user(self):
        self.set_privacy('registered')
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, "Edit your profile")

    def test_public_profile_anonymous(self):
        self.set_privacy('open')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertNotContains(response, "Edit your profile")

    def test_public_profile_other_user(self):
        self.set_privacy('open')
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertNotContains(response, "Edit your profile")

    def test_public_profile_same_user(self):
        self.set_privacy('open')
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, "Edit your profile")


class ProfileEditTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(ProfileEditTest, cls).setUpTestData()

        cls.user = cls.create_user()
        cls.url = resolve_url('profile_edit')

    def edit_submit(self, privacy='closed',
                    first_name="Alice", last_name="Baker",
                    affiliation="Testing Society",
                    website="http://www.testingsociety.org/",
                    location="Seoul, South Korea",
                    about_me="I'm a tester.\nI test things for a living.",
                    avatar_file=None, use_email_gravatar=True):
        data = dict(
            privacy=privacy,
            first_name=first_name, last_name=last_name,
            affiliation=affiliation,
            website=website, location=location, about_me=about_me,
            avatar_file=avatar_file, use_email_gravatar=use_email_gravatar)
        response = self.client.post(self.url, data, follow=True)
        return response

    def test_load_page_anonymous(self):
        """The view only makes sense for registered users."""
        response = self.client.get(self.url, follow=True)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_load_page(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'profiles/profile_form.html')

    def test_submit(self):
        self.client.force_login(self.user)
        response = self.edit_submit(avatar_file=sample_image_as_file('_.png'))
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')

        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice")
        self.assertEqual(self.user.last_name, "Baker")
        self.assertEqual(self.user.profile.affiliation, "Testing Society")
        self.assertEqual(
            self.user.profile.website, "http://www.testingsociety.org/")
        self.assertEqual(self.user.profile.location, "Seoul, South Korea")
        self.assertEqual(
            self.user.profile.about_me,
            "I'm a tester.\nI test things for a living.")
        self.assertNotEqual(self.user.profile.avatar_file.name, '')
        self.assertEqual(self.user.profile.use_email_gravatar, True)

    def test_first_name_required(self):
        self.client.force_login(self.user)
        response = self.edit_submit(first_name="")
        self.assertTemplateUsed(response, 'profiles/profile_form.html')
        self.assertContains(response, "This field is required.")

    def test_last_name_required(self):
        self.client.force_login(self.user)
        response = self.edit_submit(last_name="")
        self.assertTemplateUsed(response, 'profiles/profile_form.html')
        self.assertContains(response, "This field is required.")

    def test_affiliation_required(self):
        self.client.force_login(self.user)
        response = self.edit_submit(affiliation="")
        self.assertTemplateUsed(response, 'profiles/profile_form.html')
        self.assertContains(response, "This field is required.")

    def test_website_optional(self):
        self.client.force_login(self.user)
        response = self.edit_submit(website="")
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.website, "")

    def test_location_optional(self):
        self.client.force_login(self.user)
        response = self.edit_submit(location="")
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.location, "")

    def test_about_me_optional(self):
        self.client.force_login(self.user)
        response = self.edit_submit(about_me="")
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.about_me, "")

    def test_avatar_file_optional(self):
        self.client.force_login(self.user)
        response = self.edit_submit(avatar_file='no_file')
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar_file.name, '')

    def test_use_email_gravatar_optional(self):
        self.client.force_login(self.user)
        response = self.edit_submit(use_email_gravatar=False)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.use_email_gravatar, False)

    def test_avatar_file_plus_use_email_gravatar_equals_email_gravatar(self):
        self.client.force_login(self.user)
        response = self.edit_submit(
            avatar_file=sample_image_as_file('_.png'),
            use_email_gravatar=True)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, 'gravatar.com/avatar')
        self.assertContains(
            response, hashlib.md5(self.user.email.lower()).hexdigest())

    def test_avatar_file_plus_no_email_gravatar_equals_avatar_file(self):
        self.client.force_login(self.user)
        response = self.edit_submit(
            avatar_file=sample_image_as_file('_.png'),
            use_email_gravatar=False)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertNotContains(response, 'gravatar.com/avatar')
        self.assertNotContains(
            response, hashlib.md5(self.user.email.lower()).hexdigest())

    def test_no_file_plus_use_email_gravatar_equals_email_gravatar(self):
        self.client.force_login(self.user)
        response = self.edit_submit(
            avatar_file=None,
            use_email_gravatar=True)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, 'gravatar.com/avatar')
        self.assertContains(
            response, hashlib.md5(self.user.email.lower()).hexdigest())

    def test_no_file_plus_no_email_gravatar_equals_random_gravatar(self):
        self.client.force_login(self.user)
        response = self.edit_submit(
            avatar_file=None,
            use_email_gravatar=False)
        self.assertTemplateUsed(response, 'profiles/profile_detail.html')
        self.assertContains(response, 'gravatar.com/avatar')
        self.assertNotContains(
            response, hashlib.md5(self.user.email.lower()).hexdigest())
