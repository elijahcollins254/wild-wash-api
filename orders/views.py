# orders/views.py
from django.db import models
from django.db.models import Prefetch
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Order
from .serializers import OrderListSerializer, OrderCreateSerializer
from users.permissions import LocationBasedPermission
from users.models import Location
class StaffCreateOrderView(APIView):
    """
    POST -> Create a manual order for a customer (by staff)
    Only accessible by staff members
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Check if user is staff
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'error': 'Only staff members can create manual orders'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Use the OrderCreateSerializer to handle order creation
        serializer = OrderCreateSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            try:
                order = serializer.save()
                
                # Create in-app notifications for admin and customer
                try:
                    from notifications.models import Notification
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    
                    # 1. Notify customer (user who dropped off items)
                    if order.user:
                        Notification.objects.create(
                            user=order.user,
                            order=order,
                            message=f"Your order {order.code} has been created by staff.",
                            notification_type='new_order'
                        )
                    
                    # 2. Notify all admins
                    admin_users = User.objects.filter(is_superuser=True, is_active=True)
                    services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                    
                    for admin in admin_users:
                        Notification.objects.create(
                            user=admin,
                            order=order,
                            message=f"Manual order {order.code} created by {request.user.username}",
                            notification_type='new_order'
                        )
                
                except Exception as notif_error:
                    print(f"⚠ Error creating notifications: {str(notif_error)}")
                
                # Send SMS to admin and customer (no rider assigned yet for manual orders)
                try:
                    from django.conf import settings
                    from services.sms_service import AfricasTalkingSMSService
                    
                    admin_phone = settings.ADMIN_PHONE_NUMBER
                    
                    # Format services list
                    services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                    user_name = order.user.get_full_name() or order.user.username if order.user else order.customer_name or 'Customer'
                    # Get customer phone from user.phone OR customer_phone field (for walk-in orders)
                    user_phone = (order.user.phone if order.user and order.user.phone else None) or \
                                 (order.customer_phone if order.customer_phone else None) or None
                    
                    # 1. Send SMS to CUSTOMER (user who dropped off items)
                    if user_phone and str(user_phone).strip():
                        try:
                            from services.sms_service import format_phone_number
                            from django.utils import timezone
                            sms_service = AfricasTalkingSMSService()
                            # Format phone number to international format
                            formatted_phone = format_phone_number(user_phone)
                            order_url = f"https://www.wildwash.co.ke/orders/{order.code}"
                            
                            # Extract clean pickup address and calculate hours for estimated delivery
                            clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                            if order.estimated_delivery:
                                hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                                est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                            else:
                                est_time = 'TBD'
                            
                            customer_message = (
                                f"WILDWASH SERVICES\n"
                                f"Order Created!\n"
                                f"Order #: {order.code}\n"
                                f"Services: {services}\n"
                                f"Pickup: {clean_pickup}\n"
                                f"Price: KES {order.price or 'TBD'}\n"
                                f"Est. Delivery: {est_time}\n"
                                f"View: {order_url}\n"
                                f"We'll update you when it's ready!"
                            )
                            
                            result = sms_service.send_sms(formatted_phone, customer_message)
                            
                            if result and result.get('status') == 'success':
                                print(f"✓ Customer SMS sent to {formatted_phone} for order {order.code}")
                            else:
                                error_msg = result.get('message', 'Unknown error') if result else 'No response'
                                print(f"⚠ Failed to send customer SMS: {error_msg}")
                        
                        except Exception as sms_error:
                            print(f"⚠ Error sending customer SMS: {str(sms_error)}")
                            import traceback
                            traceback.print_exc()
                    
                    # 2. Send SMS to ADMIN
                    if admin_phone:
                        try:
                            from django.utils import timezone
                            sms_service = AfricasTalkingSMSService()
                            order_url = f"https://www.wildwash.co.ke/orders/{order.code}"
                            
                            # Extract clean pickup address and calculate hours for estimated delivery
                            clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                            if order.estimated_delivery:
                                hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                                est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                            else:
                                est_time = 'TBD'
                            
                            admin_message = (
                                f"MANUAL ORDER CREATED!\n"
                                f"Order #: {order.code}\n"
                                f"Customer: {user_name}\n"
                                f"Phone: {user_phone or 'N/A'}\n"
                                f"Pickup: {clean_pickup}\n"
                                f"Dropoff: {order.dropoff_address}\n"
                                f"Services: {services}\n"
                                f"Items: {order.items}\n"
                                f"Price: KES {order.price or 'TBD'}\n"
                                f"Est. Delivery: {est_time}\n"
                                f"Created By: {request.user.username}\n"
                                f"Status: {order.get_actual_status_display()}\n"
                                f"Manage: {order_url}"
                            )
                            
                            result = sms_service.send_sms(admin_phone, admin_message)
                            
                            if result and result.get('status') == 'success':
                                print(f"✓ Admin SMS sent to {admin_phone} for order {order.code}")
                            else:
                                error_msg = result.get('message', 'Unknown error') if result else 'No response'
                                print(f"⚠ Failed to send admin SMS: {error_msg}")
                        
                        except Exception as sms_error:
                            print(f"⚠ Error sending admin SMS: {str(sms_error)}")
                            import traceback
                            traceback.print_exc()
                
                except Exception as e:
                    print(f"⚠ Error in SMS notification block: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                return Response(
                    OrderListSerializer(order, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response(
                    {'error': f'Failed to create order: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )


class RequestedOrdersListView(generics.ListAPIView):
    """
    GET -> List all unassigned orders with status 'requested'
    Only for admin/staff to see pending orders
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get all unassigned requested orders
        """
        return Order.objects.filter(
            status='requested',
            rider__isnull=True
        ).select_related('user', 'service', 'service_location').prefetch_related('services').order_by('-created_at')

class RiderOrderListView(generics.ListAPIView):
    """
    GET -> List orders assigned to the authenticated rider
    For washers: Show 'in_progress' orders to wash
    For folders: Show 'washed' orders to fold
    For riders: Show 'ready' and 'delivered' orders for delivery
    Excludes orders with: Cleaning, fumigation, cctv installation, shower installation
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Get orders based on user's staff type
        """
        user = self.request.user
        excluded_services = ['Cleaning', 'fumigation', 'cctv installation', 'shower installation']
        
        # For washers: show in_progress orders
        if hasattr(user, 'staff_type') and user.staff_type == 'washer':
            queryset = Order.objects.filter(
                service_location=user.service_location,
                status='in_progress',
                washer__isnull=True  # Not yet assigned to a washer
            ).exclude(
                services__name__in=excluded_services
            ).distinct().select_related('user', 'service', 'rider', 'service_location').prefetch_related('services').order_by('-created_at')
            
            print(f"\n[DEBUG WasherOrders] Washer {user.username} (ID: {user.id}) querying in_progress orders")
            print(f"[DEBUG] Total in_progress orders: {queryset.count()}")
        
        # For folders: show washed orders
        elif hasattr(user, 'staff_type') and user.staff_type == 'folder':
            queryset = Order.objects.filter(
                service_location=user.service_location,
                status='washed',
                folder__isnull=True  # Not yet assigned to a folder
            ).exclude(
                services__name__in=excluded_services
            ).distinct().select_related('user', 'service', 'rider', 'service_location').prefetch_related('services').order_by('-created_at')
            
            print(f"\n[DEBUG FolderOrders] Folder {user.username} (ID: {user.id}) querying washed orders")
            print(f"[DEBUG] Total washed orders: {queryset.count()}")
        
        # For riders: show ready and delivered orders
        else:
            queryset = Order.objects.filter(
                rider=user,
                status__in=['in_progress', 'picked', 'ready', 'delivered']
            ).exclude(
                services__name__in=excluded_services
            ).distinct().select_related('user', 'service', 'rider', 'service_location').prefetch_related('services').order_by('-created_at')
            
            print(f"\n[DEBUG RiderOrders] Rider {user.username} (ID: {user.id}) querying orders")
            print(f"[DEBUG] Total orders assigned to this rider: {queryset.count()}")
        
        return queryset

    def post(self, request, *args, **kwargs):
        """Accept an order"""
        order_id = request.data.get('order_id')
        action = request.data.get('action', 'accept')  # 'accept' or 'reject'

        try:
            order = Order.objects.get(
                id=order_id,
                rider__isnull=True,
                status__iexact='requested'  # case-insensitive match
            )
            if action == 'accept':
                order.rider = request.user
                order.status = 'in_progress'  # Change status to in_progress directly
                order.save()
                return Response({'message': 'Order accepted successfully', 'order': OrderListSerializer(order).data})
            else:
                return Response({'message': 'Order rejected'})
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found or already assigned'},
                status=status.HTTP_404_NOT_FOUND
            )

class OrderUpdateView(APIView):
    """
    PATCH -> Update order status, quantity, weight, and description
    Sends notification to rider when status changes to 'ready' (ready for delivery)
    """
    permission_classes = [permissions.IsAuthenticated, LocationBasedPermission]

    def patch(self, request, *args, **kwargs):
        try:
            order_id = request.query_params.get('id')
            if not order_id:
                return Response({'error': 'Order ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            order = Order.objects.get(id=order_id)
            
            # Check if the staff member has permission for this location
            # Allow: superusers, or staff with matching service_location, or any staff with washer/folder role
            if request.user.is_staff and not request.user.is_superuser:
                has_staff_type = hasattr(request.user, 'staff_type') and request.user.staff_type in ['washer', 'folder']
                has_location_match = request.user.service_location and order.service_location == request.user.service_location
                
                if not has_staff_type and not has_location_match:
                    return Response({'error': 'You do not have permission to update this order'}, 
                                 status=status.HTTP_403_FORBIDDEN)

            # Determine incoming values and capture old values for audit BEFORE mutating
            new_status = request.data.get('status')
            old_status = order.status
            status_changed_to_ready = new_status and new_status.lower() == 'ready' and old_status.lower() != 'ready'
            status_changed_to_washed = new_status and new_status.lower() == 'washed' and old_status.lower() != 'washed'

            # Capture old values before update
            old_values = {
                'status': old_status,
                'rider': order.rider,
                'quantity': getattr(order, 'quantity', None),
                'weight_kg': getattr(order, 'weight_kg', None),
                'description': getattr(order, 'description', None),
                'actual_price': getattr(order, 'actual_price', None),
                'delivered_at': getattr(order, 'delivered_at', None),
            }

            print(f"\n[DEBUG OrderUpdate] Order {order.code}")
            print(f"[DEBUG] Old status: {old_status}, New status: {new_status}")
            print(f"[DEBUG] Status changed to ready: {status_changed_to_ready}")
            print(f"[DEBUG] Current rider: {order.rider.username if order.rider else 'None'}")

            # Update status if provided
            if new_status:
                order.status = new_status

            # Update rider if provided (for manual assignment by admin)
            rider_id = request.data.get('rider')
            if rider_id is not None:
                try:
                    from users.models import User
                    rider = User.objects.get(id=rider_id, role='rider', is_active=True)
                    old_rider = order.rider
                    order.rider = rider
                    # Update status to 'requested' if it was 'pending_assignment'
                    if order.status == 'pending_assignment':
                        order.status = 'requested'
                    print(f"[DEBUG] Rider assigned: {rider.username} (was: {old_rider.username if old_rider else 'None'})")

                    # Send notification to the newly assigned rider
                    from notifications.models import Notification
                    message = f"Order {order.code} assigned to you. Pickup: {order.pickup_address[:50]}..."
                    Notification.objects.create(
                        user=rider,
                        order=order,
                        message=message,
                        notification_type='new_order'
                    )
                    print(f"✓ Notification sent to rider {rider.username} for order {order.code}")

                    # Send SMS to the newly assigned rider
                    try:
                        from django.conf import settings
                        from services.sms_service import AfricasTalkingSMSService, format_phone_number
                        from django.utils import timezone

                        rider_phone = rider.phone if hasattr(rider, 'phone') and rider.phone else None
                        rider_phone = None if rider_phone and not str(rider_phone).strip() else rider_phone

                        if rider_phone and str(rider_phone).strip():
                            sms_service = AfricasTalkingSMSService()
                            rider_url = f"https://www.wildwash.co.ke/rider/orders/{order.code}"

                            # Format services list
                            services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                            user_name = order.user.get_full_name() or order.user.username if order.user else order.customer_name or 'Customer'
                            user_phone = (order.user.phone if order.user and order.user.phone else None) or \
                                       (order.customer_phone if order.customer_phone else None) or None

                            # Extract clean pickup address and calculate hours for estimated delivery
                            clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                            if order.estimated_delivery:
                                hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                                est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                            else:
                                est_time = 'TBD'

                            rider_message = (
                                f"WILDWASH SERVICES\n"
                                f"New Order Assigned!\n"
                                f"Order #: {order.code}\n"
                                f"Customer: {user_name}\n"
                                f"Phone: {user_phone or 'N/A'}\n"
                                f"Pickup: {clean_pickup}\n"
                                f"Dropoff: {order.dropoff_address}\n"
                                f"Services: {services}\n"
                                f"Items: {order.items}\n"
                                f"Price: KES {order.price or 'TBD'}\n"
                                f"Est. Delivery: {est_time}\n"
                                f"Accept: {rider_url}"
                            )

                            formatted_phone = format_phone_number(rider_phone)
                            result = sms_service.send_sms(formatted_phone, rider_message)

                            if result and result.get('status') == 'success':
                                print(f"✓ Rider SMS sent to {rider.username} ({formatted_phone}) for order {order.code}")
                            else:
                                error_msg = result.get('message', 'Unknown error') if result else 'No response'
                                print(f"⚠ Failed to send rider SMS to {rider.username}: {error_msg}")
                        else:
                            print(f"⚠ No phone number found for rider {rider.username}")

                    except Exception as sms_error:
                        print(f"⚠ Error sending rider SMS: {str(sms_error)}")
                        import traceback
                        traceback.print_exc()

                except User.DoesNotExist:
                    return Response({'error': 'Invalid rider selected'}, status=status.HTTP_400_BAD_REQUEST)

            # Update rider-provided details
            quantity = request.data.get('quantity')
            if quantity is not None:
                order.quantity = quantity

            weight_kg = request.data.get('weight_kg')
            if weight_kg is not None:
                order.weight_kg = weight_kg

            description = request.data.get('description')
            if description is not None:
                order.description = description

            # Update staff-entered actual price if provided
            actual_price = request.data.get('actual_price')
            if actual_price is not None:
                try:
                    # attempt to coerce into Decimal-compatible numeric string
                    from decimal import Decimal
                    order.actual_price = Decimal(str(actual_price))
                except Exception:
                    # fallback to raw assignment; DB will validate/raise if invalid
                    order.actual_price = actual_price

            order.save()

            # Accept delivered_at from request (rider marking delivery)
            delivered_at = request.data.get('delivered_at')
            if delivered_at is not None:
                try:
                    # Parse and set delivered_at; allow ISO strings
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(str(delivered_at))
                    if parsed:
                        order.delivered_at = parsed
                        order.save(update_fields=['delivered_at'])
                except Exception:
                    # ignore parse errors
                    pass

            # Record events for changes
            from .models import OrderEvent
            actor = request.user if request.user.is_authenticated else None

            # status change
            if new_status and (old_status != new_status):
                OrderEvent.objects.create(
                    order=order,
                    actor=actor,
                    event_type='status_changed',
                    data={'old': old_status, 'new': new_status}
                )

            # rider change
            if rider_id is not None and old_values.get('rider') != order.rider:
                OrderEvent.objects.create(
                    order=order,
                    actor=actor,
                    event_type='rider_assigned',
                    data={'old': old_values.get('rider').username if old_values.get('rider') else None, 'new': order.rider.username}
                )

            # details changed (quantity, weight, description)
            changed_details = {}
            if quantity is not None and quantity != old_values.get('quantity'):
                changed_details['quantity'] = {'old': old_values.get('quantity'), 'new': quantity}
            if weight_kg is not None and weight_kg != old_values.get('weight_kg'):
                changed_details['weight_kg'] = {'old': old_values.get('weight_kg'), 'new': weight_kg}
            if description is not None and description != old_values.get('description'):
                changed_details['description'] = {'old': old_values.get('description'), 'new': description}
            # actual_price changed
            if actual_price is not None:
                # Compare with old value (coerce to string/Decimal as needed)
                old_ap = old_values.get('actual_price')
                # If Decimal objects, string comparison is safe for equality check here
                if str(old_ap) != str(actual_price):
                    changed_details['actual_price'] = {'old': old_ap, 'new': actual_price}
            # delivered_at changed (rider marking delivered)
            delivered_at_req = request.data.get('delivered_at')
            if delivered_at_req is not None:
                old_da = old_values.get('delivered_at')
                # compare as ISO string where possible
                if str(old_da) != str(delivered_at_req):
                    changed_details['delivered_at'] = {'old': old_da, 'new': delivered_at_req}

            if changed_details:
                OrderEvent.objects.create(
                    order=order,
                    actor=actor,
                    event_type='details_updated',
                    data=changed_details
                )
            print(f"[DEBUG] Order saved with status: {order.status}")

            # Handle status change to 'washed' - washer marks as washed
            if status_changed_to_washed:
                # Track who washed the order
                if request.user.is_staff or (hasattr(request.user, 'staff_type') and request.user.staff_type == 'washer'):
                    order.washer = request.user
                    from django.utils import timezone
                    order.washed_at = timezone.now()
                    order.save(update_fields=['washer', 'washed_at'])
                    print(f"✓ Order {order.code} marked as washed by {request.user.username}")
                
                # Create notification for folder staff at the same location
                try:
                    from notifications.models import Notification
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    
                    # Notify all folder staff at this location
                    folder_staff = User.objects.filter(
                        service_location=order.service_location,
                        staff_type='folder',
                        is_active=True
                    )
                    
                    services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                    
                    for folder in folder_staff:
                        Notification.objects.create(
                            user=folder,
                            order=order,
                            message=f"Order {order.code} ({services}) is ready for folding!",
                            notification_type='order_update'
                        )
                        print(f"✓ Notification sent to folder {folder.username} for order {order.code}")
                    
                    # Send SMS to folder staff
                    if folder_staff.exists():
                        try:
                            from services.sms_service import AfricasTalkingSMSService
                            
                            sms_service = AfricasTalkingSMSService()
                            customer_name = order.user.get_full_name() or order.user.username if order.user else 'Customer'
                            
                            sms_message = (
                                f"Order Ready for Folding!\n"
                                f"Order #: {order.code}\n"
                                f"Customer: {customer_name}\n"
                                f"Service: {services}\n"
                                f"Items: {order.quantity or order.items}\n"
                                f"Weight: {order.weight_kg}kg\n"
                                f"Please proceed with folding. Thank you!"
                            )
                            
                            for folder in folder_staff:
                                if hasattr(folder, 'phone') and folder.phone:
                                    sms_result = sms_service.send_sms(folder.phone, sms_message)
                                    if sms_result and sms_result.get('status') == 'success':
                                        print(f"✓ SMS sent to folder {folder.username}")
                        except Exception as e:
                            print(f"⚠ SMS service error notifying folder: {str(e)}")
                
                except Exception as e:
                    print(f"⚠ Error notifying folder staff: {str(e)}")
            
            # Handle status change to 'ready'
            if status_changed_to_ready:
                # Track who folded the order (for ready status set by folder)
                if hasattr(request.user, 'staff_type') and request.user.staff_type == 'folder':
                    order.folder = request.user
                    from django.utils import timezone
                    order.folded_at = timezone.now()
                    order.save(update_fields=['folder', 'folded_at'])
                    print(f"✓ Order {order.code} marked as ready by folder {request.user.username}")
                
                from notifications.models import Notification
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                assigned_rider = None
                
                # DISABLED: Auto-assignment of riders - now manual by admin
                # For manual orders created by staff, only auto-assign if delivery address was provided
                # if order.order_type == 'manual':
                #     print(f"[DEBUG] Order {order.code} is a manual order")
                #     print(f"[DEBUG] Order created by staff: {order.created_by.username if order.created_by else 'Unknown'}")
                #
                #     # Check if delivery address was provided (not the default "To be assigned")
                #     has_delivery_address = (
                #         order.dropoff_address and
                #         order.dropoff_address.lower() != 'to be assigned' and
                #         order.dropoff_address.strip() != ''
                #     )
                #
                #     if has_delivery_address:
                #         print(f"[DEBUG] Delivery address provided: {order.dropoff_address}")
                #         print(f"[DEBUG] Assigning to available rider...")
                #         # Only auto-assign if delivery address was provided
                #         if not order.rider and order.service_location:
                #             available_riders = User.objects.filter(
                #                 role='rider',
                #                 service_location=order.service_location,
                #                 is_active=True
                #             ).select_related('rider_profile').order_by('rider_profile__completed_jobs')
                #
                #             if available_riders.exists():
                #                 assigned_rider = available_riders.first()
                #                 order.rider = assigned_rider
                #                 # Update status from pending_assignment to requested if it was pending
                #                 if order.status == 'pending_assignment':
                #                     order.status = 'requested'
                #                 order.save(update_fields=['rider', 'status'])
                #                 print(f"✓ Order {order.code} assigned to rider {assigned_rider.username}")
                #             else:
                #                 print(f"⚠ No available riders in {order.service_location.name}")
                #     else:
                #         print(f"[DEBUG] No delivery address - order stays with staff creator")
                #
                # # If order doesn't have a rider assigned, assign it to an available rider in the same location
                # elif not order.rider and order.service_location:
                #     print(f"[DEBUG] No rider assigned yet, finding available rider...")
                #     available_riders = User.objects.filter(
                #         role='rider',
                #         service_location=order.service_location,
                #         is_active=True
                #     ).select_related('rider_profile').order_by('rider_profile__completed_jobs')
                #
                #     print(f"[DEBUG] Available riders in {order.service_location.name}: {available_riders.count()}")
                #
                #     if available_riders.exists():
                #         assigned_rider = available_riders.first()
                #         order.rider = assigned_rider
                #         # Update status from pending_assignment to requested if it was pending
                #         if order.status == 'pending_assignment':
                #             order.status = 'requested'
                #         order.save(update_fields=['rider', 'status'])
                #         print(f"✓ Order {order.code} assigned to rider {assigned_rider.username}")
                #     else:
                #         print(f"⚠ No available riders in {order.service_location.name} for order {order.code}")
                # else:
                #     # Rider already assigned, use existing rider
                #     assigned_rider = order.rider
                #     if assigned_rider:
                #         print(f"[DEBUG] Rider already assigned: {assigned_rider.username}")
                #
                # # Send notification to rider if assigned
                # if assigned_rider:
                #     message = f"Order {order.code} is ready for delivery! Pickup from: {order.pickup_address}"
                #     notification = Notification.objects.create(
                #         user=assigned_rider,
                #         order=order,
                #         message=message,
                        notification_type='order_update'
                    )
                    print(f"✓ Notification (ID: {notification.id}) sent to rider {assigned_rider.username} for order {order.code}")
                    
                    # Send SMS to rider if phone number exists
                    print(f"[DEBUG] Checking rider phone: {assigned_rider.phone if hasattr(assigned_rider, 'phone') else 'No phone attribute'}")
                    if assigned_rider.phone:  # type: ignore
                        try:
                            from services.sms_service import AfricasTalkingSMSService
                            
                            print(f"[DEBUG] Initializing SMS service for rider...")
                            sms_service = AfricasTalkingSMSService()
                            print(f"[DEBUG] Sending order ready notification to {assigned_rider.phone}...")
                            
                            sms_result = sms_service.send_order_ready_notification(
                                assigned_rider.phone,  # type: ignore
                                order,
                                assigned_rider.get_full_name() or assigned_rider.username
                            )
                            
                            print(f"[DEBUG] SMS result: {sms_result}")
                            
                            if sms_result and sms_result.get('status') == 'success':
                                print(f"✓ SMS sent to rider {assigned_rider.username} ({assigned_rider.phone})")  # type: ignore
                            else:
                                error_msg = sms_result.get('message', 'Unknown error') if sms_result else 'No response'
                                print(f"⚠ Failed to send SMS to rider: {error_msg}")
                        except Exception as e:
                            print(f"⚠ SMS service error for rider {assigned_rider.username}: {str(e)}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"⚠ Rider {assigned_rider.username} has no phone number registered")
                else:
                    print(f"⚠ No rider to send notification to for order {order.code}")

                # record assignment event
                if assigned_rider:
                    from .models import OrderEvent
                    OrderEvent.objects.create(
                        order=order,
                        actor=request.user if request.user.is_authenticated else None,
                        event_type='assigned_rider',
                        data={'rider_id': assigned_rider.id, 'rider_username': assigned_rider.username}  # type: ignore
                    )
                
                # Send SMS to customer notifying that order is ready with invoice
                if order.user and order.user.phone:  # type: ignore
                    try:
                        from services.sms_service import AfricasTalkingSMSService
                        
                        sms_service = AfricasTalkingSMSService()
                        sms_result = sms_service.send_order_ready_for_customer(
                            order.user.phone,  # type: ignore
                            order
                        )
                        
                        if sms_result and sms_result.get('status') == 'success':
                            print(f"✓ Order ready notification with invoice sent to customer {order.user.username}")
                        else:
                            error_msg = sms_result.get('message', 'Unknown error') if sms_result else 'No response'
                            print(f"⚠ Failed to send order ready SMS to customer: {error_msg}")
                    except Exception as e:
                        print(f"⚠ SMS service error for order ready notification: {str(e)}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"⚠ Customer {order.user.username if order.user else 'Unknown'} has no phone number registered")
            
            # Handle status change to 'delivered' - send SMS to customer
            status_changed_to_delivered = new_status and new_status.lower() == 'delivered' and old_status.lower() != 'delivered'
            if status_changed_to_delivered and order.user and order.user.phone:  # type: ignore
                try:
                    from services.sms_service import AfricasTalkingSMSService
                    
                    sms_service = AfricasTalkingSMSService()
                    sms_result = sms_service.send_delivery_confirmation(
                        order.user.phone,  # type: ignore
                        order
                    )
                    
                    if sms_result and sms_result.get('status') == 'success':
                        print(f"✓ Delivery confirmation SMS sent to customer {order.user.username}")
                    else:
                        error_msg = sms_result.get('message', 'Unknown error') if sms_result else 'No response'
                        print(f"⚠ Failed to send delivery SMS: {error_msg}")
                except Exception as e:
                    print(f"⚠ SMS service error for delivery confirmation: {str(e)}")
                    import traceback
                    traceback.print_exc()

            serializer = OrderListSerializer(order)
            return Response(serializer.data)

        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"[ERROR] Exception in OrderUpdateView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET  -> list orders (filtered by location for staff)
    POST -> create order (anonymous allowed)
    """
    queryset = Order.objects.all().order_by("-created_at")
    # We'll enforce authentication for GET (listing) but still allow anonymous POST (create)
    permission_classes = [LocationBasedPermission]

    def get_permissions(self):
        """
        Use stricter permissions for GET requests (require authentication) so
        anonymous users cannot list all orders. Allow anonymous POST to create orders.
        """
        if self.request.method == 'GET':
            return [permissions.IsAuthenticated(), LocationBasedPermission()]
        if self.request.method == 'POST':
            return [permissions.AllowAny(), LocationBasedPermission()]
        return [permissions.IsAuthenticated(), LocationBasedPermission()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Optimize queries
        queryset = queryset.select_related('user', 'service', 'rider', 'service_location').prefetch_related('services')
        
        # Filter by order code if provided
        code = self.request.query_params.get("code")
        if code:
            return queryset.filter(code__iexact=code.strip())

        # For staff users, filter by their service location
        if user.is_authenticated and user.is_staff and not user.is_superuser:
            print(f"\n[DEBUG Orders] Staff user: {user.username} (ID: {user.id})")
            print(f"[DEBUG Orders] Staff service_location: {user.service_location} (ID: {user.service_location.id if user.service_location else 'None'})")
            
            if user.service_location:
                # Filter orders where either:
                # 1. The order's service_location matches staff's service_location, or
                # 2. The customer's location matches staff's service location area
                queryset = queryset.filter(
                    models.Q(service_location=user.service_location) |
                    models.Q(user__location__icontains=user.service_location.name)
                )
                print(f"[DEBUG Orders] Applied location filter for: {user.service_location}")
                print(f"[DEBUG Orders] Total orders matching location: {queryset.count()}")
                for order in queryset[:5]:
                    print(f"  - Order {order.code}: service_location={order.service_location}, status={order.status}")
            else:
                print(f"[DEBUG Orders] ⚠️ Staff has no service_location assigned, returning no orders")
                return Order.objects.none()
        # For regular users, show only their orders
        elif user.is_authenticated and not user.is_staff:
            queryset = queryset.filter(user=user)
            
        return queryset

    def perform_create(self, serializer):
        # Automatically set the service_location based on the pickup address
        # You might want to implement a more sophisticated location assignment logic
        if self.request.user.is_authenticated:
            order = serializer.save(user=self.request.user)
        else:
            order = serializer.save()
        
        print(f"\n[DEBUG perform_create] Order {order.code} created")
        print(f"[DEBUG] Initial rider: {order.rider.username if order.rider else 'None'}")
        
        # AUTO-ASSIGN RIDER FOR ALL ORDERS WITHOUT A RIDER BEFORE SENDING SMS
        # This ensures the rider is assigned before we try to send SMS
        # Applies to both manual (staff-created) and online orders
        if not order.rider:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                print(f"[DEBUG] Attempting to auto-assign rider for order {order.code}")
                print(f"[DEBUG] Order type: {order.order_type}, Has rider: {bool(order.rider)}")
                
                service_location = order.service_location
                print(f"[DEBUG] Initial service_location: {service_location}")
                
                # If no service_location, try to infer from user's location or pickup address
                if not service_location:
                    # Try to match from user's location field
                    if order.user and order.user.location:
                        user_location = order.user.location.lower().strip()
                        print(f"[DEBUG] Trying to find location matching user location: {user_location}")
                        service_location = Location.objects.filter(
                            name__icontains=user_location,
                            is_active=True
                        ).first()
                        print(f"[DEBUG] Found location from user: {service_location}")
                    
                    # If still no location, try to extract from pickup_address
                    if not service_location:
                        print(f"[DEBUG] Trying to find location from pickup_address: {order.pickup_address}")
                        locations = Location.objects.filter(is_active=True)
                        print(f"[DEBUG] Available locations: {[loc.name for loc in locations]}")
                        for loc in locations:
                            if loc.name.lower() in order.pickup_address.lower():
                                service_location = loc
                                print(f"[DEBUG] Found location from address: {service_location}")
                                break
                    
                    # If still no match, assign to the first active location
                    if not service_location:
                        print(f"[DEBUG] No location found, using first active location")
                        service_location = Location.objects.filter(is_active=True).first()
                        print(f"[DEBUG] First active location: {service_location}")
                
                # DISABLED: Auto-assignment of riders - now manual by admin
                # Get all riders assigned to this location, sorted by completed_jobs
                # if service_location:
                #     print(f"[DEBUG] Looking for riders in location: {service_location.name}")
                #     riders = User.objects.filter(
                #         role='rider',
                #         service_location=service_location,
                #         is_active=True
                #     ).select_related('rider_profile').order_by('rider_profile__completed_jobs')
                #
                #     print(f"[DEBUG] Found {riders.count()} riders in {service_location.name}")
                #     for rider in riders:
                #         print(f"[DEBUG]   - {rider.username} (completed_jobs: {rider.rider_profile.completed_jobs if hasattr(rider, 'rider_profile') else 'N/A'})")
                #
                #     if riders.exists():
                #         # Auto-assign to the first available rider (least busy)
                #         assigned_rider = riders.first()
                #         order.rider = assigned_rider
                #         order.service_location = service_location
                #         # Update status from pending_assignment to requested if it was pending
                #         if order.status == 'pending_assignment':
                #             order.status = 'requested'
                #         order.save(update_fields=['rider', 'service_location', 'status'])
                #         print(f"[ASSIGNED] Order {order.code} auto-assigned to rider {assigned_rider.username}")
                #     else:
                #         print(f"⚠ No active riders found in {service_location.name}")
                # else:
                #     print(f"⚠ No service_location found, cannot assign rider")
            
            except Exception as e:
                print(f"⚠ Error auto-assigning rider: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print(f"[DEBUG] Rider after assignment: {order.rider.username if order.rider else 'None'}")
        print(f"[DEBUG] Rider phone: {order.rider.phone if order.rider and hasattr(order.rider, 'phone') else 'N/A'}")
        
        # Create in-app notifications for all three parties
        try:
            from notifications.models import Notification
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # 1. Notify customer
            if order.user:
                Notification.objects.create(
                    user=order.user,
                    order=order,
                    message=f"Your order {order.code} has been placed successfully!",
                    notification_type='new_order'
                )
            
            # 2. Notify all admins
            admin_users = User.objects.filter(is_superuser=True, is_active=True)
            services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
            
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    order=order,
                    message=f"📦 New online order {order.code} from {order.user.username if order.user else 'Guest'}",
                    notification_type='new_order'
                )
            
            # 3. Notify rider (if assigned)
            if order.rider:
                Notification.objects.create(
                    user=order.rider,
                    order=order,
                    message=f"Order {order.code} assigned to you!",
                    notification_type='order_assigned'
                )
        
        except Exception as e:
            print(f"⚠ Error creating order notifications: {str(e)}")
        
        # Send SMS to all three parties (admin, customer, and rider if assigned)
        try:
            from django.conf import settings
            from services.sms_service import AfricasTalkingSMSService
            from users.models import Location
            
            admin_phone = settings.ADMIN_PHONE_NUMBER
            
            # Format services list
            services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
            user_name = order.user.get_full_name() or order.user.username if order.user else order.customer_name or 'Customer'
            # Get customer phone from user.phone OR customer_phone field (for walk-in orders)
            user_phone = (order.user.phone if order.user and order.user.phone else None) or \
                         (order.customer_phone if order.customer_phone else None) or None
            
            # 1. Send SMS to CUSTOMER
            if user_phone and str(user_phone).strip():
                try:
                    from services.sms_service import format_phone_number
                    from django.utils import timezone
                    sms_service = AfricasTalkingSMSService()
                    # Format phone number to international format
                    formatted_phone = format_phone_number(user_phone)
                    order_url = f"https://www.wildwash.co.ke/orders/{order.code}"
                    
                    # Extract clean pickup address and calculate hours for estimated delivery
                    clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                    if order.estimated_delivery:
                        hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                        est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                    else:
                        est_time = 'TBD'
                    
                    customer_message = (
                        f"WILDWASH SERVICES\n"
                        f"Order Confirmed!\n"
                        f"Order #: {order.code}\n"
                        f"Services: {services}\n"
                        f"Pickup: {clean_pickup}\n"
                        f"Price: KES {order.price or 'TBD'}\n"
                        f"Est. Delivery: {est_time}\n"
                        f"View: {order_url}\n"
                        f"We'll notify you when your order is ready!"
                    )
                    
                    result = sms_service.send_sms(formatted_phone, customer_message)
                    
                    if result and result.get('status') == 'success':
                        print(f"✓ Customer SMS sent to {formatted_phone} for order {order.code}")
                    else:
                        error_msg = result.get('message', 'Unknown error') if result else 'No response'
                        print(f"⚠ Failed to send customer SMS: {error_msg}")
                
                except Exception as sms_error:
                    print(f"⚠ Error sending customer SMS: {str(sms_error)}")
                    import traceback
                    traceback.print_exc()
            
            # 2. Send SMS to ADMIN
            if admin_phone:
                try:
                    from django.utils import timezone
                    sms_service = AfricasTalkingSMSService()
                    admin_url = f"https://www.wildwash.co.ke/orders/{order.code}"
                    
                    # Extract clean pickup address (remove contact info)
                    clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                    
                    # Calculate hours for estimated delivery
                    if order.estimated_delivery:
                        hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                        est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                    else:
                        est_time = 'TBD'
                    
                    admin_message = (
                        f"WILDWASH SERVICES\n"
                        f"New Online Order Assigned!\n"
                        f"Order #: {order.code}\n"
                        f"Customer: {user_name}\n"
                        f"Phone: {user_phone or 'N/A'}\n"
                        f"Pickup: {clean_pickup}\n"
                        f"Dropoff: {order.dropoff_address}\n"
                        f"Services: {services}\n"
                        f"Items: {order.items}\n"
                        f"Price: KES {order.price or 'TBD'}\n"
                        f"Est. Delivery: {est_time}\n"
                        f"Status: {order.get_actual_status_display()}\n"
                        f"Manage: {admin_url}"
                    )
                    
                    result = sms_service.send_sms(admin_phone, admin_message)
                    
                    if result and result.get('status') == 'success':
                        print(f"✓ Admin SMS sent to {admin_phone} for order {order.code}")
                    else:
                        error_msg = result.get('message', 'Unknown error') if result else 'No response'
                        print(f"⚠ Failed to send admin SMS: {error_msg}")
                
                except Exception as sms_error:
                    print(f"⚠ Error sending admin SMS: {str(sms_error)}")
                    import traceback
                    traceback.print_exc()
            
            # 3. Send SMS to ASSIGNED RIDER (if order has rider assigned)
            print(f"[DEBUG] Checking rider for SMS: {order.rider}")
            if order.rider:
                print(f"[DEBUG] Rider exists: {order.rider.username}")
                print(f"[DEBUG] Rider phone attribute: {hasattr(order.rider, 'phone')}")
                print(f"[DEBUG] Rider phone value: {order.rider.phone if hasattr(order.rider, 'phone') else 'NO PHONE ATTR'}")
                
                # Properly convert empty string to None
                rider_phone = order.rider.phone if hasattr(order.rider, 'phone') and order.rider.phone else None  # type: ignore
                rider_phone = None if rider_phone and not str(rider_phone).strip() else rider_phone  # type: ignore
                print(f"[DEBUG] Final rider_phone: {rider_phone}")
                
                if rider_phone and str(rider_phone).strip():
                    try:
                        from django.utils import timezone
                        print(f"[DEBUG] Attempting to send SMS to rider {order.rider.username} at {rider_phone}")
                        sms_service = AfricasTalkingSMSService()
                        rider_url = f"https://www.wildwash.co.ke/rider/orders/{order.code}"
                        
                        # Extract clean pickup address and calculate hours for estimated delivery
                        clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                        if order.estimated_delivery:
                            hours_diff = (order.estimated_delivery - timezone.now()).total_seconds() / 3600
                            est_time = f"{int(hours_diff)}hrs" if hours_diff > 0 else 'TBD'
                        else:
                            est_time = 'TBD'
                        
                        rider_name = order.rider.get_full_name() or order.rider.username if order.rider else 'Rider'
                        rider_message = (
                            f"WILDWASH SERVICES\n"
                            f"New Order Assigned!\n"
                            f"Order #: {order.code}\n"
                            f"Customer: {user_name}\n"
                            f"Phone: {user_phone or 'N/A'}\n"
                            f"Pickup: {clean_pickup}\n"
                            f"Dropoff: {order.dropoff_address}\n"
                            f"Services: {services}\n"
                            f"Items: {order.items}\n"
                            f"Price: KES {order.price or 'TBD'}\n"
                            f"Est. Delivery: {est_time}\n"
                            f"Accept: {rider_url}"
                        )
                        
                        result = sms_service.send_sms(rider_phone, rider_message)
                        
                        if result and result.get('status') == 'success':
                            print(f"✓ Rider SMS sent to {order.rider.username} ({rider_phone}) for order {order.code}")
                        else:
                            error_msg = result.get('message', 'Unknown error') if result else 'No response'
                            print(f"⚠ Failed to send rider SMS to {order.rider.username}: {error_msg}")
                    
                    except Exception as sms_error:
                        print(f"⚠ Error sending rider SMS to {order.rider.username}: {str(sms_error)}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[DEBUG] Rider {order.rider.username} has no phone number")
            else:
                print(f"[DEBUG] No rider assigned to order {order.code}")
        
        except Exception as e:
            print(f"⚠ Error in SMS notification block: {str(e)}")
            import traceback
            traceback.print_exc()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class OrderPaymentStatusView(APIView):
    """
    GET -> Get payment status for an order
    Retrieves the payment information associated with an order
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code, *args, **kwargs):
        try:
            # Try to get the order by code (order reference/id)
            order = Order.objects.get(code=code)
            
            # Check if user has permission to view this order
            if order.user != request.user and not request.user.is_staff:
                return Response(
                    {'detail': 'You do not have permission to view this order'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get the latest payment for this order
            from payments.models import Payment
            try:
                payment = Payment.objects.filter(order_id=order.id).latest('created_at')
                return Response({
                    'status': payment.status,
                    'message': f'Payment is {payment.status}',
                    'checkout_request_id': payment.provider_reference,
                    'order_id': order.code,
                    'amount': float(payment.amount),
                    'delivery_requested': order.delivery_requested,
                })
            except Payment.DoesNotExist:
                return Response({
                    'status': 'pending',
                    'message': 'No payment found for this order',
                    'checkout_request_id': '',
                    'order_id': order.code,
                    'amount': 0,
                    'delivery_requested': order.delivery_requested,
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class RequestDeliveryView(APIView):
    """
    POST -> Request delivery for a paid order
    Notifies the assigned rider via SMS and in-app notification
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code, *args, **kwargs):
        try:
            # Try to get the order by code
            order = Order.objects.get(code=code)
            
            # Check if user has permission to request delivery for this order
            if order.user != request.user and not request.user.is_staff:
                return Response(
                    {'detail': 'You do not have permission to request delivery for this order'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if delivery has already been requested
            if order.delivery_requested:
                return Response(
                    {'detail': 'Delivery has already been requested for this order'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if order has a payment
            from payments.models import Payment
            try:
                payment = Payment.objects.filter(order_id=order.id).latest('created_at')
                if payment.status != 'success':
                    return Response(
                        {'detail': 'Payment must be successful before requesting delivery'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Payment.DoesNotExist:
                return Response(
                    {'detail': 'No payment found for this order'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if order has an assigned rider
            if not order.rider:
                return Response(
                    {'detail': 'No rider assigned to this order yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Send SMS to rider requesting delivery
            rider = order.rider
            rider_phone = rider.phone if hasattr(rider, 'phone') else None  # type: ignore
            
            if rider_phone:
                try:
                    from services.sms_service import AfricasTalkingSMSService
                    
                    sms_service = AfricasTalkingSMSService()
                    
                    services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                    customer_name = order.user.get_full_name() or order.user.username if order.user else 'Customer'
                    customer_phone = order.user.phone if order.user and order.user.phone else 'N/A'  # type: ignore
                    
                    # Extract clean pickup address
                    clean_pickup = order.pickup_address.split('(contact:')[0].strip() if order.pickup_address else 'N/A'
                    
                    rider_url = f"https://www.wildwash.co.ke/rider/orders/{order.code}"
                    rider_message = (
                        f"Delivery Request!\n"
                        f"Order #: {order.code}\n"
                        f"Customer: {customer_name}\n"
                        f"Phone: {customer_phone}\n"
                        f"Pickup: {clean_pickup}\n"
                        f"Dropoff: {order.dropoff_address}\n"
                        f"Service: {services}\n"
                        f"Items: {order.quantity or order.items}\n"
                        f"Amount: KES {order.actual_price or order.price}\n"
                        f"Payment: ✓ Confirmed\n"
                        f"View: {rider_url}\n"
                        f"Please proceed with delivery. Thank you!"
                    )
                    
                    sms_result = sms_service.send_sms(rider_phone, rider_message)
                    
                    if not (sms_result and sms_result.get('status') == 'success'):
                        return Response(
                            {'detail': f'Failed to notify rider: {sms_result.get("message", "Unknown error") if sms_result else "No response"}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                    
                    print(f"✓ Delivery request SMS sent to rider {rider.username} ({rider_phone}) for order {order.code}")
                
                except Exception as e:
                    print(f"⚠ SMS service error for delivery request: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return Response(
                        {'detail': f'Error sending notification to rider: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                return Response(
                    {'detail': 'Rider has no phone number registered'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create in-app notification for rider
            try:
                from notifications.models import Notification
                Notification.objects.create(
                    user=rider,
                    order=order,
                    message=f"Customer {order.user.username if order.user else 'Customer'} requested delivery for order {order.code}",
                    notification_type='delivery_request'
                )
                print(f"✓ Delivery request notification sent to rider {rider.username} for order {order.code}")
            except Exception as e:
                print(f"⚠ Error creating notification: {str(e)}")
            
            # Send SMS to admin about delivery request
            try:
                from django.conf import settings
                from services.sms_service import AfricasTalkingSMSService
                
                admin_phone = settings.ADMIN_PHONE_NUMBER
                
                if admin_phone:
                    sms_service = AfricasTalkingSMSService()
                    
                    services = ', '.join([s.name for s in order.services.all()]) if order.services.exists() else 'N/A'
                    customer_name = order.user.get_full_name() or order.user.username if order.user else 'Customer'
                    rider_name = rider.get_full_name() or rider.username
                    
                    admin_message = (
                        f"📦 DELIVERY REQUEST!\n"
                        f"Order #: {order.code}\n"
                        f"Customer: {customer_name}\n"
                        f"Rider: {rider_name}\n"
                        f"Service: {services}\n"
                        f"Pickup: {order.pickup_address}\n"
                        f"Dropoff: {order.dropoff_address}\n"
                        f"Amount: KES {order.actual_price or order.price}\n"
                        f"Payment: ✓ Confirmed\n"
                        f"Status: Ready for pickup/delivery"
                    )
                    
                    admin_sms_result = sms_service.send_sms(admin_phone, admin_message)
                    
                    if admin_sms_result and admin_sms_result.get('status') == 'success':
                        print(f"✓ Delivery request SMS sent to admin ({admin_phone}) for order {order.code}")
                    else:
                        error_msg = admin_sms_result.get('message', 'Unknown error') if admin_sms_result else 'No response'
                        print(f"⚠ Failed to send admin SMS: {error_msg}")
                else:
                    print(f"⚠ Admin phone number not configured")
            
            except Exception as e:
                print(f"⚠ SMS service error sending admin notification: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # Mark delivery as requested
            from django.utils import timezone
            order.delivery_requested = True
            order.delivery_requested_at = timezone.now()
            order.save(update_fields=['delivery_requested', 'delivery_requested_at'])
            
            print(f"✓ Delivery request marked as complete for order {order.code}")
            
            return Response({
                'status': 'success',
                'message': f'Delivery request sent to rider {rider.get_full_name() or rider.username}',
                'rider_name': rider.get_full_name() or rider.username,
                'rider_phone': rider_phone,
            })
        
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"[ERROR] Exception in RequestDeliveryView: {str(e)}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )