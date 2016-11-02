# Utility classes and functions for tests.
import datetime
from io import BytesIO
import json
import os
import posixpath
import pytz
import random
import urlparse
from PIL import Image as PILImage
from django.contrib.auth import get_user_model
from django.core import mail, management
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from django.test.client import Client
from django.utils import timezone

from accounts.utils import get_robot_user
from annotations.models import Annotation
from images.model_utils import PointGen
from images.models import Source, Point, Image
from labels.models import LabelGroup, Label, LocalLabel
from lib.exceptions import TestfileDirectoryError
from lib.utils import is_django_str
from vision_backend.models import Classifier as Robot
import boto.sqs


# Settings to override in all of our unit tests.
test_settings = dict()

# Store media in a 'unittests' subdir of the usual location.

# MEDIA_ROOT is only defined for local storage,
# so use hasattr() to catch the undefined case (to avoid exceptions).
if hasattr(settings, 'MEDIA_ROOT'):
    test_settings['MEDIA_ROOT'] = os.path.join(
        settings.MEDIA_ROOT, 'unittests')

# AWS_LOCATION is only defined for S3 storage. In this case, a change of the
# media location also needs a corresponding change in the MEDIA_URL.
if hasattr(settings, 'AWS_LOCATION'):
    test_settings['AWS_LOCATION'] = posixpath.join(
        settings.AWS_LOCATION, 'unittests')
    test_settings['MEDIA_URL'] = urlparse.urljoin(
        settings.MEDIA_URL, 'unittests/')

# Bypass the .delay() call to make the tasks run synchronously. 
# This is needed since the celery agent runs in a different 
# context (e.g. Database)
test_settings['CELERY_ALWAYS_EAGER'] = True

# Make sure backedn tasks do not run.
test_settings['FORCE_NO_BACKEND_SUBMIT'] = True


def get_total_messages_in_jobs_queue():
    """
    Returns number of jobs in the spacer jobs queue.
    If there are, for some tests, it means we have to wait.
    """
    if not settings.DEFAULT_FILE_STORAGE == 'lib.storage_backends.MediaStorageS3':
        return 0
    c = boto.sqs.connect_to_region('us-west-2')
    queue = c.lookup('spacer_jobs')
    attr = queue.get_attributes()
    return int(attr['ApproximateNumberOfMessages']) + int(attr['ApproximateNumberOfMessagesNotVisible'])


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
        
        # Reset so that only tests that explicitly need the backend calls it.
        test_settings['FORCE_NO_BACKEND_SUBMIT'] = True

        super(BaseTest, cls).tearDownClass()

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
        User = get_user_model()
        cls.superuser = User.objects.get(username='superuser')

    def setUp(self):
        BaseTest.setUp(self)

        # The test client.
        self.client = Client()

        # Whenever a source id needs to be specified for a URL parameter
        # or something, this will generally be used.
        # Subclasses can set this to an actual source id.
        self.source_id = None

        self.default_upload_params = dict(
            specify_metadata='after',
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
        url_signin_with_protected_page_next = reverse(settings.LOGIN_URL) + '?next=' + protected_url
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
            reverse('upload_images_ajax', kwargs={'source_id': self.source_id}),
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
    def create_user(cls, username=None, password='SamplePassword', email=None):
        """
        Create a user.
        :param username: New user's username. 'user<number>' if not given.
        :param password: New user's password.
        :param email: New user's email. '<username>@example.com' if not given.
        :return: The new user.
        """
        cls.user_count += 1
        if not username:
            username = 'user{n}'.format(n=cls.user_count)
        if not email:
            email = '{username}@example.com'.format(username=username)

        cls.client.post(reverse('registration_register'), dict(
            username=username, email=email,
            password1=password, password2=password,
            first_name="-", last_name="-",
            affiliation="-",
            reason_for_registering="-",
            project_description="-",
            how_did_you_hear_about_us="-",
            agree_to_data_policy=True,
        ))

        activation_email = mail.outbox[-1]
        activation_link = None
        for word in activation_email.body.split():
            if '://' in word:
                activation_link = word
                break
        cls.client.get(activation_link)

        User = get_user_model()
        return User.objects.get(username=username)

    source_count = 0
    source_defaults = dict(
        name=None,
        visibility=Source.VisibilityTypes.PUBLIC,
        description="Description",
        affiliation="Affiliation",
        key1="Aux1",
        key2="Aux2",
        key3="Aux3",
        key4="Aux4",
        key5="Aux5",
        image_height_in_cm=50,
        min_x=0,
        max_x=100,
        min_y=0,
        max_y=100,
        point_generation_type=PointGen.Types.SIMPLE,
        simple_number_of_points=5,
        confidence_threshold=100,
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
    def add_source_member(cls, admin, source, member, perm):
        """
        Add member to source, with permission level perm.
        Use admin to send the invite.
        """
        # Send invite as source admin
        cls.client.force_login(admin)
        cls.client.post(
            reverse('source_admin', kwargs={'source_id': source.pk}),
            dict(
                sendInvite='sendInvite',
                recipient=member.username,
                source_perm=perm,
            )
        )
        # Accept invite as prospective source member
        cls.client.force_login(member)
        cls.client.post(
            reverse('invites_manage'),
            dict(
                accept='accept',
                sender=admin.pk,
                source=source.pk,
            )
        )

        cls.client.logout()

    @classmethod
    def create_labels(cls, user, label_names, group_name, default_codes = None):
        """
        Create labels.
        :param user: User who is creating these labels.
        :param label_names: Names for the new labels.
        :param group_name: Name for the label group to put the labels in;
            this label group is assumed to not exist yet.
        :return: The new labels, as a queryset.
        """
        group = LabelGroup(name=group_name, code=group_name[:10])
        group.save()

        if default_codes is None:
            default_codes = [name[:10] for name in label_names]

        cls.client.force_login(user)
        for name, code in zip(label_names, default_codes):
            cls.client.post(
                reverse('label_new_ajax'),
                dict(
                    name=name,
                    default_code=code,
                    group=group.id,
                    description="Description",
                    # A new filename will be generated, and the uploaded
                    # filename will be discarded, so it doesn't matter.
                    thumbnail=sample_image_as_file('_.png'),
                )
            )
        cls.client.logout()

        return Label.objects.filter(name__in=label_names)

    @classmethod
    def create_labelset(cls, user, source, labels):
        """
        Create a labelset (or redefine entries in an existing one).
        :param user: User to create the labelset as.
        :param source: The source which this labelset will belong to
        :param labels: The labels this labelset will have, as a queryset
        :return: The new labelset
        """
        cls.client.force_login(user)
        cls.client.post(
            reverse('labelset_add', kwargs=dict(source_id=source.id)),
            dict(
                label_ids=','.join(
                    str(pk) for pk in labels.values_list('pk', flat=True)),
            ),
        )
        cls.client.logout()
        source.refresh_from_db()
        return source.labelset

    image_count = 0
    @classmethod
    def upload_image_new(cls, user, source, image_options=None):
        """
        Upload a data image.
        :param user: User to upload as.
        :param source: Source to upload to.
        :param image_options: Dict of options for the image file.
            Accepted keys: filetype, and whatever create_sample_image() takes.
        :return: The new image.
        """
        cls.image_count += 1

        post_dict = dict()

        # Get an image file
        image_options = image_options or dict()
        filetype = image_options.pop('filetype', 'PNG')
        default_filename = "file_{count}.{filetype}".format(
            count=cls.image_count, filetype=filetype.lower())
        filename = image_options.pop('filename', default_filename)
        post_dict['file'] = sample_image_as_file(
            filename, filetype, image_options)

        # Send the upload form
        cls.client.force_login(user)
        response = cls.client.post(
            reverse('upload_images_ajax', kwargs={'source_id': source.id}),
            post_dict,
        )
        cls.client.logout()

        response_json = response.json()
        image_id = response_json['image_id']
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

    @classmethod
    def create_robot(cls, source):
        """
        Add a robot to a source.
        NOTE: This does not use any standard task or utility function
        for adding a robot, so standard assumptions might not hold.
        :param source: Source to add a robot for.
        :return: The new Robot.
        """
        robot = Robot(
            source=source,
            nbr_train_images=50,
            runtime_train=100,
        )
        robot.save()
        return robot

    @classmethod
    def add_robot_annotations(cls, robot, image, annotations):
        """
        Add robot annotations to an image.
        NOTE: This does not use any standard view or utility function
        for adding robot annotations, so standard assumptions might not hold:
        overwriting old annotations, setting statuses, etc. Use with caution.
        :param robot: Robot model object to use for annotation.
        :param image: Image to add annotations for.
        :param annotations: Annotations to add, as a dict of point
            numbers to label codes, e.g.: {1: 'labelA', 2: 'labelB'}
        :return: None.
        """
        num_points = Point.objects.filter(image=image).count()

        # TODO: Speed up with prefetching and/or bulk saving
        for point_num in range(1, num_points+1):
            label_code = annotations.get(point_num, '')
            if not label_code:
                continue

            point = Point.objects.get(image=image, point_number=point_num)
            annotation = Annotation(
                image=image,
                source=image.source,
                point=point,
                label=image.source.labelset.get_global_by_code(label_code),
                user=get_robot_user(),
                robot_version=robot,
            )
            annotation.save()

        if all([n in annotations for n in range(1, num_points+1)]):
            # Annotations passed in for all points
            image.features.classified = True
            image.features.save()

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
    ignorable_filenames = [
        'vision_backend.log',
        # It seems S3 is silly, and will sometimes think there's a file with
        # an empty filename in a directory. These 'files' can be deleted but
        # it may be tricky. Best to just ignore these files, as it shouldn't
        # hurt to leave them in between tests.
        '',
    ]

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


def create_sample_image(width=200, height=200, cols=10, rows=10):
    """
    Create a test image. The image content is a color grid.
    Optionally specify pixel width/height, and the color grid cols/rows.
    Colors are interpolated along the grid with randomly picked color ranges.

    Return as an in-memory PIL image.
    """
    # Randomly choose one RGB color component to vary along x, one to vary
    # along y, and one to stay constant.
    x_varying_component = random.choice([0, 1, 2])
    y_varying_component = random.choice(list(
        {0, 1, 2} - {x_varying_component}))
    const_component = list(
        {0, 1, 2} - {x_varying_component, y_varying_component})[0]
    # Randomly choose the ranges of colors.
    x_min_color = random.choice([0.0, 0.1, 0.2, 0.3])
    x_max_color = random.choice([0.7, 0.8, 0.9, 1.0])
    y_min_color = random.choice([0.0, 0.1, 0.2, 0.3])
    y_max_color = random.choice([0.7, 0.8, 0.9, 1.0])
    const_color = random.choice([0.3, 0.4, 0.5, 0.6, 0.7])

    col_width = width / float(cols)
    row_height = height / float(rows)
    min_rgb = 0
    max_rgb = 255

    im = PILImage.new('RGB', (width,height))

    const_color_value = int(round(
        const_color*(max_rgb - min_rgb) + min_rgb
    ))

    for x in range(cols):

        left_x = int(round(x*col_width))
        right_x = int(round((x+1)*col_width))

        x_varying_color_value = int(round(
            (x/float(cols))*(x_max_color - x_min_color)*(max_rgb - min_rgb)
            + (x_min_color*min_rgb)
        ))

        for y in range(rows):

            upper_y = int(round(y*row_height))
            lower_y = int(round((y+1)*row_height))

            y_varying_color_value = int(round(
                (y/float(rows))*(y_max_color - y_min_color)*(max_rgb - min_rgb)
                + (y_min_color*min_rgb)
            ))

            color_dict = {
                x_varying_component: x_varying_color_value,
                y_varying_component: y_varying_color_value,
                const_component: const_color_value,
            }

            # The dict's keys should be the literals 0, 1, and 2.
            # We interpret these as R, G, and B respectively.
            rgb_color = (color_dict[0], color_dict[1], color_dict[2])

            # Write the RGB color to the range of pixels.
            im.paste(rgb_color, (left_x, upper_y, right_x, lower_y))

    return im


def sample_image_as_file(filename, filetype=None, image_options=None):
    if not filetype:
        if posixpath.splitext(filename)[-1].upper() in ['.JPG', '.JPEG']:
            filetype = 'JPEG'
        elif posixpath.splitext(filename)[-1].upper() == '.PNG':
            filetype = 'PNG'
        else:
            raise ValueError(
                "Couldn't get filetype from filename: {}".format(filename))

    image_options = image_options or dict()
    im = create_sample_image(**image_options)
    with BytesIO() as stream:
        # Save the PIL image to an IO stream
        im.save(stream, filetype)
        # Convert to a file-like object, and use that in the upload form
        # http://stackoverflow.com/a/28209277/
        image_file = ContentFile(stream.getvalue(), name=filename)
    return image_file
