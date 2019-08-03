from django.urls import reverse

from andablog.models import Entry as AndablogEntry

from .managers import EntryManager


class Entry(AndablogEntry):

    class Meta:
        # This is a proxy model: it uses the same database table as the parent
        # model, but it changes some Python functionality.
        proxy = True

        # Controls earliest() and latest().
        #
        # TODO: In Django 2.0, this can be a list. Might want to change this
        # to ['-is_published', 'published_timestamp'] so that
        # drafts are considered latest, followed by the latest-published entry.
        get_latest_by = 'published_timestamp'

    objects = EntryManager()

    def get_absolute_url(self):
        # Use `blog:` URL instead of `andablog:`.
        return reverse('blog:entry_detail', args=[self.slug])

    def next_newest_entry(self):
        # Even for admins, it doesn't really make sense to have drafts
        # included in previous/next links on the main site.
        # So we narrow it down to only published entries.
        published_entries = Entry.objects.get_published()

        if not self.is_published:
            # This is a draft, so this is considered newer than any
            # published entry.
            return None

        newer_entries = published_entries.filter(
            published_timestamp__gt=self.published_timestamp)
        if newer_entries.count() == 0:
            # No published entries are newer.
            return None

        # There is a newer published entry. Get the oldest of those.
        return newer_entries.earliest()

    def next_oldest_entry(self):
        published_entries = Entry.objects.get_published()

        if not self.is_published:
            # This is a draft, so this is considered newer than any
            # published entry. Thus the next oldest is the latest published.
            return published_entries.latest()

        older_entries = published_entries.filter(
            published_timestamp__lt=self.published_timestamp)
        if older_entries.count() == 0:
            # No published entries are older.
            return None

        # There is an older published entry. Get the newest of those.
        return older_entries.latest()
