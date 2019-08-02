from andablog.views import EntriesList as AndablogEntriesList


class EntriesList(AndablogEntriesList):

    # Entries per page.
    paginate_by = 10
    # A non-zero value here would allow the last page to merge with the
    # second-last page, if the last page's entry count is small enough.
    # We'll disallow that behavior since "Showing 1-10 of 23" along with
    # "Page 1 of 2" seems pretty confusing.
    paginate_orphans = 0
