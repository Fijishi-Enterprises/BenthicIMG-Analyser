from django.db import models


class EventManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.model.type_for_subclass:
            queryset = queryset.filter(type=self.model.type_for_subclass)
        return queryset
