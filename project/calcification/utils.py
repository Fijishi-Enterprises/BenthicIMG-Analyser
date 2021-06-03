import csv

from django.core.cache import cache

from labels.models import Label
from .models import CalcifyRateTable


def get_default_calcify_tables():
    # Get the latest global table from each region.
    tables = CalcifyRateTable.objects.filter(source__isnull=True).order_by(
        'region', '-date').distinct('region')
    return {
        table.region: table
        for table in tables
    }


def get_default_calcify_rates():
    cache_key = 'default_calcify_rates'

    # Check for cached value
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    # No cached value available
    tables = get_default_calcify_tables()
    rates = {
        region: table.rates_json
        for region, table in tables.items()
    }
    # Cache for 10 minutes
    cache.set(cache_key, rates, 60*10)
    return rates


def label_has_calcify_rates(label):
    rates_by_region = get_default_calcify_rates()
    return any([
        str(label.pk) in region_rates
        for _, region_rates in rates_by_region.items()
    ])


def rate_table_json_to_csv(csv_stream, rate_table):
    fieldnames = [
        "Label",
        "Mean rate",
        "Lower bound",
        "Upper bound",
    ]
    writer = csv.DictWriter(csv_stream, fieldnames)
    writer.writeheader()

    rates = rate_table.rates_json
    label_ids = [label_id for label_id in rates.keys()]
    # Get the label names we need with O(1) queries.
    label_names = {
        str(label['pk']): label['name']
        for label
        in Label.objects.filter(pk__in=label_ids).values('pk', 'name')
    }

    for label_id, label_rates in rates.items():
        writer.writerow({
            "Label": label_names[label_id],
            "Mean rate": label_rates['mean'],
            "Lower bound": label_rates['lower_bound'],
            "Upper bound": label_rates['upper_bound'],
        })
