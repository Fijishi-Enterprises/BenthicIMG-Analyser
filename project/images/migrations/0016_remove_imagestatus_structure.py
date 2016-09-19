## This migration should be viewed together with 0015. 
# 0015 adds a field and does the data-migrations.
# 0016 removes the old redundant fields
# The reason for this is postgresql does one migration in a single
# 'transaction'
# http://stackoverflow.com/questions/12838111/south-cannot-alter-table-because-it-has-pending-trigger-events
#
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0015_remove_imagestatus_class'),
    ]

    operations = [


        # Remove the whole Image Status model
        migrations.RemoveField(
            model_name='image',
            name='status',
        ),
        
        migrations.RemoveField(
            model_name='ImageStatus',
            name='annotatedByHuman',
        ),

        migrations.DeleteModel(
            name='ImageStatus',
        ),

    ]