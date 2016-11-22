import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string


class Command(BaseCommand):

    help = "Generates the nginx.conf file."

    def handle(self, *args, **options):
        # This string goes in a server_name line in the nginx conf.
        # That means the hosts should be space-separated.
        allowed_hosts_str = ' '.join(settings.ALLOWED_HOSTS)

        conf_file = os.path.join(settings.PROJECT_DIR, 'config', 'nginx.conf')
        with open(conf_file, 'w') as fp:
            fp.write(render_to_string('nginx_template.conf', {
                'allowed_hosts': allowed_hosts_str,
                'site_dir': settings.SITE_DIR,
                'static_root': settings.STATIC_ROOT,
                'use_https': settings.SESSION_COOKIE_SECURE,
            }))

        self.stdout.write(self.style.SUCCESS(
            "Done: Generated config file at {f}.".format(f=conf_file)))
