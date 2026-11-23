from collections import defaultdict

from django.db import migrations, models


def normalize_phone(phone):
    phone = ''.join(
        character for character in str(phone).strip()
        if character.isdigit() or character == '+'
    )
    if phone.startswith('+'):
        phone = phone[1:]
    if not phone:
        return None
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    if not phone.startswith('254'):
        phone = '254' + phone
    return '+' + phone


def normalize_and_clear_duplicate_phones(apps, schema_editor):
    User = apps.get_model('users', 'User')
    using = schema_editor.connection.alias
    users_by_phone = defaultdict(list)
    normalized_by_id = {}

    for user in User.objects.using(using).only('id', 'phone').iterator():
        normalized_phone = normalize_phone(user.phone) if user.phone else None
        normalized_by_id[user.pk] = normalized_phone
        if normalized_phone:
            users_by_phone[normalized_phone].append(user.pk)

    duplicates = {
        phone: user_ids
        for phone, user_ids in users_by_phone.items()
        if len(user_ids) > 1
    }
    duplicate_user_ids = {
        user_id
        for user_ids in duplicates.values()
        for user_id in user_ids
    }

    for user_id, phone in normalized_by_id.items():
        User.objects.using(using).filter(pk=user_id).update(
            phone=None if user_id in duplicate_user_ids else phone
        )

    if duplicate_user_ids:
        print(
            'Cleared phone numbers from '
            f'{len(duplicate_user_ids)} accounts in {len(duplicates)} duplicate groups.'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_user_machine_count'),
    ]

    operations = [
        migrations.RunPython(normalize_and_clear_duplicate_phones),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
