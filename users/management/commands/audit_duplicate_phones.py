from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from users.models import format_phone_number


class Command(BaseCommand):
    help = "Report duplicate phone groups before applying the uniqueness migration."

    def handle(self, *args, **options):
        User = get_user_model()
        users_by_phone = defaultdict(list)

        for user in User.objects.exclude(phone__isnull=True).exclude(phone="").only(
            "id", "username", "phone"
        ):
            normalized_phone = format_phone_number(user.phone)
            if normalized_phone:
                users_by_phone[normalized_phone].append(user)

        duplicates = {
            phone: users
            for phone, users in users_by_phone.items()
            if len(users) > 1
        }

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicate phone numbers found."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {len(duplicates)} duplicate phone number group(s):"
            )
        )
        for phone, users in sorted(duplicates.items()):
            self.stdout.write(f"\n{phone}")
            for user in sorted(users, key=lambda item: item.pk):
                self.stdout.write(f"  user_id={user.pk} username={user.username}")
        self.stdout.write(
            "\nThe uniqueness migration clears the phone from every account in each "
            "group. Save this report so you can reassign numbers afterward."
        )
