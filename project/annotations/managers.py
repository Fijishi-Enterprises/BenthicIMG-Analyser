from django.db import models

from accounts.utils import get_robot_user, is_robot_user


class AnnotationManager(models.Manager):

    def update_point_annotation_if_applicable(
            self, point, label, now_confirmed, user_or_robot_version):
        """
        Update a single Point's Annotation in the database. If an Annotation
        exists for this point already, update it accordingly. Else, create a
        new Annotation.

        This function takes care of the logic for which annotations should be
        updated or not:
        - Don't overwrite confirmed with unconfirmed.
        - Only re-save the same label if overwriting unconfirmed with confirmed.

        This doesn't need to be used every time we save() an Annotation, but if
        the save has any kind of conditional logic on the annotation status
        (does the point already have an annotation? is the existing annotation
        confirmed or not?), then it's highly recommended to use this function.

        :param point: Point object we're interested in saving an Annotation to.
        :param label: Label object to save to the Annotation.
        :param now_confirmed: boolean saying whether the Annotation is
        considered confirmed or not.
        :param user_or_robot_version: a User if now_confirmed is True; a Robot
        if now_confirmed is False.
        """
        try:
            annotation = point.annotation
        except self.model.DoesNotExist:
            # This point doesn't have an annotation in the database yet.
            # Create a new annotation.
            new_annotation = self.model(
                point=point, image=point.image,
                source=point.image.source, label=label)
            if now_confirmed:
                new_annotation.user = user_or_robot_version
            else:
                new_annotation.user = get_robot_user()
                new_annotation.robot_version = user_or_robot_version
            new_annotation.save()
        else:
            # An annotation for this point exists in the database
            previously_confirmed = not is_robot_user(annotation.user)

            if previously_confirmed and not now_confirmed:
                # Never overwrite confirmed with unconfirmed.
                pass
            elif (not previously_confirmed and now_confirmed) \
                    or (label != annotation.label):
                # Previously unconfirmed, and now a human user is
                # confirming or changing it
                # OR
                # Label was otherwise changed
                # In either case, we update the annotation.
                annotation.label = label
                if now_confirmed:
                    annotation.user = user_or_robot_version
                else:
                    annotation.user = get_robot_user()
                    annotation.robot_version = user_or_robot_version
                annotation.save()
            # Else, there's nothing to save, so don't do anything.
