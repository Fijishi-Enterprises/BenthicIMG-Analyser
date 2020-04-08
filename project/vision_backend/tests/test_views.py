# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from unittest import skip

from django.urls import reverse

from export.tests.utils import BaseExportTest
from labels.models import Label
from lib.tests.utils import BasePermissionTest


class BackendViewPermissions(BasePermissionTest):

    def test_backend_main(self):
        url = reverse('backend_main', args=[self.source.pk])
        template = 'vision_backend/backend_main.html'

        self.source_to_private()
        self.assertPermissionLevel(url, self.SOURCE_VIEW, template=template)
        self.source_to_public()
        self.assertPermissionLevel(url, self.SIGNED_OUT, template=template)

    @skip("Skip until we can run backend during tests.")
    def test_backend_overview(self):
        # Requires at least 1 image
        self.upload_image(self.user, self.source)

        url = reverse('backend_overview')
        template = 'vision_backend/overview.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)

    def test_cm_test(self):
        url = reverse('cm_test')
        template = 'vision_backend/cm_test.html'

        self.assertPermissionLevel(
            url, self.SUPERUSER, template=template,
            deny_type=self.REQUIRE_LOGIN)


class BackendMainConfusionMatrixExportTest(BaseExportTest):

    @classmethod
    def setUpTestData(cls):
        super(BackendMainConfusionMatrixExportTest, cls).setUpTestData()

        cls.user = cls.create_user()

        cls.source = cls.create_source(cls.user)
        cls.create_labels(cls.user, ['A', 'B'], 'Group1')
        cls.create_labels(cls.user, ['C'], 'Group2')
        labels = Label.objects.all()
        cls.create_labelset(cls.user, cls.source, labels)
        cls.valres_classes = [
            labels.get(name=name).pk for name in ['A', 'B', 'C']]

        cls.url = reverse('backend_main', args=[cls.source.pk])

    def test_export_basic(self):
        robot = self.create_robot(self.source)
        valres = dict(
            classes=self.valres_classes,
            gt=[0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            est=[0, 0, 1, 1, 1, 1, 1, 1, 1, 0],
            scores=[.8]*10,
        )

        # Add valres to the session so that we don't have to create it in S3.
        #
        # "Be careful: To modify the session and then save it,
        # it must be stored in a variable first (because a new SessionStore
        # is created every time this property is accessed)"
        # http://stackoverflow.com/a/4454671/
        session = self.client.session
        session['valres'] = valres
        session['ccpk'] = robot.pk
        session.save()

        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data=dict(export_cm="Export confusion matrix"))

        expected_lines = [
            'A (A),2,4,0',
            'B (B),1,3,0',
            'C (C),0,0,0',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_export_with_confidence_threshold(self):
        robot = self.create_robot(self.source)
        valres = dict(
            classes=self.valres_classes,
            gt=[0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            est=[0, 0, 1, 1, 1, 1, 1, 1, 1, 0],
            scores=[.9, .9, .9, .8, .8, .8, .8, .7, .7, .7],
        )
        session = self.client.session
        session['valres'] = valres
        session['ccpk'] = robot.pk
        session.save()

        self.client.force_login(self.user)
        response = self.client.post(
            self.url + '?confidence_threshold=75',
            data=dict(export_cm="Export confusion matrix"))

        expected_lines = [
            'A (A),2,4,0',
            'B (B),0,1,0',
            'C (C),0,0,0',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_export_in_functional_groups_mode(self):
        robot = self.create_robot(self.source)

        # 0 and 1 are in Group1; 2 is in Group2. Being in functional groups
        # mode means we don't care if gt/est are 0/0, 0/1, 1/0, or 1/1. Those
        # are all matches for Group1.
        valres = dict(
            classes=self.valres_classes,
            gt=[0, 0, 0, 1, 1, 1, 2, 2, 2, 2],
            est=[0, 1, 2, 0, 1, 2, 0, 1, 1, 2],
            scores=[.8]*10,
        )
        session = self.client.session
        session['valres'] = valres
        session['ccpk'] = robot.pk
        session.save()

        self.client.force_login(self.user)
        response = self.client.post(
            self.url + '?labelmode=func',
            data=dict(export_cm="Export confusion matrix"))

        expected_lines = [
            'Group1,4,2',
            'Group2,3,1',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)

    def test_export_with_unicode(self):
        robot = self.create_robot(self.source)
        valres = dict(
            classes=self.valres_classes,
            gt=[0, 0, 0, 0, 0, 0, 1, 1, 1, 1],
            est=[0, 0, 1, 1, 1, 1, 1, 1, 1, 0],
            scores=[.8]*10,
        )
        session = self.client.session
        session['valres'] = valres
        session['ccpk'] = robot.pk
        session.save()

        local_label_a = self.source.labelset.get_labels().get(code='A')
        local_label_a.code = 'あ'
        local_label_a.save()

        self.client.force_login(self.user)
        response = self.client.post(
            self.url, data=dict(export_cm="Export confusion matrix"))

        expected_lines = [
            'A (あ),2,4,0',
            'B (B),1,3,0',
            'C (C),0,0,0',
        ]
        self.assert_csv_content_equal(response.content, expected_lines)
