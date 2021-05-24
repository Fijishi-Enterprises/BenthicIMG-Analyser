import json

from ..models import CalcifyRateTable


class CalcifyTestMixin:

    @staticmethod
    def create_global_rate_table(region, rates_dict):
        table = CalcifyRateTable(
            name="Table Name - {}".format(region),
            description="Table Description",
            rates_json=json.dumps(rates_dict),
            source=None,
            region=region,
        )
        table.save()
