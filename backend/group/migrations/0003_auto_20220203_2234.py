# Generated by Django 3.2.11 on 2022-02-03 13:34

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('group', '0002_alter_groupmember_is_admin'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='GroupApplication',
            new_name='GroupMemberJoin',
        ),
        migrations.AlterModelTable(
            name='groupmemberjoin',
            table='group_member_join',
        ),
    ]
