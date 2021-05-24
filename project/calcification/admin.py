from django.contrib import admin

from .models import CalcifyRateTable


@admin.register(CalcifyRateTable)
class RateTableAdmin(admin.ModelAdmin):
    pass
