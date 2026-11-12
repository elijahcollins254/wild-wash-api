from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from services.image_urls import (
    DEFAULT_SERVICE_IMAGE_BASE_URL,
    get_service_image_filename,
    get_service_image_url,
)
from services.models import Service


class Command(BaseCommand):
    help = "Map known service names to their public image URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            default=DEFAULT_SERVICE_IMAGE_BASE_URL,
            help="Public URL prefix for the uploaded service images.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace image URLs already configured on services.",
        )

    def handle(self, *args, **options):
        base_url = options["base_url"].strip()
        parsed_url = urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise CommandError("--base-url must be an absolute HTTP(S) URL.")

        updated = 0
        already_configured = 0
        unmapped = []

        with transaction.atomic():
            for service in Service.objects.order_by("pk"):
                filename = get_service_image_filename(service.name)
                if filename is None:
                    unmapped.append(service.name)
                    continue
                if service.image_link and not options["overwrite"]:
                    already_configured += 1
                    continue

                service.image_link = get_service_image_url(service.name, base_url)
                service.save(update_fields=("image_link", "updated_at"))
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Set image URLs for {updated} service(s); "
                f"left {already_configured} existing URL(s) unchanged."
            )
        )
        if unmapped:
            self.stderr.write(
                self.style.WARNING(
                    "No image mapping for service(s): " + ", ".join(sorted(set(unmapped)))
                )
            )
