import json
import random
import re

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.test.client import Client
from django.urls import reverse
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = (
        "Submit a deploy API request for testing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'coralnet_username', type=str,
            help="CoralNet username to request as")
        parser.add_argument(
            'classifier_id', type=int, help="Classifier ID to use")
        parser.add_argument(
            'image_url', type=str,
            help="Image URL to submit for classification")

    def handle(self, *args, **options):
        # Get auth token without asking for password
        user = User.objects.get(username=options['coralnet_username'])
        token_instance, created = Token.objects.get_or_create(user=user)
        token = token_instance.key

        relative_url = reverse('api:deploy', args=[options['classifier_id']])

        request_data = json.dumps(dict(
            data=[dict(
                type='image',
                attributes=dict(
                    url=options['image_url'],
                    points=[
                        dict(
                            row=random.randint(1, 100),
                            column=random.randint(1, 100),
                        )
                        for _ in range(2)
                    ],
                ),
            )],
        ))

        client = Client()
        client.force_login(user)
        response = client.post(
            relative_url,
            data=request_data,
            content_type='application/vnd.api+json',
            Authorization=f'Token {token}',
        )

        if response.status_code >= 400:
            self.stdout.write("Error: " + response.data['errors'][0]['detail'])
            return

        location = response['Location']
        job_id = re.search(r'(\d+)', location).groups()[0]

        status_dashboard_url = reverse(
            'api_management:job_detail', args=[job_id])
        self.stdout.write(
            f"Deploy request sent. Check status here: {status_dashboard_url}")
