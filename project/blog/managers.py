from django.db import models


class EntryManager(models.Manager):

    def get_visible_to_user(self, user):
        default_queryset = \
            super(EntryManager, self).get_queryset()

        if user.is_superuser:
            # Superusers can see every blog post.
            queryset = default_queryset
        else:
            # Other users can only see published (non-draft) blog posts.
            queryset = default_queryset.filter(is_published=True)

        # Drafts first, then latest to earliest publish date.
        return queryset.order_by('is_published', '-published_timestamp')
