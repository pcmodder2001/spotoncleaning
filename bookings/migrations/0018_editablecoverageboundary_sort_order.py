from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0017_editablecoverageboundary'),
    ]

    operations = [
        migrations.AddField(
            model_name='editablecoverageboundary',
            name='sort_order',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='editablecoverageboundary',
            name='name',
            field=models.CharField(default='Service area', max_length=100),
        ),
        migrations.AlterField(
            model_name='editablecoverageboundary',
            name='slug',
            field=models.SlugField(max_length=40, unique=True),
        ),
    ]
