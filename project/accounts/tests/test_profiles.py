from __future__ import unicode_literals
import hashlib

from django.shortcuts import resolve_url
from django.utils.html import escape

from lib.test_utils import ClientTest, sample_image_as_file


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
