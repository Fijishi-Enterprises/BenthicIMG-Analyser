from andablog.views import (
    EntriesList as AndablogEntriesList,
    EntryDetail as AndablogEntryDetail)

from .models import Entry


class EntriesList(AndablogEntriesList):

    # Entries per page.
    paginate_by = 10
    # A non-zero value here would allow the last page to merge with the
    # second-last page, if the last page's entry count is small enough.
    # We'll disallow that behavior since "Showing 1-10 of 23" along with
    # "Page 1 of 2" seems pretty confusing.
    paginate_orphans = 0

    def get_queryset(self):
        """Restrict to Entries that the user is allowed to view."""
        return Entry.objects.get_visible_to_user(self.request.user)


class EntryDetail(AndablogEntryDetail):

    def get_queryset(self):
        """The queryset used to look up the Entry. We restrict to Entries
        that the user is allowed to view. If the Entry isn't there, we 404."""
        return Entry.objects.get_visible_to_user(self.request.user)
