from ..models import CalcifyRateTable


def create_default_calcify_table(region, rates_dict):
    table = CalcifyRateTable(
        name="Table Name - {}".format(region),
        description="Table Description",
        rates_json=rates_dict,
        source=None,
        region=region,
    )
    table.save()
    return table
