# orders/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from notifications.models import Notification
from django.contrib.auth import get_user_model
from users.models import Location
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=Order)
def order_status_update(sender, instance, created, update_fields=None, **kwargs):
    """Create notifications when order is created or updated"""
    
    # Prevent infinite recursion when we update order in auto-assign
    if update_fields is not None and set(update_fields) == {'rider', 'status', 'service_location'}:
        return
    # Also prevent if only code is being updated
    if update_fields is not None and update_fields == ['code']:
        return
    
    # Notify customer about order status changes
    if instance.user:
        if created:
            message = f"Your order {instance.code} has been created."
            notification_type = 'new_order'
        else:
            message = f"Your order {instance.code} is now {instance.get_status_display()}."
            notification_type = 'order_update'
        
        try:
            Notification.objects.create(
                user=instance.user,
                order=instance,
                message=message,
                notification_type=notification_type
            )
        except Exception as e:
            print(f"Error creating customer notification: {e}")
    
    # DISABLED: Admin SMS notification is now sent from perform_create() in views.py
    # This avoids duplicate SMS messages being sent to admin
    # if created:
    #     try:
    #         from services.sms_service import send_order_notification_sms
    #         admin_phone = settings.ADMIN_PHONE_NUMBER
    #         
    #         # Only send if API credentials are configured
    #         if settings.AFRICAS_TALKING_API_KEY and admin_phone:
    #             result = send_order_notification_sms(instance, admin_phone)
    #             if result['status'] == 'success':
    #                 logger.info(f"Admin SMS notification sent for order {instance.code}")
    #             else:
    #                 logger.warning(f"Failed to send admin SMS for order {instance.code}: {result.get('message')}")
    #     except Exception as e:
    #         logger.error(f"Error sending admin SMS notification for order {instance.code}: {str(e)}")
    
    # Auto-assign riders for all orders (both manual and online) that don't have one yet
    # This ensures riders get SMS notifications and customers get updates
    if created and not instance.rider:
        try:
            service_location = instance.service_location
            
            # If no service_location, try to infer from user's location or pickup address
            if not service_location:
                # Try to match from user's location field
                if instance.user and instance.user.location:
                    user_location = instance.user.location.lower().strip()
                    service_location = Location.objects.filter(
                        name__icontains=user_location,
                        is_active=True
                    ).first()
                
                # If still no location, try to extract from pickup_address
                if not service_location:
                    # Try to find any active location that matches the pickup address
                    locations = Location.objects.filter(is_active=True)
                    for loc in locations:
                        if loc.name.lower() in instance.pickup_address.lower():
                            service_location = loc
                            break
                
                # If still no match, assign to the first active location with riders
                if not service_location:
                    service_location = Location.objects.filter(is_active=True).first()
            
            # DISABLED: Auto-assignment of riders - now manual by admin
            # Get all riders assigned to this location, sorted by completed_jobs (ascending)
            # to distribute work evenly
            # if service_location:
            #     riders = User.objects.filter(
            #         role='rider',
            #         service_location=service_location,
            #         is_active=True
            #     ).select_related('rider_profile').order_by('rider_profile__completed_jobs')
            #
            #     if riders.exists():
            #         # Auto-assign to the first available rider (least busy)
            #         assigned_rider = riders.first()
            #         instance.rider = assigned_rider
            #         instance.service_location = service_location
            #         instance.status = 'pending_assignment'  # Keep status as pending_assignment for manual orders
            #         instance.save(update_fields=['rider', 'status', 'service_location'])
            #
            #         # Notify the assigned rider
            #         message = f"Order {instance.code} assigned to you. Pickup: {instance.pickup_address[:50]}..."
            #         Notification.objects.create(
            #             user=assigned_rider,
            #             order=instance,
            #             message=message,
            #             notification_type='new_order'
            #         )
            #         print(f"[ASSIGNED] Order {instance.code} assigned to rider {assigned_rider.username} in {service_location.name}")
            #     else:
            #         # No riders in this location, try to assign to any available rider
            #         all_riders = User.objects.filter(
            #             role='rider',
            #             is_active=True
            #         ).select_related('rider_profile').order_by('rider_profile__completed_jobs')
            #
            #         if all_riders.exists():
            #             assigned_rider = all_riders.first()
            #             instance.rider = assigned_rider
            #             instance.service_location = service_location
            #             instance.status = 'pending_assignment'
            #             instance.save(update_fields=['rider', 'status', 'service_location'])
            #
            #             message = f"Order {instance.code} assigned to you (alternate location). Pickup: {instance.pickup_address[:50]}..."
            #             Notification.objects.create(
            #                 user=assigned_rider,
            #                 order=instance,
            #                 message=message,
            #                 notification_type='new_order'
            #             )
            #             print(f"[ASSIGNED-ALT] Order {instance.code} assigned to rider {assigned_rider.username} (alternate location)")
            #         else:
            #             print(f"[NO-RIDERS] No riders available for order {instance.code}")
            # else:
            #     print(f"[NO-LOCATION] Could not determine location for order {instance.code}")
                
        except Exception as e:
            print(f"Error in auto-assign logic for order {instance.code}: {e}")
            import traceback
            traceback.print_exc()


