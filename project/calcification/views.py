import re

from django.shortcuts import get_object_or_404

from export.utils import create_csv_stream_response
from .models import CalcifyRateTable
from .utils import rate_table_json_to_csv


# TODO: Whenever we implement saving user-defined tables: If the table belongs to a source, require permission to that source.
def rate_table_download(request, table_id):
    """
    Main page for a particular label
    """
    rate_table = get_object_or_404(CalcifyRateTable, id=table_id)

    # Convert the rate table's name to a valid filename in Windows and
    # Linux/Mac (or at least make a reasonable effort to).
    # Convert chars that are problematic in either OS to underscores.
    #
    # Linux only disallows / (and the null char, but we'll ignore that case).
    # Windows:
    # https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions
    non_filename_chars_regex = re.compile(r'[<>:"/\\|?*]')
    csv_filename = non_filename_chars_regex.sub('_', rate_table.name)

    # Make a CSV stream response and write the data to it.
    response = create_csv_stream_response('{}.csv'.format(csv_filename))
    rate_table_json_to_csv(response, rate_table)

    return response
