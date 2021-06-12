from ..models import CalcifyRateTable


def create_default_calcify_table(
        region, rates_dict, name=None, description=None):
    if name is None:
        name = "Table Name - {}".format(region)
    if description is None:
        description = "Table Description"

    table = CalcifyRateTable(
        name=name,
        description=description,
        rates_json=rates_dict,
        source=None,
        region=region,
    )
    table.save()
    return table
