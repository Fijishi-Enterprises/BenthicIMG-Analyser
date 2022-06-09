from io import StringIO

from lib.tests.utils import BaseTest

from ..utils import csv_to_dicts


class CsvToDictsTest(BaseTest):

    def test_missing_optional_column(self):
        lines = [
            'A,B',
            '1,2',
        ]
        csv_content = ''.join([line + '\n' for line in lines])
        dicts = csv_to_dicts(
            StringIO(csv_content),
            required_columns=dict(a='A', b='B'),
            optional_columns=dict(c='C'),
            unique_keys=[],
        )
        self.assertDictEqual(
            dicts[0], dict(a='1', b='2'),
            msg="dict should not have key for optional column")

    def test_missing_optional_cell(self):
        # Optional column is present, but cell is not; note how there's
        # no comma after the 2.
        lines = [
            'A,B,C',
            '1,2',
        ]
        csv_content = ''.join([line + '\n' for line in lines])
        dicts = csv_to_dicts(
            StringIO(csv_content),
            required_columns=dict(a='A', b='B'),
            optional_columns=dict(c='C'),
            unique_keys=[],
        )
        self.assertDictEqual(
            dicts[0], dict(a='1', b='2', c=''),
            msg="dict should have key for optional column")

    def test_blank_optional_cell(self):
        # Cell under the optional column is present, but blank; note how
        # there's a comma after the 2.
        # Since this is hard to distinguish from a missing optional cell,
        # we want the behavior to be the same as that case.
        # (But not necessarily the same as when the column header is absent.)
        lines = [
            'A,B,C',
            '1,2,',
        ]
        csv_content = ''.join([line + '\n' for line in lines])
        dicts = csv_to_dicts(
            StringIO(csv_content),
            required_columns=dict(a='A', b='B'),
            optional_columns=dict(c='C'),
            unique_keys=[],
        )
        self.assertDictEqual(
            dicts[0], dict(a='1', b='2', c=''),
            msg="dict should have key for optional column")
