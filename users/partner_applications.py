from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import PartnerApplication


@transaction.atomic
def approve_partner_application(application, reviewer, notes=""):
    application = PartnerApplication.objects.select_for_update().select_related("user").get(pk=application.pk)
    if application.status != "pending":
        raise ValidationError(f"Cannot approve an application with status {application.status}.")

    user = application.user
    for field in [
        "first_name",
        "last_name",
        "phone",
        "email",
        "business_name",
        "business_type",
        "location",
        "pickup_address",
        "service_area",
        "machine_count",
        "pickup_latitude",
        "pickup_longitude",
    ]:
        setattr(user, field, getattr(application, field))
    user.role = "washer"
    user.staff_type = "washer"
    user.profile_complete = True
    user.save()

    application.status = "approved"
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.reviewer_notes = str(notes).strip()
    application.save(update_fields=["status", "reviewed_by", "reviewed_at", "reviewer_notes", "updated_at"])
    return application
