# Test the action buttons available from the image detail page.

from __future__ import unicode_literals
from abc import ABCMeta
import six

from django.urls import reverse

from annotations.model_utils import AnnotationAreaUtils
from images.model_utils import PointGen
from images.models import Image, Metadata
from lib.tests.utils import BasePermissionTest
from upload.tests.utils import UploadAnnotationsTestMixin
from vision_backend.models import Features


# Abstract class
@six.add_metaclass(ABCMeta)
class ImageDetailActionBaseTest(BasePermissionTest):

    # Subclasses should fill this in.
    action_url_name = None

    @classmethod
    def setUpTestData(cls):
        super(ImageDetailActionBaseTest, cls).setUpTestData()

        cls.source.default_point_generation_method = \
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.SIMPLE,
                simple_number_of_points=2)
        cls.source.save()

        cls.img = cls.upload_image(cls.user, cls.source)
        cls.img2 = cls.upload_image(cls.user, cls.source)
        cls.img3 = cls.upload_image(cls.user, cls.source)
        cls.img4 = cls.upload_image(cls.user, cls.source)
        cls.img5 = cls.upload_image(cls.user, cls.source)
        cls.img6 = cls.upload_image(cls.user, cls.source)

        cls.action_url_img = reverse(cls.action_url_name, args=[cls.img.pk])
        cls.action_url_img2 = reverse(cls.action_url_name, args=[cls.img2.pk])
        cls.action_url_img3 = reverse(cls.action_url_name, args=[cls.img3.pk])
        cls.action_url_img4 = reverse(cls.action_url_name, args=[cls.img4.pk])
        cls.action_url_img5 = reverse(cls.action_url_name, args=[cls.img5.pk])
        cls.action_url_img6 = reverse(cls.action_url_name, args=[cls.img6.pk])

        cls.labels = cls.create_labels(cls.user, ['A', 'B'], 'GroupA')
        cls.create_labelset(cls.user, cls.source, cls.labels)

    def assertCorrectPermissionsForPrivateSource(self):
        # Accessing the view. Use different images so we can re-test after a
        # successful action. (Actions such as image delete can't be re-done
        # on the same image.)
        self.assertPermissionDenied(self.action_url_img, None, post_data={})
        self.assertPermissionDenied(
            self.action_url_img2, self.user_outsider, post_data={})
        self.assertPermissionDenied(
            self.action_url_img3, self.user_viewer, post_data={})
        self.assertPermissionGranted(
            self.action_url_img4, self.user_editor, post_data={})
        self.assertPermissionGranted(
            self.action_url_img5, self.user_admin, post_data={})

        # Displaying the action button on the image detail page
        # (Logged out users can't see the image detail page)
        # (Outsider users can't see the image detail page)
        self.assertLinkAbsent(self.user_viewer, self.img6)
        self.assertLinkPresent(self.user_editor, self.img6)
        self.assertLinkPresent(self.user_admin, self.img6)

    def assertCorrectPermissionsForPublicSource(self):
        # Accessing the view. Use different images so we can re-test after a
        # successful action. (Actions such as image delete can't be re-done
        # on the same image.)
        self.assertPermissionDenied(self.action_url_img, None, post_data={})
        self.assertPermissionDenied(
            self.action_url_img2, self.user_outsider, post_data={})
        self.assertPermissionDenied(
            self.action_url_img3, self.user_viewer, post_data={})
        self.assertPermissionGranted(
            self.action_url_img4, self.user_editor, post_data={})
        self.assertPermissionGranted(
            self.action_url_img5, self.user_admin, post_data={})

        # Displaying the action button on the image detail page
        self.assertLinkAbsent(None, self.img6)
        self.assertLinkAbsent(self.user_outsider, self.img6)
        self.assertLinkAbsent(self.user_viewer, self.img6)
        self.assertLinkPresent(self.user_editor, self.img6)
        self.assertLinkPresent(self.user_admin, self.img6)

    def get_detail_page(self, user, img):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        url = reverse('image_detail', args=[img.pk])
        return self.client.get(url)

    def post_to_action_view(self, user, img):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        url = reverse(self.action_url_name, args=[img.pk])
        return self.client.post(url, follow=True)

    def upload_points_for_image(self, img):
        rows = [
            ['Name', 'Column', 'Row'],
            [img.metadata.name, 50, 50],
            [img.metadata.name, 60, 40],
        ]
        csv_file = self.make_csv_file('A.csv', rows)
        self.preview_csv_annotations(self.user, self.source, csv_file)
        self.upload_annotations(self.user, self.source)

    def action_url(self, img):
        return reverse(self.action_url_name, args=[img.pk])

    def assertLinkPresent(self, user, img):
        response = self.get_detail_page(user, img)
        self.assertContains(
            response, self.action_url(img),
            msg_prefix="Action button should be present")

    def assertLinkAbsent(self, user, img):
        response = self.get_detail_page(user, img)
        self.assertNotContains(
            response, self.action_url(img),
            msg_prefix="Action button should be absent")

    def assertActionDenyMessage(self, user, img, deny_message):
        response = self.post_to_action_view(user, img)
        self.assertContains(
            response, deny_message,
            msg_prefix="Page should show the denial message")


class DeleteImageTest(ImageDetailActionBaseTest):
    action_url_name = 'image_delete'

    def test_permission_private_source(self):
        self.source_to_private()
        self.assertCorrectPermissionsForPrivateSource()

    def test_permission_public_source(self):
        self.source_to_public()
        self.assertCorrectPermissionsForPublicSource()

    def test_success(self):
        img = self.upload_image(
            self.user, self.source,
            image_options=dict(filename="img1.png"))
        image_id = img.pk
        metadata_id = img.metadata.pk
        features_id = img.features.pk

        # Image, metadata, and features objects exist (fetching them doesn't
        # raise DoesNotExist)
        Image.objects.get(pk=image_id)
        Metadata.objects.get(pk=metadata_id)
        Features.objects.get(pk=features_id)

        response = self.post_to_action_view(self.user, img)
        self.assertContains(
            response, "Successfully deleted image img1.png.",
            msg_prefix="Page should show the correct message")

        # Image, metadata, and features should not exist anymore
        self.assertRaises(
            Image.DoesNotExist,
            callableObj=Image.objects.get, pk=image_id)
        self.assertRaises(
            Metadata.DoesNotExist,
            callableObj=Metadata.objects.get, pk=metadata_id)
        self.assertRaises(
            Features.DoesNotExist,
            callableObj=Features.objects.get, pk=features_id)

    def test_other_images_not_deleted(self):
        """Ensure that other images don't get deleted, just this one."""

        # Test with an image in a different source too.
        s2 = self.create_source(self.user)
        s2_img = self.upload_image(self.user, s2)

        img_id = self.img.pk
        img2_id = self.img2.pk
        s2_img_id = s2_img.pk

        # Delete img
        self.post_to_action_view(self.user, self.img)

        # img should be gone
        self.assertRaises(
            Image.DoesNotExist,
            callableObj=Image.objects.get, pk=img_id)
        # Other image in the same source should still be there
        Image.objects.get(pk=img2_id)
        # Image in another source should still be there
        Image.objects.get(pk=s2_img_id)

    def test_show_button_even_if_confirmed(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})

        self.assertLinkPresent(self.user, self.img)


class DeleteAnnotationsTest(ImageDetailActionBaseTest):
    action_url_name = 'image_delete_annotations'

    def test_permission_private_source(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img2, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img3, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img4, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img5, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img6, {1: 'A', 2: 'B'})

        self.source_to_private()
        self.assertCorrectPermissionsForPrivateSource()

    def test_permission_public_source(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img2, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img3, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img4, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img5, {1: 'A', 2: 'B'})
        self.add_annotations(self.user, self.img6, {1: 'A', 2: 'B'})

        self.source_to_public()
        self.assertCorrectPermissionsForPublicSource()

    def test_success(self):
        """Test deleting annotations."""
        img = self.upload_image(self.user, self.source)
        self.add_annotations(self.user, img, {1: 'A', 2: 'B'})

        img.refresh_from_db()
        self.assertEqual(
            img.annotation_set.count(), 2, msg="Should have annotations")
        self.assertTrue(img.confirmed, msg="Image should be confirmed")

        response = self.post_to_action_view(self.user, img)
        self.assertContains(
            response, "Successfully removed all annotations from this image.",
            msg_prefix="Page should show the success message")

        img.refresh_from_db()
        self.assertEqual(
            img.annotation_set.count(), 0,
            msg="Annotations should be deleted")
        self.assertFalse(img.confirmed, msg="Image should not be confirmed")

    def test_show_button_if_all_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})

        self.assertLinkPresent(self.user, self.img)

    def test_show_button_if_some_points_have_confirmed_annotations(self):
        robot = self.create_robot(self.source)

        # Unconfirmed
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B'})
        # Confirmed
        self.add_annotations(self.user, self.img, {1: 'A'})

        self.assertLinkPresent(self.user, self.img)

    def test_hide_button_if_only_machine_annotations(self):
        """
        It doesn't hurt to still make this function internally available,
        but there's no real use case, so we shouldn't show the button.
        """
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B'})

        self.assertLinkAbsent(self.user, self.img)

    def test_hide_button_if_no_annotations(self):
        self.assertLinkAbsent(self.user, self.img)


class RegeneratePointsTest(
        ImageDetailActionBaseTest, UploadAnnotationsTestMixin):
    action_url_name = 'image_regenerate_points'

    def test_permission_private_source(self):
        self.source_to_private()
        self.assertCorrectPermissionsForPrivateSource()

    def test_permission_public_source(self):
        self.source_to_public()
        self.assertCorrectPermissionsForPublicSource()

    def test_success(self):
        """Test regenerating points."""
        img = self.upload_image(self.user, self.source)
        old_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(old_point_pks), 0, msg="Should have points")

        response = self.post_to_action_view(self.user, img)
        self.assertContains(
            response, "Successfully regenerated point locations.",
            msg_prefix="Page should show the success message")

        new_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(new_point_pks), 0, msg="Should still have points")
        self.assertTrue(
            [new_pk not in old_point_pks for new_pk in new_point_pks],
            msg="New points should have different IDs from the old ones")

    def test_deny_if_all_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_some_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_imported_points(self):
        self.upload_points_for_image(self.img)

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_show_button_if_only_machine_annotations(self):
        robot = self.create_robot(self.source)
        self.add_robot_annotations(robot, self.img, {1: 'A', 2: 'B'})

        self.assertLinkPresent(self.user, self.img)

    def test_show_button_if_no_annotations(self):
        self.assertLinkPresent(self.user, self.img)


class ResetPointGenTest(ImageDetailActionBaseTest, UploadAnnotationsTestMixin):
    action_url_name = 'image_reset_point_generation_method'

    def test_permission_private_source(self):
        # Change the source default point-gen method, so that it doesn't match
        # any of the images'
        self.source.default_point_generation_method = \
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.UNIFORM,
                number_of_cell_rows=1, number_of_cell_columns=2)
        self.source.save()

        self.source_to_private()
        self.assertCorrectPermissionsForPrivateSource()

    def test_permission_public_source(self):
        # Change the source default point-gen method, so that it doesn't match
        # any of the images'
        self.source.default_point_generation_method = \
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.UNIFORM,
                number_of_cell_rows=1, number_of_cell_columns=2)
        self.source.save()

        self.source_to_public()
        self.assertCorrectPermissionsForPublicSource()

    def test_success(self):
        img = self.upload_image(self.user, self.source)
        old_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(old_point_pks), 0, msg="Should have points")

        # Change source point gen method
        self.source.default_point_generation_method = \
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.UNIFORM,
                number_of_cell_rows=1, number_of_cell_columns=2)
        self.source.save()
        self.assertNotEqual(
            self.source.default_point_generation_method,
            img.point_generation_method,
            msg="Source's point gen method should differ from the image's")

        # Reset image point gen method
        response = self.post_to_action_view(self.user, img)
        self.assertContains(
            response, "Reset image point generation method to source default.",
            msg_prefix="Page should show the correct message")

        img.refresh_from_db()
        new_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(new_point_pks), 0, msg="Should still have points")
        self.assertTrue(
            [new_pk not in old_point_pks for new_pk in new_point_pks],
            msg="New points should have different IDs from the old ones")
        self.assertEqual(
            self.source.default_point_generation_method,
            img.point_generation_method,
            msg="Source's point gen method should match the image's")

    def test_deny_if_all_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_some_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_imported_points(self):
        self.upload_points_for_image(self.img)

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_hide_button_if_point_gen_method_is_default(self):
        """
        It doesn't hurt to still make this function internally available,
        but there's no real use case, so we shouldn't show the button.
        """
        self.assertLinkAbsent(self.user, self.img)

    def test_show_button_if_point_gen_method_is_not_default(self):
        self.source.default_point_generation_method = \
            PointGen.args_to_db_format(
                point_generation_type=PointGen.Types.UNIFORM,
                number_of_cell_rows=1, number_of_cell_columns=2)
        self.source.save()

        self.assertLinkPresent(self.user, self.img)


class ResetAnnotationAreaTest(
        ImageDetailActionBaseTest, UploadAnnotationsTestMixin):
    action_url_name = 'image_reset_annotation_area'

    def test_permission_private_source(self):
        # Change the default annotation area so that it doesn't match any of
        # the images'
        self.source.image_annotation_area = \
            AnnotationAreaUtils.percentages_to_db_format(5, 95, 5, 95)
        self.source.save()

        self.source_to_private()
        self.assertCorrectPermissionsForPrivateSource()

    def test_permission_public_source(self):
        # Change the default annotation area
        self.source.image_annotation_area = \
            AnnotationAreaUtils.percentages_to_db_format(5, 95, 5, 95)
        self.source.save()

        self.source_to_public()
        self.assertCorrectPermissionsForPublicSource()

    def test_success(self):
        img = self.upload_image(self.user, self.source)

        # Change annotation area for the image
        self.client.force_login(self.user)
        self.client.post(
            reverse('annotation_area_edit', args=[img.pk]),
            data=dict(min_x=10, max_x=200, min_y=10, max_y=200))

        old_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(old_point_pks), 0, msg="Should have points")

        # Reset image's annotation area
        response = self.post_to_action_view(self.user, img)
        self.assertContains(
            response, "Reset annotation area to source default.",
            msg_prefix="Page should show the correct message")

        new_point_pks = list(img.point_set.values_list('pk', flat=True))
        self.assertGreater(
            len(new_point_pks), 0, msg="Should still have points")
        self.assertTrue(
            [new_pk not in old_point_pks for new_pk in new_point_pks],
            msg="New points should have different IDs from the old ones")

        img.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(
            self.source.image_annotation_area,
            img.metadata.annotation_area,
            msg="Source's annotation area should match the image's")

    def test_deny_if_all_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A', 2: 'B'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_some_points_have_confirmed_annotations(self):
        self.add_annotations(self.user, self.img, {1: 'A'})

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_deny_if_imported_points(self):
        self.upload_points_for_image(self.img)

        self.assertLinkAbsent(self.user, self.img)
        self.assertActionDenyMessage(
            self.user, self.img, "annotation area is not editable")

    def test_hide_button_if_annotation_area_is_default(self):
        """
        It doesn't hurt to still make this function internally available,
        but there's no real use case, so we shouldn't show the button.
        """
        self.assertLinkAbsent(self.user, self.img)

    def test_show_button_if_source_annotation_area_changed(self):
        self.source.image_annotation_area = \
            AnnotationAreaUtils.percentages_to_db_format(12, 88, 12, 88)
        self.source.save()

        self.assertLinkPresent(self.user, self.img)

    def test_show_button_if_image_specific_annotation_area(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('annotation_area_edit', args=[self.img.pk]),
            data=dict(min_x=10, max_x=200, min_y=10, max_y=200))

        self.assertLinkPresent(self.user, self.img)
