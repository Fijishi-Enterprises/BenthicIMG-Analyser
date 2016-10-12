from images.models import Source


def is_label_editable_by_user(label, user):
    if user.has_perm('labels.edit_label'):
        # Labelset committee members and superusers can edit all labels
        return True

    if label.verified:
        # Only committee/superusers can edit verified labels
        return False

    sources_using_label = \
        Source.objects.filter(labelset__locallabel__global_label=label) \
        .distinct()
    for source in sources_using_label:
        if not user.has_perm(Source.PermTypes.ADMIN.code, source):
            # This label is used by a source that this user isn't an
            # admin of; therefore, can't edit the label
            return False

    # The user is admin of all sources using this label, and the label
    # isn't verified; OK to edit
    return True
