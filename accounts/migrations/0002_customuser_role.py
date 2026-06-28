from django.db import migrations, models


def set_roles_from_staff(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.filter(is_staff=True).update(role='admin')
    CustomUser.objects.filter(is_staff=False).update(role='standard')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('standard', 'Standard user'),
                    ('engineer', 'Engineer'),
                    ('admin', 'Admin'),
                ],
                default='standard',
                max_length=20,
            ),
        ),
        migrations.RunPython(set_roles_from_staff, migrations.RunPython.noop),
    ]
