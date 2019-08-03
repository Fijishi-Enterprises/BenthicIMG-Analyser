from andablog.models import Entry as AndablogEntry
from .managers import EntryManager


class Entry(AndablogEntry):
    """
    This is a proxy model: it uses the same database table as the parent
    model, but it changes some Python functionality.
    """
    class Meta:
        proxy = True

    objects = EntryManager()
