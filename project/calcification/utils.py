import json

from .models import CalcifyRateTable


def get_default_calcify_tables():
    # Get the latest global table from each region.
    return CalcifyRateTable.objects.filter(source__isnull=True).order_by(
        'region', '-date').distinct('region')


def get_default_calcify_rates():
    tables = get_default_calcify_tables()
    return {
        table.region: json.loads(table.rates_json)
        for table in tables
    }
