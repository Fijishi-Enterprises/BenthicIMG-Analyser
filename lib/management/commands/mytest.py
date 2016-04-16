from django.core.management.base import NoArgsCommand
from django.core.management.commands.test import Command as TestCommand
from django.core.management import call_command

class Command(NoArgsCommand):
    option_list = TestCommand.option_list
    help = "Runs unit tests for only our project's apps, not 3rd party apps."

    requires_system_checks = False

    def handle_noargs(self, **options):
        from django.conf import settings

        print "Running tests for the following apps:\n{0}\n".format(
            ', '.join(settings.PROJECT_APPS))

        call_command('test', *settings.PROJECT_APPS, **options)

