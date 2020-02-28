from __future__ import unicode_literals
from abc import ABCMeta
import six

from django.urls import reverse

from api_core.tests.utils import BaseAPITest
from images.models import Source


@six.add_metaclass(ABCMeta)
class DeployBaseTest(BaseAPITest):

    @classmethod
    def setUpTestData(cls):
        super(DeployBaseTest, cls).setUpTestData()

        cls.user = cls.create_user(
            username='testuser', password='SamplePassword')
        cls.source = cls.create_source(
            cls.user, visibility=Source.VisibilityTypes.PUBLIC)
        cls.labels = cls.create_labels(cls.user, ['A'], 'GroupA')
        labelset = cls.create_labelset(cls.user, cls.source, cls.labels)

        # Set a custom label code, so we can confirm whether responses
        # contain the source's custom codes or default codes.
        local_label = labelset.locallabel_set.get(code='A')
        local_label.code = 'A_mycode'
        local_label.save()

        cls.classifier = cls.create_robot(cls.source)
        cls.deploy_url = reverse('api:deploy', args=[cls.classifier.pk])

        # Get a token
        response = cls.client.post(
            reverse('api:token_auth'),
            data='{"username": "testuser", "password": "SamplePassword"}',
            content_type='application/vnd.api+json',
        )
        token = response.json()['token']

        # Kwargs for test client post() and get().
        cls.request_kwargs = dict(
            # Authorization header.
            HTTP_AUTHORIZATION='Token {token}'.format(token=token),
            # Content type. Particularly needed for POST requests,
            # but doesn't hurt for other requests either.
            content_type='application/vnd.api+json',
        )


# During tests, we use CELERY_ALWAYS_EAGER = True to run tasks synchronously,
# so that we don't have to wait for tasks to finish before checking their
# results. To test state before all tasks finish, we'll mock the task
# functions to disable or change their behavior.
#
# Note: We have to patch the run() method of the task rather than patching
# the task itself. Otherwise, the patched task may end up being
# patched / not patched in tests where it's not supposed to be.
# https://stackoverflow.com/a/29269211/
#
# Note: Yes, patching views.deploy.run (views, not tasks) is
# correct if we want to affect usages of deploy in the views module.
# https://docs.python.org/3/library/unittest.mock.html#where-to-patch


def noop_task(*args):
    pass
