from django.contrib import admin

from .models import NewsItem, NewsSubItem

admin.site.register(NewsItem)
admin.site.register(NewsSubItem)
