import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string


class Command(BaseCommand):

    help = "Generates the nginx.conf file"

    def handle(self, *args, **options):
        try:
            nginx_allowed_hosts = settings.NGINX_ALLOWED_HOSTS
        except AttributeError:
            raise CommandError("Must define the NGINX_ALLOWED_HOSTS setting.")

        # This string goes in a server_name line in the nginx conf.
        # That means the hosts should be space-separated.
        nginx_allowed_hosts_str = ' '.join(nginx_allowed_hosts)

        conf_file = os.path.join(settings.PROJECT_DIR, 'config', 'nginx.conf')
        with open(conf_file, 'w') as fp:
            fp.write(render_to_string('nginx_template.conf', {
                'nginx_allowed_hosts': nginx_allowed_hosts_str,
            }))

        self.stdout.write(self.style.SUCCESS(
            "Done: Generated config file at {f}.".format(f=conf_file)))
