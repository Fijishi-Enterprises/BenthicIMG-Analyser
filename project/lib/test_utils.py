# Utility classes and functions for tests.
import datetime
import json
import os
import posixpath
import urlparse
import pytz
from django.contrib.auth import get_user_model
from django.core import mail, management
from django.core.files.storage import get_storage_class
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from django.test.client import Client
from django.utils import timezone
from annotations.models import LabelGroup, Label
from images.model_utils import PointGen
from images.models import Source, Point, Image
from lib.exceptions import TestfileDirectoryError
from lib.storage_backends import get_processing_storage_class
from lib.utils import is_django_str


# Settings to override in all of our unit tests.
test_settings = dict()

# Store media in a 'unittests' subdir of the usual location.
# MEDIA_ROOT is only defined for local, and AWS for production,
# so use getattr() to catch the undefined cases (to avoid exceptions).
if hasattr(settings, 'MEDIA_ROOT'):
    test_settings['MEDIA_ROOT'] = os.path.join(
        settings.MEDIA_ROOT, 'unittests')
if hasattr(settings, 'AWS_S3_MEDIA_SUBDIR'):
    test_settings['AWS_S3_MEDIA_SUBDIR'] = posixpath.join(
        settings.AWS_S3_MEDIA_SUBDIR, 'unittests')
test_settings['MEDIA_URL'] = urlparse.urljoin(
    settings.MEDIA_URL, 'unittests/')

# Store processing files in a 'unittests' subdir of the usual location.
if hasattr(settings, 'PROCESSING_ROOT'):
    test_settings['PROCESSING_ROOT'] = os.path.join(
        settings.PROCESSING_ROOT, 'unittests')
if hasattr(settings, 'AWS_S3_PROCESSING_SUBDIR'):
    test_settings['AWS_S3_PROCESSING_SUBDIR'] = posixpath.join(
        settings.AWS_S3_PROCESSING_SUBDIR, 'unittests')

# To test functionality of sending emails to the admins,
# the setting ADMINS must be set. It might not be set for
# development machines.
test_settings['ADMINS'] = [
    ('Admin One', 'admin1@example.com'),
    ('Admin Two', 'admin2@example.com'),
]


@override_settings(**test_settings)
class BaseTest(TestCase):
    """
    Base class for our test classes.
    """
    fixtures = []
    source_member_roles = []

    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)

    @classmethod
    def setUpTestData(cls):
        super(BaseTest, cls).setUpTestData()

        # File checking must be done in setUpTestData() rather than setUp(),
        # so that we can run it before individual test classes'
        # setUpTestData(), which may add files.
        cls.storage_checker = StorageChecker()
        cls.storage_checker.check_storage_pre_test()

    def setUp(self):
        self.setAccountPerms()
        self.setTestSpecificPerms()

    @classmethod
    def tearDownClass(cls):
        # File cleanup must be done in tearDownClass() rather than tearDown(),
        # otherwise it'll clean up class-wide setup files after the
        # class's first test.
        #
        # TODO: It's possible that files created by one test will interfere
        # with the next test (in the same class), and this timing doesn't
        # account for that because it doesn't run between tests. We may need
        # a more clever solution.
        # Read here for example:
        # http://stackoverflow.com/questions/4283933/
        cls.storage_checker.clean_storage_post_test()

        super(BaseTest, cls).tearDownClass()

    def setAccountPerms(self):
        # TODO: is the below necessary, or is adding these permissions done by magic anyway?
        #
        # Give account and profile permissions to each user.
        # It's less annoying to do this dynamically than it is to include
        # the permissions in the fixtures for every user.
        #UserenaManager().check_permissions()
        pass

    def setTestSpecificPerms(self):
        """
        Set permissions specific to the test class, e.g. source permissions.
        This has two advantages over specifying permissions in fixtures:
        (1) Can easily set permissions specific to a particular test class.
        (2) It's tedious to specify permissions in fixtures.
        """
        for role in self.source_member_roles:
            source = Source.objects.get(name=role[0])
            user = User.objects.get(username=role[1])
            source.assign_role(user, role[2])


class ClientTest(BaseTest):
    """
    Base class for tests that use a test client.
    """
    PERMISSION_DENIED_TEMPLATE = 'permission_denied.html'
    client = None

    @classmethod
    def setUpTestData(cls):
        super(ClientTest, cls).setUpTestData()
        cls.client = Client()

        # Create a superuser. By using --noinput, the superuser won't be
        # able to log in normally because no password was set.
        # Use force_login() to log in.
        management.call_command('createsuperuser',
            '--noinput', username='superuser',
            email='superuser@example.com', verbosity=0)

    def setUp(self):
        BaseTest.setUp(self)

        # The test client.
        self.client = Client()

        # Whenever a source id needs to be specified for a URL parameter
        # or something, this will generally be used.
        # Subclasses can set this to an actual source id.
        self.source_id = None

        self.default_upload_params = dict(
            specify_metadata='filenames',
            skip_or_upload_duplicates='skip',
            is_uploading_points_or_annotations=False,
            is_uploading_annotations_not_just_points='no',
        )

    def assertStatusOK(self, response):
        self.assertEqual(response.status_code, 200)

    def assertMessages(self, response, expected_messages):
        """
        Asserts that a specific set of messages (to display at the top
        of the page) are in the response.

        Actual and expected messages are sorted before being compared,
        so message order does not matter.

        response: the response object to check, which must have messages
            in its context
        expected_messages: a list of strings
        """
        messages = response.context['messages']
        actual_messages = [m.message for m in messages]

        # Make sure expected_messages is a list or tuple, not a string.
        if is_django_str(expected_messages):
            self.fail("expected_messages should be a list or tuple, not a string.")

        # Sort actual and expected messages before comparing them, so that
        # message order does not matter.
        actual_messages.sort()
        expected_messages.sort()

        if not expected_messages == actual_messages:
            # Must explicitly specify each message's format string as a unicode
            # string, so that if the message is a lazy translation object, the
            # message doesn't appear as <django.utils.functional...>
            # See https://docs.djangoproject.com/en/1.4/topics/i18n/translation/#working-with-lazy-translation-objects
            actual_messages_str = ", ".join(u'"{m}"'.format(m=m) for m in actual_messages)
            expected_messages_str = ", ".join(u'"{m}"'.format(m=m) for m in expected_messages)

            self.fail(u"Message mismatch.\n" \
                      u"Expected messages were: {expected}\n" \
                      u"Actual messages were:   {actual}".format(
                expected=expected_messages_str,
                actual=actual_messages_str,
            ))
        else:
            # Success. Print the message if UNIT_TEST_VERBOSITY is on.
            if settings.UNIT_TEST_VERBOSITY >= 1:
                print u"Messages:"
                for message in actual_messages:
                    print u"{m}".format(m=message)

    def assertFormErrors(self, response, form_name, expected_errors):
        """
        Asserts that a specific form in the response context has a specific
        set of errors.

        Actual and expected errors are sorted before being compared,
        so error order does not matter.

        response: the response object to check, which must have the form
            named form_name in its context
        form_name: the name of the form in the context
        expected_errors: a dict like
            {'fieldname1': ["error1"], 'fieldname2': ["error1", "error2"], ...}
        """
        if form_name not in response.context:
            self.fail("There was no form called {form_name} in the response context.".format(
                form_name=form_name,
            ))

        actual_errors = response.context[form_name].errors

        # Sort actual and expected errors before comparing them, so that
        # error order does not matter.
        for field_name, field_errors in expected_errors.iteritems():
            # Make sure expected error entries are lists or tuples, not strings.
            if is_django_str(expected_errors[field_name]):
                self.fail("Expected errors for {field_name} should be a list or tuple, not a string.".format(
                    field_name=field_name,
                ))

            # Force lazy-translation strings to evaluate.
            expected_errors[field_name] = [u"{e}".format(e=e) for e in expected_errors[field_name]]

            expected_errors[field_name].sort()

        for field_name, field_errors in actual_errors.iteritems():
            actual_errors[field_name].sort()

        actual_errors_printable = dict( [(k,list(errors)) for k,errors in actual_errors.items() if len(errors) > 0] )

        if not expected_errors == actual_errors:
            self.fail("Error mismatch in the form {form_name}.\n" \
                      "Expected errors were: {expected}\n" \
                      "Actual errors were:   {actual}".format(
                form_name=form_name,
                expected=expected_errors,
                actual=actual_errors_printable,
            ))
        else:
            # Success. Print the errors if UNIT_TEST_VERBOSITY is on.
            if settings.UNIT_TEST_VERBOSITY >= 1:
                print "Errors:"
                print actual_errors_printable

    def login_required_page_test(self, protected_url, username, password):
        """
        Going to a login-required page while logged out should trigger a
        redirect to the login page.  Then once the user logs in, they
        should be redirected to the page they requested.
        """
        self.client.logout()
        response = self.client.get(protected_url)

        # This URL isn't built with django.utils.http.urlencode() because
        # (1) urlencode() unfortunately escapes the '/' in its arguments, and
        # (2) str concatenation should be safe when there's no possibility of
        # malicious input.
        url_signin_with_protected_page_next = reverse('signin') + '?next=' + protected_url
        self.assertRedirects(response, url_signin_with_protected_page_next)

        response = self.client.post(url_signin_with_protected_page_next, dict(
            identification=username,
            password=password,
        ))
        self.assertRedirects(response, protected_url)

    def permission_required_page_test(self, protected_url,
                                      denied_users, accepted_users):
        """
        Going to a permission-required page...
        - while logged out: should show the permission-denied template.
        - while logged in as a user without sufficient permission: should
        show the permission-denied template.
        - while logged in a a user with sufficient permission: should show
        the page they requested.
        """
        self.client.logout()
        response = self.client.get(protected_url)
        self.assertStatusOK(response)
        self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

        for user in denied_users:
            self.client.login(username=user['username'], password=user['password'])
            response = self.client.get(protected_url)
            self.assertStatusOK(response)
            self.assertTemplateUsed(response, self.PERMISSION_DENIED_TEMPLATE)

        for user in accepted_users:
            self.client.login(username=user['username'], password=user['password'])
            response = self.client.get(protected_url)
            self.assertStatusOK(response)
            self.assertTemplateNotUsed(response, self.PERMISSION_DENIED_TEMPLATE)

    # TODO: Phase this out in favor of upload_image_new().
    # This interface is a bit clunky for most purposes.
    def upload_image(self, filename, **options):
        """
        Upload a single image via the Ajax view.

        Requires logging in as a user with upload permissions in
        the source, first.

        :param filename: The image file's filepath as a string, relative to
            <settings.SAMPLE_UPLOADABLES_ROOT>/data.
        :return: A tuple of (image_id, response):
            image_id - id of the uploaded image.
            response - the response object from the upload.
        """
        sample_uploadable_directory = os.path.join(settings.SAMPLE_UPLOADABLES_ROOT, 'data')

        sample_uploadable_path = os.path.join(sample_uploadable_directory, filename)
        file_to_upload = open(sample_uploadable_path, 'rb')

        post_dict = dict(
            file=file_to_upload,
            **self.default_upload_params
        )
        post_dict.update(options)

        response = self.client.post(
            reverse('image_upload_ajax', kwargs={'source_id': self.source_id}),
            post_dict,
        )
        file_to_upload.close()

        self.assertStatusOK(response)

        # Get the image_id from response.content;
        # if not present, set to None.
        response_json = response.json()
        image_id = response_json.get('image_id', None)

        return image_id, response

    user_count = 0
    @classmethod
    def create_user(cls, username=None):
        """
        Create a user.
        :param username: New user's username. "user<number>" if not given.
        :return: The new user.
        """
        cls.user_count += 1
        if not username:
            username = 'user{n}'.format(n=cls.user_count)

        User = get_user_model()
        post_dict = dict(
            username=username,
            email='{username}@example.com'.format(username=username),
        )
        cls.client.force_login(User.objects.get(username='superuser'))
        cls.client.post(reverse('signup'), post_dict)
        cls.client.logout()

        activation_email = mail.outbox[0]
        activation_link = None
        for word in activation_email.body.split():
            if '://' in word:
                activation_link = word
                break
        cls.client.get(activation_link)

        return User.objects.get(username=username)

    source_count = 0
    source_defaults = dict(
        name=None,
        visibility=Source.VisibilityTypes.PUBLIC,
        description="Description",
        affiliation="Affiliation",
        key1="Key1",
        image_height_in_cm=50,
        min_x=0,
        max_x=100,
        min_y=0,
        max_y=100,
        point_generation_type=PointGen.Types.SIMPLE,
        simple_number_of_points=50,
        alleviate_threshold=0,
        latitude='0.0',
        longitude='0.0',
    )
    @classmethod
    def create_source(cls, user, name=None, **options):
        """
        Create a source.
        :param user: User who is creating this source.
        :param name: Source name. "Source <number>" if not given.
        :param options: Other params to POST into the new source form.
        :return: The new source.
        """
        cls.source_count += 1
        if not name:
            name = 'Source {n}'.format(n=cls.source_count)

        post_dict = dict()
        post_dict.update(cls.source_defaults)
        post_dict.update(options)
        post_dict['name'] = name

        cls.client.force_login(user)
        cls.client.post(reverse('source_new'), post_dict)
        cls.client.logout()

        return Source.objects.get(name=name)

    @classmethod
    def create_labels(cls, user, source, label_names, group_name):
        """
        Create labels.
        :param user: User who is creating these labels.
        :param source: Source whose labelset page to use
            while creating these labels.
        :param label_names: Names for the new labels.
        :param group_name: Name for the label group to put the labels in;
            this label group is assumed to not exist yet.
        :return: The new labels, as a queryset.
        """
        group = LabelGroup(name=group_name, code=group_name[:10])
        group.save()

        # TODO: Use auto-generated simple images rather than relying on
        # a sample uploadables folder.
        filepath = os.path.join(settings.SAMPLE_UPLOADABLES_ROOT,
            'data', '001_2012-05-01_color-grid-001.png')
        cls.client.force_login(user)
        for name in label_names:
            # Re-opening the file for every label may seem wasteful,
            # but the upload process seems to close the file, so it's
            # necessary.
            with open(filepath, 'rb') as thumbnail:
                cls.client.post(
                    reverse('labelset_new', kwargs=dict(source_id=source.id)),
                    dict(
                        # create_label triggers the new-label form.
                        # The key just needs to be there in the POST;
                        # the value doesn't matter.
                        create_label='.',
                        name=name,
                        code=name[:10],
                        group=group.id,
                        description="Description",
                        thumbnail=thumbnail,
                    )
                )
        cls.client.logout()

        return Label.objects.filter(name__in=label_names)

    @classmethod
    def create_labelset(cls, user, source, labels):
        """
        Create a labelset.
        :param user: User to create the labelset as.
        :param source: The source which this labelset will belong to
        :param labels: The labels this labelset will have, as a queryset
        :return: The new labelset
        """
        cls.client.force_login(user)
        cls.client.post(
            reverse('labelset_new', kwargs=dict(source_id=source.id)),
            dict(
                # create_labelset indicates that the new-labelset form should
                # be used, not the new-label form which is also on the page.
                # The key just needs to be there in the POST;
                # the value doesn't matter.
                create_labelset='.',
                labels=labels.values_list('pk', flat=True),
            ),
        )
        cls.client.logout()
        source.refresh_from_db()
        return source.labelset

    image_count = 0
    image_upload_defaults = dict(
        specify_metadata='after',
        skip_or_upload_duplicates='skip',
        is_uploading_points_or_annotations=False,
        is_uploading_annotations_not_just_points='no',
    )
    @classmethod
    def upload_image_new(cls, user, source, **options):
        """
        Upload a data image.
        :param user: User to upload as.
        :param source: Source to upload to.
        :param options: Other params to POST into the image upload form.
        :return: The new image.
        """
        cls.image_count += 1

        post_dict = dict()
        post_dict.update(cls.image_upload_defaults)
        post_dict.update(options)

        # TODO: Use auto-generated simple images rather than relying on
        # a sample uploadables folder.
        filepath = os.path.join(settings.SAMPLE_UPLOADABLES_ROOT,
            'data', '001_2012-05-01_color-grid-001.png')
        with open(filepath, 'rb') as f:
            post_dict['file'] = f
            cls.client.force_login(user)
            response = cls.client.post(
                reverse('image_upload_ajax', kwargs={'source_id': source.id}),
                post_dict,
            )
            cls.client.logout()

        response_json = response.json()
        image_id = response_json.get('image_id', None)
        image = Image.objects.get(pk=image_id)
        return image

    @classmethod
    def add_annotations(cls, user, image, annotations):
        """
        Add human annotations to an image.
        :param user: Which user to annotate as.
        :param image: Image to add annotations for.
        :param annotations: Annotations to add, as a dict of point
            numbers to label codes, e.g.: {1: 'labelA', 2: 'labelB'}
        :return: None.
        """
        num_points = Point.objects.filter(image=image).count()

        post_dict = dict()
        for point_num in range(1, num_points+1):
            post_dict['label_'+str(point_num)] = annotations.get(point_num, '')
            post_dict['robot_'+str(point_num)] = json.dumps(False)

        cls.client.force_login(user)
        cls.client.post(
            reverse('save_annotations_ajax', kwargs=dict(image_id=image.id)),
            post_dict,
        )
        cls.client.logout()

    @staticmethod
    def print_response_messages(response):
        """
        Outputs (to console) the Django messages that were received in the given response.
        """
        print ['message: '+m.message for m in list(response.context['messages'])]

    @staticmethod
    def print_form_errors(response, form_name):
        """
        Outputs (to console) the errors of the given form in the given response.
        response: the response object
        form_name: the form's name in the response context (this is a string)
        """
        print ['{0} error: {1}: {2}'.format(form_name, field_name, str(error_list))
               for field_name, error_list in response.context[form_name].errors.iteritems()]

class StorageChecker(object):
    """
    Provide functions that (1) check that file storage for tests is empty
    before tests, and (2) clean up test file storage after tests.
    """
    # Filenames we can safely ignore during setup and teardown.
    ignorable_filenames = ['tasks.log']

    def __init__(self):
        self.timestamp_before_tests = None
        self.unexpected_filenames = None

    def check_storage_pre_test(self):
        """
        Pre-test check for files in the test file directories.
        """
        self.unexpected_filenames = []

        storages = [
            # Media
            get_storage_class()(),
            # Processing
            get_processing_storage_class()(),
        ]

        for storage in storages:
            # Check for files, starting at the storage's base directory.
            self._check_directory_pre_test(storage, '')

            if self.unexpected_filenames:
                format_str = (
                    "The test setup routine found files in {dir}:"
                    "\n{filenames}"
                    "\nPlease ensure that:"
                    "\n1. The directory is empty prior to testing"
                    "\n2. Files were cleaned properly after previous tests"
                )
                filenames_str = '\n'.join(self.unexpected_filenames[:10])
                if len(self.unexpected_filenames) > 10:
                    filenames_str += "\n(And others)"

                raise TestfileDirectoryError(format_str.format(
                    dir=storage.location, filenames=filenames_str))

        # Save a timestamp just before the tests start.
        # This will allow an extra sanity check when tearing down tests.
        self.timestamp_before_tests = timezone.now()

    def _check_directory_pre_test(self, storage, directory):
        # If we found enough unexpected files, just abort.
        # No need to burn resources listing all the unexpected files.
        if len(self.unexpected_filenames) > 10:
            return

        dirnames, filenames = storage.listdir(directory)

        for dirname in dirnames:
            self._check_directory_pre_test(
                storage, storage.path_join(directory, dirname))

        for filename in filenames:
            # If we found enough unexpected files, just abort.
            # No need to burn resources listing all the unexpected files.
            if len(self.unexpected_filenames) > 10:
                return
            # Ignore certain filenames.
            if filename in self.ignorable_filenames:
                continue

            self.unexpected_filenames.append(
                storage.path_join(directory, filename))

    def clean_storage_post_test(self):
        """
        Post-test file cleanup of the test file directories.
        """
        self.unexpected_filenames = []

        storages = [
            # Media
            get_storage_class()(),
            # Processing
            get_processing_storage_class()(),
        ]

        for storage in storages:
            # Look for files, starting at the storage's base directory.
            # Delete files that were generated by the test. Raise an error
            # if unidentified files are found.
            self._clean_directory_post_test(storage, '')

            if self.unexpected_filenames:
                format_str = (
                    "The test teardown routine found unexpected files"
                    " in {dir}:"
                    "\n{filenames}"
                    "\nThese files seem to have been created prior to the test."
                    " Please make sure this directory isn't being used for"
                    " anything else during testing."
                )
                filenames_str = '\n'.join(self.unexpected_filenames[:10])
                if len(self.unexpected_filenames) > 10:
                    filenames_str += "\n(And others)"

                raise TestfileDirectoryError(format_str.format(
                    dir=storage.location, filenames=filenames_str))

    def _clean_directory_post_test(self, storage, directory):
        # If we found enough unexpected files, just abort.
        # No need to burn resources listing all the unexpected files.
        if len(self.unexpected_filenames) > 10:
            return

        dirnames, filenames = storage.listdir(directory)

        for dirname in dirnames:
            self._clean_directory_post_test(
                storage, storage.path_join(directory, dirname))

        for filename in filenames:
            # If we found enough unexpected files, just abort.
            # No need to burn resources listing all the unexpected files.
            if len(self.unexpected_filenames) > 10:
                return
            # Ignore certain filenames.
            if filename in self.ignorable_filenames:
                continue

            leftover_file_path = storage.path_join(directory, filename)

            file_naive_datetime = storage.modified_time(leftover_file_path)
            file_aware_datetime = timezone.make_aware(
                file_naive_datetime, pytz.timezone(storage.timezone))

            if file_aware_datetime + datetime.timedelta(0,60*10) \
             < self.timestamp_before_tests:
                # The file was created before the test started.
                # So it must not have been created by the test...
                # something's wrong.
                # Prepare to throw an error instead of deleting the file.
                #
                # (This is a real corner case because the file needs to
                # materialize in the directory AFTER the pre-test check...
                # but we want to be really careful about file deletions.)
                #
                # The 10-minute cushion in the time comparison is to allow
                # for discrepancies between the timekeeping used by Django
                # and the timekeeping used by the file storage system.
                # Even on Stephen's local Windows setup, where both Django
                # and the file storage are on the same machine, discrepancies
                # of ~6 seconds have been observed. Not sure why.
                # In any case, our compensation for the discrepancy doesn't
                # significantly decrease the safety of our mystery-files check.
                self.unexpected_filenames.append(leftover_file_path)
            else:
                # Timestamps indicate that it's almost certainly a file
                # generated by the test; remove it.
                storage.delete(leftover_file_path)

                if settings.UNIT_TEST_VERBOSITY >= 1:
                    print "*File removed* {fn}".format(
                        fn=leftover_file_path
                    )

        # We don't try to delete directories anymore because:
        #
        # (1) Amazon S3 doesn't actually have directories/folders.
        # A directory should get auto-deleted after deleting all
        # of its contents.
        # http://stackoverflow.com/a/22669537
        # (In practice, I didn't observe this auto-deletion when using
        # the S3 file browser or Django's manage.py shell, yet it
        # worked during actual test runs. Well, if it works, it works.
        # -Stephen)
        #
        # (2) With local storage, deleting a folder on Windows seems to
        # get 'Access is denied' even if the directories were created
        # during that same test run. Not sure how it is on Linux, but
        # overall it seems like directory cleanup is more trouble than
        # it's worth.