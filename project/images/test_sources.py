from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils import timezone
from guardian.shortcuts import get_objects_for_user
from annotations.model_utils import AnnotationAreaUtils
from images.model_utils import PointGen
from images.models import Source
from lib.test_utils import ClientTest


class SourceAboutTest(ClientTest):
    """
    Test the About Sources page.
    """
    fixtures = ['test_users.yaml', 'test_sources.yaml']

    def test_source_about(self):
        response = self.client.get(reverse('source_about'))
        self.assertStatusOK(response)


class SourceListTestWithSources(ClientTest):
    """
    Test the source list page when there's at least one source.
    """

    fixtures = ['test_users.yaml', 'test_sources.yaml']
    source_member_roles = [
        ('public1', 'user2', Source.PermTypes.ADMIN.code),
        ('public1', 'user4', Source.PermTypes.EDIT.code),
        ('private1', 'user3', Source.PermTypes.ADMIN.code),
        ('private1', 'user4', Source.PermTypes.VIEW.code),
        ]

    def source_list_as_user(self, username, password,
                            num_your_sources_predicted,
                            num_other_public_sources_predicted):
        """
        Test the source_list page as a certain user.
        If username is None, then the test is done while logged out.
        """
        # Sign in
        user = None
        if username is not None:
            user = User.objects.get(username=username)
            self.client.login(username=username, password=password)

        response = self.client.get(reverse('source_list'))

        if user is None or num_your_sources_predicted == 0:
            # Redirects to source_about page
            self.assertRedirects(response, reverse('source_about'))

            # 2 public sources
            response = self.client.get(reverse('source_list'), follow=True)
            public_sources = response.context['public_sources']
            self.assertEqual(len(public_sources), 2)
            for source in public_sources:
                self.assertEqual(source.visibility, Source.VisibilityTypes.PUBLIC)
        else:
            # Goes to source_list page
            self.assertStatusOK(response)
            your_sources_predicted = get_objects_for_user(user, Source.PermTypes.VIEW.fullCode)

            # Sources this user is a member of
            your_sources = response.context['your_sources']
            self.assertEqual(len(your_sources), num_your_sources_predicted)
            for source_dict in your_sources:
                source = Source.objects.get(pk=source_dict['id'])
                self.assertTrue(source in your_sources_predicted)
                self.assertEqual(source.get_member_role(user), source_dict['your_role'])

            # Public sources this user isn't a member of
            other_public_sources = response.context['other_public_sources']
            self.assertEqual(len(other_public_sources), num_other_public_sources_predicted)
            for source in other_public_sources:
                self.assertFalse(source in your_sources_predicted)
                self.assertEqual(source.visibility, Source.VisibilityTypes.PUBLIC)

        self.client.logout()

    def test_source_list(self):
        self.source_list_as_user(
            None, None,
            num_your_sources_predicted=0, num_other_public_sources_predicted=2,
        )
        self.source_list_as_user(
            'user2', 'secret',
            num_your_sources_predicted=1, num_other_public_sources_predicted=1,
        )
        self.source_list_as_user(
            'user3', 'secret',
            num_your_sources_predicted=1, num_other_public_sources_predicted=2,
        )
        self.source_list_as_user(
            'user4', 'secret',
            num_your_sources_predicted=2, num_other_public_sources_predicted=1,
        )
        self.source_list_as_user(
            'user5', 'secret',
            num_your_sources_predicted=0, num_other_public_sources_predicted=2,
        )
        self.source_list_as_user(
            'superuser_user', 'secret',
            num_your_sources_predicted=4, num_other_public_sources_predicted=0,
        )


class SourceListTestWithoutSources(ClientTest):
    """
    Test the source list page when there are no sources on the entire site.
    (A corner case to be sure, but testable material nonetheless.)
    """

    fixtures = ['test_users.yaml']

    def source_list_as_user(self, username, password):
        """
        Test the source_list page as a certain user.
        If username is None, then the test is done while logged out.
        """
        if username is not None:
            self.client.login(username=username, password=password)

        # Redirect to source_about
        response = self.client.get(reverse('source_list'))
        self.assertRedirects(response, reverse('source_about'))

        # 0 public sources
        response = self.client.get(reverse('source_list'), follow=True)
        self.assertEqual(len(response.context['public_sources']), 0)

        self.client.logout()

    def test_source_list(self):
        self.source_list_as_user(None, None)
        self.source_list_as_user('user2', 'secret')


class SourceNewTest(ClientTest):
    """
    Test the New Source page.
    """
    @classmethod
    def setUpTestData(cls):
        super(SourceNewTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source_defaults = dict(
            name="Test Source",
            visibility=Source.VisibilityTypes.PRIVATE,
            affiliation="Testing Society",
            description="Description\ngoes here.",
            key1="Aux1",
            key2="Aux2",
            key3="Aux3",
            key4="Aux4",
            key5="Aux5",
            min_x=10,
            max_x=90,
            min_y=10,
            max_y=90,
            point_generation_type=PointGen.Types.SIMPLE,
            simple_number_of_points=16,
            confidence_threshold=25,
            latitude='-17.3776',
            longitude='25.1982',
        )

    def test_login_required(self):
        response = self.client.get(reverse('source_new'))
        self.assertRedirects(
            response,
            reverse(settings.LOGIN_URL)+'?next='+reverse('source_new'),
        )

    def test_access_page(self):
        """
        Access the page without errors.
        """
        self.client.force_login(self.user)
        response = self.client.get(reverse('source_new'))
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'images/source_new.html')

    def test_source_defaults(self):
        """
        Check for default values in the source form.
        """
        self.client.force_login(self.user)
        response = self.client.get(reverse('source_new'))

        form = response.context['sourceForm']
        self.assertEqual(
            form['visibility'].value(), Source.VisibilityTypes.PRIVATE)
        self.assertEqual(form['key1'].value(), 'Aux1')
        self.assertEqual(form['key2'].value(), 'Aux2')
        self.assertEqual(form['key3'].value(), 'Aux3')
        self.assertEqual(form['key4'].value(), 'Aux4')
        self.assertEqual(form['key5'].value(), 'Aux5')
        self.assertEqual(form['confidence_threshold'].value(), 100)

    def test_source_create(self):
        """
        Successful creation of a new source.
        """
        datetime_before_creation = timezone.now()

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('source_new'), self.source_defaults)

        new_source = Source.objects.latest('create_date')
        self.assertRedirects(response,
            reverse('source_main', kwargs={'source_id': new_source.pk}))

        self.assertEqual(new_source.name, "Test Source")
        self.assertEqual(new_source.visibility, Source.VisibilityTypes.PRIVATE)
        self.assertEqual(new_source.affiliation, "Testing Society")
        self.assertEqual(new_source.description, "Description\ngoes here.")
        self.assertEqual(new_source.labelset, None)
        self.assertEqual(new_source.key1, "Aux1")
        self.assertEqual(new_source.key2, "Aux2")
        self.assertEqual(new_source.key3, "Aux3")
        self.assertEqual(new_source.key4, "Aux4")
        self.assertEqual(new_source.key5, "Aux5")
        self.assertEqual(
            new_source.default_point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.SIMPLE,
                simple_number_of_points=16,
            ),
        )
        self.assertEqual(
            new_source.image_annotation_area,
            AnnotationAreaUtils.percentages_to_db_format(
                min_x=10, max_x=90,
                min_y=10, max_y=90,
            ),
        )
        self.assertEqual(new_source.latitude, '-17.3776')
        self.assertEqual(new_source.longitude, '25.1982')

        self.assertEqual(new_source.enable_robot_classifier, True)

        # Check that the source creation date is reasonable:
        # - a timestamp taken before creation should be before the creation date.
        # - a timestamp taken after creation should be after the creation date.
        self.assertTrue(datetime_before_creation <= new_source.create_date)
        self.assertTrue(new_source.create_date <= timezone.now())

    def test_aux_name_required(self):
        """
        Not filling in an aux. meta field name should get an error saying it's
        required.
        """
        source_args = dict()
        source_args.update(self.source_defaults)
        source_args.update(dict(
            key1="",
            key2="",
            key3="",
            key4="",
            key5="",
        ))

        self.client.force_login(self.user)
        response = self.client.post(reverse('source_new'), source_args)

        # Should be back on the new source form with errors.
        self.assertTemplateUsed(response, 'images/source_new.html')
        self.assertDictEqual(
            response.context['sourceForm'].errors,
            dict(
                key1=[forms.Field.default_error_messages['required']],
                key2=[forms.Field.default_error_messages['required']],
                key3=[forms.Field.default_error_messages['required']],
                key4=[forms.Field.default_error_messages['required']],
                key5=[forms.Field.default_error_messages['required']],
            )
        )
        # Should have no source created.
        self.assertEqual(Source.objects.all().count(), 0)

    def test_temporal_aux_name_not_accepted(self):
        """
        If an aux. meta field name looks like it's tracking date or time,
        don't accept it.
        """
        source_args = dict()
        source_args.update(self.source_defaults)
        source_args.update(dict(
            key1="date",
            key2="Year",
            key3="TIME",
            key4="month",
            key5="day",
        ))

        self.client.force_login(self.user)
        response = self.client.post(reverse('source_new'), source_args)

        # Should be back on the new source form with errors.
        self.assertTemplateUsed(response, 'images/source_new.html')
        error_dont_use_temporal = (
            "Date of image acquisition is already a default metadata field."
            " Do not use auxiliary metadata fields"
            " to encode temporal information."
        )
        self.assertDictEqual(
            response.context['sourceForm'].errors,
            dict(
                key1=[error_dont_use_temporal],
                key2=[error_dont_use_temporal],
                key3=[error_dont_use_temporal],
                key4=[error_dont_use_temporal],
                key5=[error_dont_use_temporal],
            )
        )
        # Should have no source created.
        self.assertEqual(Source.objects.all().count(), 0)

    def test_aux_name_conflict_with_builtin_name(self):
        """
        If an aux. meta field name conflicts with a built-in metadata field,
        show an error.
        """
        source_args = dict()
        source_args.update(self.source_defaults)
        source_args.update(dict(
            key1="name",
            key2="Comments",
            key3="FRAMING GEAR used",
        ))

        self.client.force_login(self.user)
        response = self.client.post(reverse('source_new'), source_args)

        # Should be back on the new source form with errors.
        self.assertTemplateUsed(response, 'images/source_new.html')
        error_conflict = (
            "This conflicts with either a built-in metadata"
            " field or another auxiliary field."
        )
        self.assertDictEqual(
            response.context['sourceForm'].errors,
            dict(
                key1=[error_conflict],
                key2=[error_conflict],
                key3=[error_conflict],
            )
        )
        # Should have no source created.
        self.assertEqual(Source.objects.all().count(), 0)

    def test_aux_name_conflict_with_other_aux_name(self):
        """
        If two aux. meta field names are the same, show an error.
        """
        source_args = dict()
        source_args.update(self.source_defaults)
        source_args.update(dict(
            key2="Site",
            key3="site",
        ))

        self.client.force_login(self.user)
        response = self.client.post(reverse('source_new'), source_args)

        # Should be back on the new source form with errors.
        self.assertTemplateUsed(response, 'images/source_new.html')
        error_conflict = (
            "This conflicts with either a built-in metadata"
            " field or another auxiliary field."
        )
        self.assertDictEqual(
            response.context['sourceForm'].errors,
            dict(
                key2=[error_conflict],
                key3=[error_conflict],
            )
        )
        # Should have no source created.
        self.assertEqual(Source.objects.all().count(), 0)


class SourceEditTest(ClientTest):
    """
    Test the Edit Source page.
    """
    @classmethod
    def setUpTestData(cls):
        super(SourceEditTest, cls).setUpTestData()

        cls.user_creator = cls.create_user()

        # Create a source
        cls.source = cls.create_source(cls.user_creator)
        cls.url = reverse('source_edit', kwargs={'source_id': cls.source.pk})

        # Source members
        cls.user_admin = cls.create_user()
        cls.add_source_member(cls.user_creator, cls.source,
            cls.user_admin, Source.PermTypes.ADMIN.code)
        cls.user_editor = cls.create_user()
        cls.add_source_member(cls.user_creator, cls.source,
            cls.user_editor, Source.PermTypes.EDIT.code)
        cls.user_viewer = cls.create_user()
        cls.add_source_member(cls.user_creator, cls.source,
            cls.user_viewer, Source.PermTypes.VIEW.code)
        # Non-member
        cls.user_outsider = cls.create_user()

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_access_as_admin(self):
        self.client.force_login(self.user_admin)
        response = self.client.get(self.url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, 'images/source_edit.html')

    def test_access_denied_as_editor(self):
        self.client.force_login(self.user_editor)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_access_denied_as_viewer(self):
        self.client.force_login(self.user_viewer)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_access_denied_as_outsider(self):
        self.client.force_login(self.user_outsider)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    def test_source_edit(self):
        self.client.force_login(self.user_creator)
        response = self.client.post(
            self.url,
            dict(
                name="Test Source 2",
                visibility=Source.VisibilityTypes.PUBLIC,
                affiliation="Testing Association",
                description="This is\na description.",
                key1="Island",
                key2="Site",
                key3="Habitat",
                key4="Section",
                key5="Transect",
                min_x=5,
                max_x=95,
                min_y=5,
                max_y=95,
                point_generation_type=PointGen.Types.STRATIFIED,
                number_of_cell_rows=4,
                number_of_cell_columns=6,
                stratified_points_per_cell=3,
                confidence_threshold=80,
                latitude='5.789',
                longitude='-50',
            ),
        )

        self.assertRedirects(
            response,
            reverse('source_main', kwargs={'source_id': self.source.pk})
        )

        self.source.refresh_from_db()
        self.assertEqual(self.source.name, "Test Source 2")
        self.assertEqual(self.source.visibility, Source.VisibilityTypes.PUBLIC)
        self.assertEqual(self.source.affiliation, "Testing Association")
        self.assertEqual(self.source.description, "This is\na description.")
        self.assertEqual(self.source.key1, "Island")
        self.assertEqual(self.source.key2, "Site")
        self.assertEqual(self.source.key3, "Habitat")
        self.assertEqual(self.source.key4, "Section")
        self.assertEqual(self.source.key5, "Transect")
        self.assertEqual(
            self.source.image_annotation_area,
            AnnotationAreaUtils.percentages_to_db_format(
                min_x=5, max_x=95, min_y=5, max_y=95,
            )
        )
        self.assertEqual(
            self.source.default_point_generation_method,
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.STRATIFIED,
                number_of_cell_rows=4,
                number_of_cell_columns=6,
                stratified_points_per_cell=3,
            )
        )
        self.assertEqual(self.source.confidence_threshold, 80)
        self.assertEqual(self.source.latitude, '5.789')
        self.assertEqual(self.source.longitude, '-50')


class SourceInviteTest(ClientTest):
    """
    Test sending and accepting invites to sources.
    """
    @classmethod
    def setUpTestData(cls):
        super(SourceInviteTest, cls).setUpTestData()

        cls.user_creator = cls.create_user()
        cls.source = cls.create_source(cls.user_creator)

        cls.user_editor = cls.create_user()

    def test_source_invite(self):
        # Send invite as source admin
        self.client.force_login(self.user_creator)
        self.client.post(
            reverse('source_admin', kwargs={'source_id': self.source.pk}),
            dict(
                sendInvite='sendInvite',
                recipient=self.user_editor.username,
                source_perm=Source.PermTypes.EDIT.code,
            ),
        )

        # Accept invite as prospective source member
        self.client.force_login(self.user_editor)
        self.client.post(
            reverse('invites_manage'),
            dict(
                accept='',
                sender=self.user_creator.pk,
                source=self.source.pk,
            ),
        )

        # Test that the given permission level works
        self.client.force_login(self.user_editor)
        response = self.client.get(
            reverse('upload_images', kwargs={'source_id': self.source.pk}))
        self.assertTemplateUsed(response, 'upload/upload_images.html')


class ImageViewTest(ClientTest):
    """
    Test the image view/detail page.
    """
    @classmethod
    def setUpTestData(cls):
        super(ImageViewTest, cls).setUpTestData()

        cls.user = cls.create_user()

        # Create a source
        cls.source = cls.create_source(cls.user)

        # Upload a small image and a large image
        cls.small_image = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(width=400, height=400))
        cls.large_image = cls.upload_image_new(
            cls.user, cls.source, image_options=dict(width=1600, height=1600))

    def test_view_page_with_small_image(self):
        url = reverse('image_detail', kwargs={'image_id': self.small_image.id})
        response = self.client.get(url)
        self.assertStatusOK(response)

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)

    def test_view_page_with_large_image(self):
        url = reverse('image_detail', kwargs={'image_id': self.large_image.id})
        response = self.client.get(url)
        self.assertStatusOK(response)

        # Try fetching the page a second time, to make sure thumbnail
        # generation doesn't go nuts.
        response = self.client.get(url)
        self.assertStatusOK(response)
