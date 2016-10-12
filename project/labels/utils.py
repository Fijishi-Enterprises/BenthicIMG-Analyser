from images.models import Source


def is_label_editable_by_user(label, user):
    if user.has_perm('labels.change_label'):
        # Labelset committee members and superusers can edit all labels
        return True

    if label.verified:
        # Only committee/superusers can edit verified labels
        return False

    sources_using_label = \
        Source.objects.filter(labelset__locallabel__global_label=label) \
        .distinct()
    if not sources_using_label:
        # Labels not in any source can only be edited by the committee.
        # It's probably a corner case, but it's likely confusing for users
        # if they see they're able to edit such a label. And it's best if
        # free-for-all edit situations aren't even possible.
        return False

    for source in sources_using_label:
        if not user.has_perm(Source.PermTypes.ADMIN.code, source):
            # This label is used by a source that this user isn't an
            # admin of; therefore, can't edit the label
            return False

    # The user is admin of all 1+ sources using this label, and the label
    # isn't verified; OK to edit
    return True
