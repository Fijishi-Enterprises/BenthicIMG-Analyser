import csv
import math
from io import StringIO
import re
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.storage import get_storage_class
from django.test import override_settings
from django.test.utils import patch_logger
from django.urls import reverse
import spacer.config as spacer_config
from spacer.data_classes import ValResults

from ...models import Classifier
from ...tasks import collect_all_jobs, reset_features, submit_classifier
from .utils import BaseTaskTest


class TrainClassifierTest(BaseTaskTest):

    def test_success(self):
        # Provide enough data for training, and extract features.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()

        # Create a classifier
        job_msg = submit_classifier(self.source.id)

        # This source should now have a classifier (though not trained yet)
        self.assertTrue(
            Classifier.objects.filter(source=self.source).count() > 0)

        # Process training result
        collect_all_jobs()

        # Now we should have a trained classifier whose accuracy is the best so
        # far (due to having no previous classifiers), and thus it should have
        # been marked as accepted
        latest_classifier = self.source.get_latest_robot()
        self.assertEqual(latest_classifier.status, Classifier.ACCEPTED)

        # Also check that the actual classifier is created in storage.
        storage = get_storage_class()()
        self.assertTrue(storage.exists(
            settings.ROBOT_MODEL_FILE_PATTERN.format(pk=latest_classifier.pk)))

        # And that the val results are stored.
        self.assertTrue(storage.exists(
            settings.ROBOT_MODEL_VALRESULT_PATTERN.format(
                pk=latest_classifier.pk)))

        # Check that the point-counts in val_res is equal to val_data.
        val_res = ValResults.load(job_msg.tasks[0].valresult_loc)
        val_labels = job_msg.tasks[0].val_labels
        self.assertEqual(len(val_res.gt),
                         len(val_labels) * val_labels.samples_per_image)

    def test_train_second_classifier(self):
        """
        Accept a second classifier in a source which already has an accepted
        classifier.
        """
        def mock_train_msg_1(
                self_, acc, pc_accs, ref_accs, runtime):
            self_.acc = 0.5
            self_.pc_accs = pc_accs
            self_.ref_accs = ref_accs
            self_.runtime = runtime

        def mock_train_msg_2(
                self_, acc, pc_accs, ref_accs, runtime):
            self_.acc = (0.5*settings.NEW_CLASSIFIER_IMPROVEMENT_TH) + 0.001
            self_.pc_accs = [0.5]
            self_.ref_accs = ref_accs
            self_.runtime = runtime

        # Train one classifier.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()
        submit_classifier(self.source.id)
        # Collect classifier. Use mock to specify a particular accuracy.
        with mock.patch(
                'spacer.messages.TrainClassifierReturnMsg.__init__',
                mock_train_msg_1):
            collect_all_jobs()

        clf_1 = self.source.get_latest_robot()

        # Upload enough additional images for the next training to happen.
        old_image_count = spacer_config.MIN_TRAINIMAGES + 1
        new_image_count = math.ceil(
            old_image_count*settings.NEW_CLASSIFIER_TRAIN_TH)
        added_image_count = new_image_count - old_image_count
        self.upload_images_for_training(
            train_image_count=added_image_count, val_image_count=0)
        # Collect extracted features.
        collect_all_jobs()

        submit_classifier(self.source.id)
        # Collect classifier. Use mock to ensure a high enough accuracy
        # improvement to consider the classifier accepted.
        with mock.patch(
                'spacer.messages.TrainClassifierReturnMsg.__init__',
                mock_train_msg_2):
            collect_all_jobs()

        clf_2 = self.source.get_latest_robot()

        self.assertNotEqual(clf_1.pk, clf_2.pk, "Should have a new classifier")
        self.assertGreater(
            clf_2.nbr_train_images, clf_1.nbr_train_images,
            "Second classifier's training-image count should be greater")
        self.assertGreater(
            clf_2.accuracy, clf_1.accuracy,
            "Second classifier's accuracy should be greater")

    def test_with_dupe_points(self):
        """
        Images in the training set and validation set have two points with the
        same row/column.
        """

        # Upload annotated images with dupe points
        val_image_with_dupe_point = self.upload_image_with_dupe_points(
            'val.png', with_labels=True)
        training_image_with_dupe_point = self.upload_image_with_dupe_points(
            'train.png', with_labels=True)
        # Other annotated images to get enough for training
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES-1,
            val_image_count=0)

        # Process feature extraction results
        collect_all_jobs()

        # Train classifier
        job_msg = submit_classifier(self.source.id)
        collect_all_jobs()

        # Check training data

        storage = get_storage_class()()
        train_data = job_msg.tasks[0].train_labels.data
        feature_filepath = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=training_image_with_dupe_point.original_file.name)
        feature_location = storage.spacer_data_loc(feature_filepath)
        image_train_data = train_data[feature_location.key]
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(image_train_data),
            "Training data count should include dupe points")
        rowcols = [
            (row, col) for row, col, label in image_train_data]
        self.assertListEqual(
            self.rowcols_with_dupes_included, sorted(rowcols),
            "Training data rowcols should include dupe points")

        # Check validation data

        val_data = job_msg.tasks[0].val_labels.data
        feature_filepath = settings.FEATURE_VECTOR_FILE_PATTERN.format(
            full_image_path=val_image_with_dupe_point.original_file.name)
        feature_location = storage.spacer_data_loc(feature_filepath)
        image_val_data = val_data[feature_location.key]
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(image_val_data),
            "Validation data count should include dupe points")
        rowcols = [
            (row, col) for row, col, label in image_val_data]
        self.assertListEqual(
            self.rowcols_with_dupes_included, sorted(rowcols),
            "Validation data rowcols should include dupe points")

        # Check valresults

        val_res = ValResults.load(job_msg.tasks[0].valresult_loc)
        self.assertEqual(
            len(self.rowcols_with_dupes_included), len(val_res.gt),
            "Valresults count should include dupe points")

        # Check that there's an accepted classifier.

        latest_classifier = self.source.get_latest_robot()
        self.assertEqual(latest_classifier.status, Classifier.ACCEPTED)


class AbortCasesTest(BaseTaskTest):
    """
    Test cases where the task or collection would abort before reaching the
    end.
    """

    def test_nonexistent_source(self):
        """Try to train a classifier for a nonexistent source ID."""
        # To get a nonexistent source ID, create a source, get its ID, then
        # delete the source.
        source = self.create_source(self.user)
        source_id = source.pk
        source.delete()

        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_classifier(source_id)

            log_message = "Can't find source [{}]".format(source_id)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_classification_disabled(self):
        """Try to train for a source which has classification disabled."""
        # Ensure the source is otherwise ready for training.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()

        # Disable classification.
        self.source.enable_robot_classifier = False
        self.source.save()

        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_classifier(self.source.pk)

            log_message = "Source {} [{}] don't need new classifier.".format(
                self.source.name, self.source.pk)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_below_minimum_images(self):
        """
        Try to train while below the minimum number of images needed for first
        training.
        """
        # Prepare some training images.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()

        # But set CoralNet's requirement 1 higher than that image count.
        min_images = spacer_config.MIN_TRAINIMAGES + 2

        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            with override_settings(MIN_NBR_ANNOTATED_IMAGES=min_images):
                submit_classifier(self.source.pk)

            log_message = "Source {} [{}] don't need new classifier.".format(
                self.source.name, self.source.pk)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_not_enough_train_data_since_last_classifier(self):
        """
        Try to train when there haven't been enough training images added
        since the last training.
        """
        # Train one classifier.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()
        submit_classifier(self.source.pk)
        collect_all_jobs()

        # Attempt to train another classifier without adding more images.
        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_classifier(self.source.pk)

            log_message = "Source {} [{}] don't need new classifier.".format(
                self.source.name, self.source.pk)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_not_enough_train_data_since_last_classifier_submission(self):
        """
        Try to train when there haven't been enough training images added
        since the last training submission (which hasn't completed yet).
        """
        # Train one classifier.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()
        submit_classifier(self.source.pk)
        # Don't collect the training job.

        # Attempt to train another classifier without adding more images.
        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_classifier(self.source.pk)

            log_message = "Source {} [{}] don't need new classifier.".format(
                self.source.name, self.source.pk)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_one_unique_label(self):
        """
        Try to train when the training labelset ends up only having 1 unique
        label.
        """
        # Train data will have 2 unique labels, but val data will only have 1.
        # The intersection of the train data labelset and the val data labelset
        # is the training labelset. That labelset will be size 1 (only A),
        # thus fulfilling our test conditions.
        for _ in range(spacer_config.MIN_TRAINIMAGES):
            img = self.upload_image(
                self.user, self.source, image_options=dict(
                    filename=f'train{self.image_count}.png'))
            self.add_annotations(
                self.user, img, {1: 'A', 2: 'B', 3: 'A', 4: 'A', 5: 'B'})
        for _ in range(1):
            img = self.upload_image(
                self.user, self.source, image_options=dict(
                    filename=f'val{self.image_count}.png'))
            self.add_annotations(
                self.user, img, {1: 'A', 2: 'A', 3: 'A', 4: 'A', 5: 'A'})
        collect_all_jobs()

        with patch_logger('vision_backend.tasks', 'info') as log_messages:
            submit_classifier(self.source.pk)

            classifier = self.source.get_latest_robot(only_accepted=False)
            self.assertEqual(
                classifier.status, Classifier.LACKING_UNIQUE_LABELS,
                msg="Classifier status should be correct")

            source = self.source
            log_message = (
                f"Classifier {classifier.pk} for source {source.name}"
                f" [{source.pk}] was declined training, because the training"
                f" labelset ended up only having one unique label. Training"
                f" requires at least 2 unique labels.")
            self.assertIn(
                log_message, log_messages,
                msg="Should log the appropriate message")

        self.assertFalse(
            self.source.need_new_robot(),
            msg="Source should not immediately be considered for retraining")

    def do_training_with_features_race_condition(self):
        # Upload enough images for training, but don't annotate yet.
        # This should submit feature extract jobs.
        for i in range(spacer_config.MIN_TRAINIMAGES):
            self.upload_image(
                self.user, self.source,
                image_options=dict(filename=f'train{i}.png'))
        for i in range(1):
            self.upload_image(
                self.user, self.source,
                image_options=dict(filename=f'val{i}.png'))
        # Collect the feature extract jobs.
        collect_all_jobs()

        # Prepare points + annotations.
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(['Name', 'Column', 'Row', 'Label'])
        for image in self.source.image_set.all():
            # Training data must have at least 2 distinct labels.
            writer.writerow([image.metadata.name, 10, 10, 'A'])
            writer.writerow([image.metadata.name, 20, 20, 'B'])
        csv_file = ContentFile(stream.getvalue(), name='annotations.csv')

        self.client.force_login(self.user)
        self.client.post(
            reverse(
                'upload_annotations_csv_preview_ajax', args=[self.source.pk]),
            {'csv_file': csv_file},
        )
        # Upload points + annotations for all those images. This should submit
        # a training job, but not features jobs, because we'll prevent the
        # reset_features tasks from running to simulate having a delay in those
        # tasks.
        def noop_task(*args):
            pass
        with mock.patch('vision_backend.tasks.reset_features.run', noop_task):
            self.client.post(
                reverse('upload_annotations_ajax', args=[self.source.pk]),
            )

    train_fail_log_regex = re.compile(
        r'Training failed for classifier \d+\.')
    train_success_log_regex = re.compile(
        r'Classifier \d+ \[Source: [\w\s]+ \[\d+]] collected successfully.')

    @override_settings(MIN_NBR_ANNOTATED_IMAGES=spacer_config.MIN_TRAINIMAGES+1)
    @override_settings(ADMINS=[('Admin', 'admin@example.com')])
    def test_point_feature_mismatch_mail_admins(self):
        """
        Point locations submitted to training do not match the feature vector's
        point locations.
        Feature re-extraction does not happen for whatever reason,
        retraining attempts fail, and admins get mailed.
        """
        self.do_training_with_features_race_condition()

        def noop_task(*args):
            pass

        with \
                mock.patch(
                    'vision_backend.tasks.reset_features.run', noop_task), \
                patch_logger('vision_backend.tasks', 'info') \
                    as tasks_logs, \
                patch_logger('vision_backend.task_helpers', 'info') \
                    as task_helpers_logs:

            # Expected order of events here:
            # - Collect a single train job, failed because training ran on the
            #   new point locations + old features
            # - Since it's the 1st train fail in a row, tries training a 2nd
            #   time
            # - Since jobs are synchronous in testing, collects the 2nd train
            #   job while still in the job-collect loop. 2nd train failed
            #   for the same reason
            # - Does not reset features, since we're mocking reset features
            #   to be a no-op
            # - Tries training a 3rd time
            # - Collects since we're still in the job-collect loop, failed
            #   again for the same reason. Tries training a 4th time
            # - Same thing, collects and fails. Mails admins
            collect_all_jobs()

            fail_messages = [
                m for m in tasks_logs
                if self.train_fail_log_regex.fullmatch(m)]
            success_messages = [
                m for m in task_helpers_logs
                if self.train_success_log_regex.fullmatch(m)]
            self.assertEqual(len(fail_messages), 4)
            self.assertEqual(len(success_messages), 0)

        # Classifiers, earliest to latest
        classifiers = self.source.classifier_set.order_by('pk')
        classifier_statuses = [clf.status for clf in classifiers]
        self.assertListEqual(
            classifier_statuses,
            [Classifier.TRAIN_ERROR]*4,
            "Classifier statuses should be as expected")

        # Check for admin email
        self.assertEqual(len(mail.outbox), 1, msg="Should have sent an email")
        admin_email = mail.outbox[-1]
        self.assertListEqual(
            admin_email.to, ['admin@example.com'],
            msg="Recipients should be correct")
        self.assertListEqual(admin_email.cc, [], msg="cc should be empty")
        self.assertListEqual(admin_email.bcc, [], msg="bcc should be empty")
        self.assertEqual(
            "[CoralNet] Spacer job failed", admin_email.subject,
            msg="Subject should be correct")
        self.assertIn(
            "Traceback (most recent call last):", admin_email.body,
            msg="Email body should contain the error")

    @override_settings(MIN_NBR_ANNOTATED_IMAGES=spacer_config.MIN_TRAINIMAGES+1)
    def test_point_feature_mismatch_retrain_success(self):
        """
        Point locations submitted to training do not match the feature vector's
        point locations.
        Feature re-extraction happens and retraining succeeds.
        """
        self.do_training_with_features_race_condition()

        def mock_task(args, eta):
            # Reset features and then collect jobs.
            # Note that we mock apply_async(), not run(), so that we can call
            # the task function directly here. This should avoid an infinite
            # loop.
            image_id = args[0]
            reset_features(image_id)
            collect_all_jobs()

        with \
                mock.patch(
                    'vision_backend.tasks.reset_features.apply_async',
                    mock_task), \
                patch_logger('vision_backend.tasks', 'info') \
                    as tasks_logs, \
                patch_logger('vision_backend.task_helpers', 'info') \
                    as task_helpers_logs:

            # Expected order of events here:
            # - Collect a single train job, failed because training ran on the
            #   new point locations + old features
            # - Since it's the 1st train fail in a row, tries training a 2nd
            #   time
            # - Since jobs are synchronous in testing, collects the 2nd train
            #   job while still in the job-collect loop. 2nd train failed
            #   for the same reason
            # - Resets features, and collects those jobs immediately, since
            #   we're mocking reset features to call job collection right after
            # - Tries training a 3rd time
            # - Collects since we're still in the job-collect loop, succeeded
            #   this time
            collect_all_jobs()

            fail_messages = [
                m for m in tasks_logs
                if self.train_fail_log_regex.fullmatch(m)]
            success_messages = [
                m for m in task_helpers_logs
                if self.train_success_log_regex.fullmatch(m)]
            self.assertEqual(len(fail_messages), 2)
            self.assertEqual(len(success_messages), 1)

        # Classifiers, earliest to latest
        classifiers = self.source.classifier_set.order_by('pk')
        classifier_statuses = [clf.status for clf in classifiers]
        self.assertListEqual(
            classifier_statuses,
            [Classifier.TRAIN_ERROR]*2 + [Classifier.ACCEPTED],
            "Classifier statuses should be as expected")

        # Check for lack of admin mail
        self.assertEqual(
            len(mail.outbox), 0, msg="Should not have sent an email")

    def test_point_feature_mismatch_and_clf_already_deleted(self):
        """
        Point locations race condition, plus the classifier is somehow already
        deleted before collecting the train job.
        """
        self.do_training_with_features_race_condition()

        classifier = self.source.get_latest_robot(only_accepted=False)
        classifier_pk = classifier.pk
        classifier.delete()

        with patch_logger(
                'vision_backend.tasks', 'info') as log_messages:
            collect_all_jobs()

            self.assertIn(
                f"Training failed for classifier {classifier_pk}, although the"
                " classifier was already deleted.",
                log_messages,
                "Should log the appropriate message")

    def test_classifier_deleted_before_collection(self):
        """
        Run the train task, then delete the classifier from the DB, then
        try to collect the train result.
        """
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()
        msg = submit_classifier(self.source.pk)

        clf = self.source.get_latest_robot(only_accepted=False)
        clf.delete()

        with patch_logger(
                'vision_backend.task_helpers', 'info') as log_messages:
            collect_all_jobs()

            log_message = "Classifier {} was deleted. Aborting".format(
                msg.tasks[0].job_token)
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")

    def test_classifier_rejected(self):
        """
        Run the train task, then collect the classifier and find that it's
        not enough of an improvement over the previous.
        """
        def mock_train_msg(
                self_, acc, pc_accs, ref_accs, runtime):
            self_.acc = 0.6
            self_.pc_accs = [0.5]
            self_.ref_accs = ref_accs
            self_.runtime = runtime

        # Train one classifier.
        self.upload_images_for_training(
            train_image_count=spacer_config.MIN_TRAINIMAGES, val_image_count=1)
        collect_all_jobs()
        submit_classifier(self.source.pk)
        collect_all_jobs()

        # Upload enough additional images for the next training to happen.
        old_image_count = spacer_config.MIN_TRAINIMAGES + 1
        new_image_count = math.ceil(
            old_image_count*settings.NEW_CLASSIFIER_TRAIN_TH)
        added_image_count = new_image_count - old_image_count
        self.upload_images_for_training(
            train_image_count=added_image_count, val_image_count=0)
        collect_all_jobs()
        submit_classifier(self.source.pk)

        with patch_logger(
                'vision_backend.task_helpers', 'info') as log_messages:
            with override_settings(NEW_CLASSIFIER_IMPROVEMENT_TH=1.4):
                # Collect classifier. Use mock to specify current and previous
                # classifiers' accuracy.
                with mock.patch(
                        'spacer.messages.TrainClassifierReturnMsg.__init__',
                        mock_train_msg):
                    collect_all_jobs()

            clf = self.source.get_latest_robot(only_accepted=False)
            self.assertEqual(clf.status, Classifier.REJECTED_ACCURACY)
            log_message = (
                "Classifier {} [Source: {} [{}]] "
                "worse than previous. Not accepted. Max previous: {:.2f}, "
                "threshold: {:.2f}, this: {:.2f}".format(
                    clf.pk, self.source, self.source.pk,
                    0.5, 0.5*1.4, 0.6))
            self.assertIn(
                log_message, log_messages,
                "Should log the appropriate message")
