from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.urlresolvers import reverse
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

    # TODO: Add tests for getting redirected to the expected page
    # (about sources, source list, or whatever was in the 'next' URL
    # parameter).
    # TODO: Add tests that submit the sign-in form with errors.


class RegisterTest(ClientTest):

    @classmethod
    def setUpTestData(cls):
        # Call the parent's setup (while still using this class as cls)
        super(RegisterTest, cls).setUpTestData()

        cls.user = cls.create_user()

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

    # TODO: Test registration form errors.

    def test_register_success(self):
        username = 'alice'
        email_address = 'alice123@example.com'
        response = self.client.post(reverse('registration_register'), dict(
            username=username,
            email=email_address,
            password1='GreatBarrier',
            password2='GreatBarrier',
        ))

        self.assertRedirects(response, reverse('registration_complete'))

        # Check that an activation email was sent.
        self.assertEqual(len(mail.outbox), 1)
        # Check that the intended recipient is the only recipient.
        activation_email = mail.outbox[-1]
        self.assertEqual(len(activation_email.to), 1)
        self.assertEqual(activation_email.to[0], email_address)

        # Check that the new user exists, but is inactive.
        user = User.objects.get(username=username, email=email_address)
        self.assertFalse(user.is_active)

    def test_sign_in_fail_before_activation(self):
        username = 'alice'
        email_address = 'alice123@example.com'
        password = 'GreatBarrier'
        self.client.post(reverse('registration_register'), dict(
            username=username,
            email=email_address,
            password1=password,
            password2=password,
        ))

        # Check that the new user exists, but is inactive.
        user = User.objects.get(username=username, email=email_address)
        self.assertFalse(user.is_active)

        # Attempt to sign in as the new user.
        response = self.client.post(reverse('auth_login'), dict(
            username=username,
            password=password,
        ))
        # Should not work (we should still be at the login page with an error).
        self.assertTemplateUsed(response, 'registration/login.html')
        self.assertContains(response, "This account is inactive.")

    def test_activate_success(self):
        username = 'alice'
        email_address = 'alice123@example.com'
        password = 'GreatBarrier'
        self.client.post(reverse('registration_register'), dict(
            username=username,
            email=email_address,
            password1=password,
            password2=password,
        ))

        activation_email = mail.outbox[-1]
        # Activation link: should be the first link (first "word" with '://')
        # in the activation email.
        activation_link = None
        for word in activation_email.body.split():
            if '://' in word:
                activation_link = word
                break
        self.assertIsNotNone(activation_link)

        # Navigate to the activation link.
        response = self.client.get(activation_link)
        self.assertRedirects(
            response, reverse('registration_activation_complete'))

        # Attempt to sign in as the new user.
        response = self.client.post(reverse('auth_login'), dict(
            username=username,
            password=password,
        ))
        # Should work (we should be past the login page now).
        self.assertTemplateNotUsed(response, 'registration/login.html')


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
