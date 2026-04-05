# orders/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Order, OrderItem
from services.models import Service
from users.models import Location
from decimal import Decimal

User = get_user_model()

class OrderCreateSerializer(serializers.ModelSerializer):
    # Accept multiple services via 'services' field
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        many=True,
        write_only=True,
        required=False
    )
    # Keep 'service' for backward compatibility (single service)
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        required=False
    )
    service_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.filter(is_active=True),
        required=False
    )
    # Accept service quantities as a list of {service_id, quantity} objects
    service_quantities = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField()),
        write_only=True,
        required=False
    )
    total_price = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "service",
            "services",
            "service_location",
            "description",
            "pickup_address",
            "dropoff_address",
            "requested_pickup_at",
            "urgency",
            "items",
            "package",
            "weight_kg",
            "price",
            "actual_price",
            "total_price",
            "estimated_delivery",
            "service_quantities",
            # Manual order fields
            "order_type",
            "drop_off_type",
            "customer_name",
            "customer_phone",
        ]
        read_only_fields = ["id", "total_price"]

    def validate(self, data):
        # basic sanity defaults / checks
        if data.get("items") is None:
            data["items"] = 1
        if data.get("items", 0) < 1:
            raise serializers.ValidationError({"items": "Must be at least 1"})
        
        # Check if this is a manual order
        order_type = data.get("order_type", "online")
        
        if order_type == "manual":
            # Manual orders require customer details instead of services
            if not data.get("customer_name"):
                raise serializers.ValidationError({"customer_name": "Customer name is required for manual orders"})
            if not data.get("customer_phone"):
                raise serializers.ValidationError({"customer_phone": "Customer phone is required for manual orders"})
        else:
            # Online orders require at least one service
            services = data.get("services", [])
            service = data.get("service")
            if not services and not service:
                raise serializers.ValidationError(
                    {"services": "At least one service must be provided"}
                )
        
        # allow weight_kg and price to be null for backend calculation
        return data

    def create(self, validated_data):
        """
        Attach order to:
         - request.user if authenticated (for manual orders by staff), else
         - a single guest user (created if missing) for online orders.
        Automatically set service_location from user's service_location.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        order_type = validated_data.get("order_type", "online")

        # For manual orders, track which staff member created it
        created_by_user = None
        if order_type == "manual" and user and getattr(user, "is_authenticated", False):
            created_by_user = user
            # Manual orders don't necessarily need a user linked
            if 'user' not in validated_data or validated_data['user'] is None:
                # Create or get guest user for manual orders
                guest_username = "guest_orders"
                guest_email = "guest@wildwash.local"
                guest_user, created = User.objects.get_or_create(
                    username=guest_username,
                    defaults={"email": guest_email, "is_active": False},
                )
                if created:
                    guest_user.set_unusable_password()
                    guest_user.save()
                validated_data['user'] = guest_user
        else:
            # For online orders, use normal user handling
            if not (user and getattr(user, "is_authenticated", False)):
                guest_username = "guest_orders"
                guest_email = "guest@wildwash.local"
                guest_user, created = User.objects.get_or_create(
                    username=guest_username,
                    defaults={"email": guest_email, "is_active": False},
                )
                if created:
                    guest_user.set_unusable_password()
                    guest_user.save()
                user = guest_user

            if 'user' not in validated_data:
                validated_data['user'] = user
        
        # Auto-set service_location from staff's service_location for manual orders
        if 'service_location' not in validated_data or not validated_data['service_location']:
            if order_type == "manual" and created_by_user and created_by_user.service_location:
                # Manual orders inherit staff member's location
                validated_data['service_location'] = created_by_user.service_location
            elif user and user.service_location:
                # For online orders, use user's service_location
                validated_data['service_location'] = user.service_location
            elif user and user.location:
                # Try to infer from user's location field
                user_location = user.location.lower().strip()
                from users.models import Location
                inferred_location = Location.objects.filter(
                    name__icontains=user_location,
                    is_active=True
                ).first()
                if inferred_location:
                    validated_data['service_location'] = inferred_location
            else:
                # Try to infer from pickup_address
                pickup_address = validated_data.get('pickup_address', '').lower()
                from users.models import Location
                locations = Location.objects.filter(is_active=True)
                for loc in locations:
                    if loc.name.lower() in pickup_address:
                        validated_data['service_location'] = loc
                        break
        
        # Extract services list for M2M
        services = validated_data.pop('services', [])
        # Extract service_quantities if provided
        service_quantities = validated_data.pop('service_quantities', [])
        
        # If no services in list but single service provided, use that
        if not services and 'service' in validated_data and order_type != "manual":
            services = [validated_data['service']]
        
        # Track created_by for manual orders
        if created_by_user:
            validated_data['created_by'] = created_by_user
        
        # For manual orders, set status to pending_assignment (don't auto-assign rider)
        if order_type == "manual":
            validated_data['status'] = 'pending_assignment'
        
        # Create the order
        order = Order.objects.create(**validated_data)
        
        # Add services to the order (skip for manual orders)
        if services:
            order.services.set(services)
            # Set the primary service to the first one for backward compatibility
            if not order.service:
                order.service = services[0]
                order.save(update_fields=['service'])
            
            # Create OrderItem entries with quantities
            if service_quantities:
                for sq in service_quantities:
                    service_id = sq.get('service_id')
                    quantity = sq.get('quantity', 1)
                    if service_id and quantity > 0:
                        try:
                            service = Service.objects.get(pk=service_id)
                            OrderItem.objects.update_or_create(
                                order=order,
                                service=service,
                                defaults={'quantity': quantity}
                            )
                        except Service.DoesNotExist:
                            pass
            else:
                # If no quantities provided, create OrderItems with default quantity of 1
                for service in services:
                    OrderItem.objects.update_or_create(
                        order=order,
                        service=service,
                        defaults={'quantity': 1}
                    )
        
        order.code = f"WW-{order.id:05d}"
        order.save(update_fields=["code"])
        return order

    def get_total_price(self, obj):
        """Calculate total price from all services"""
        total = sum(service.price for service in obj.services.all())
        return float(total) if total else 0


class OrderItemSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'service', 'service_name', 'service_price', 'quantity']
        read_only_fields = ['id']
    
    def get_service_price(self, obj):
        return float(obj.service.price) if obj.service.price else 0


class OrderListSerializer(serializers.ModelSerializer):
    package = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    actual_price = serializers.SerializerMethodField()
    status = serializers.CharField()
    service_name = serializers.CharField(source="service.name", read_only=True, allow_null=True)
    services_list = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    service_location = serializers.SerializerMethodField()
    rider = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    pickup_location = serializers.SerializerMethodField()
    dropoff_location = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    order_items = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    washer_name = serializers.SerializerMethodField()
    folder_name = serializers.SerializerMethodField()
    fumigator_name = serializers.SerializerMethodField()
    rider_name = serializers.SerializerMethodField()
    staff_input_details = serializers.SerializerMethodField()
    
    def get_is_paid(self, obj):
        """Return whether this order has been paid"""
        return obj.is_paid()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cache services and rider data to avoid multiple DB hits
        if isinstance(self.instance, list):
            self._services_cache = {}
            for order in self.instance:
                self._services_cache[order.id] = list(order.services.all().values('id', 'name', 'price'))
        elif self.instance:
            self._services_cache = {self.instance.id: list(self.instance.services.all().values('id', 'name', 'price'))}

    def get_user(self, obj):
        if not obj.user:
            return None
        return {
            'username': obj.user.username,
            'phone': obj.user.phone,
            'location': obj.user.location,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
        }

    def get_service_location(self, obj):
        if not obj.service_location:
            return None
        return {
            'id': obj.service_location.id,
            'name': obj.service_location.name,
        }

    def get_rider(self, obj):
        if not obj.rider:
            return None
        return {
            'username': obj.rider.username,
            'first_name': obj.rider.first_name,
            'last_name': obj.rider.last_name,
            'service_location': {
                'name': obj.rider.service_location.name if obj.rider.service_location else None
            }
        }

    def get_created_by(self, obj):
        """Return staff member who created this manual order"""
        if not obj.created_by:
            return None
        return {
            'username': obj.created_by.username,
            'first_name': obj.created_by.first_name,
            'last_name': obj.created_by.last_name,
            'service_location': {
                'name': obj.created_by.service_location.name if obj.created_by.service_location else None
            }
        }

    def get_services_list(self, obj):
        """Return list of services with their details"""
        services = obj.services.all().values('id', 'name', 'price')
        return list(services)

    def get_order_items(self, obj):
        """Return order items with quantities"""
        items = obj.order_items.all()
        return OrderItemSerializer(items, many=True).data

    def get_timeline(self, obj):
        """Return the order events/timeline for admin users or an empty list for others.

        The context must provide the request; if the request user is staff or superuser, return full timeline.
        Otherwise return a limited timeline (e.g. status changes only) or empty list.
        """
        request = self.context.get('request')
        # If no request context, be conservative and return the stored timeline if present
        if not request:
            events = getattr(obj, 'events', []).all() if hasattr(obj, 'events') else []
        else:
            user = getattr(request, 'user', None)
            # Admins (staff or superusers) get full timeline
            if user and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
                events = obj.events.all()
            else:
                # For non-admins, expose only generic status entries if any
                events = obj.events.filter(event_type__icontains='status')

        out = []
        for ev in events:
            out.append({
                'id': ev.id,
                'event_type': ev.event_type,
                'actor': ev.actor.username if ev.actor else None,
                'data': ev.data,
                'created_at': ev.created_at.isoformat() if ev.created_at else None,
            })
        return out

    def get_total_price(self, obj):
        """Calculate total price from all services"""
        total = sum(service.price for service in obj.services.all())
        return float(total) if total else None

    def get_package(self, obj):
        return getattr(obj.service, "name", f"Package {obj.package}") if obj.service else f"Package {obj.package}"

    def get_price_display(self, obj):
        # Use total price from services if available
        total = sum(service.price for service in obj.services.all())
        if total:
            try:
                p = Decimal(str(total))
                if p == p.to_integral():
                    return f"KSh {int(p):,}"
                return f"KSh {p:,}"
            except Exception:
                return str(total)
        elif obj.price is not None:
            try:
                p = Decimal(obj.price)
                if p == p.to_integral():
                    return f"KSh {int(p):,}"
                return f"KSh {p:,}"
            except Exception:
                return str(obj.price)
        return ""

    def get_actual_price(self, obj):
        """Convert Decimal actual_price to float for JSON serialization"""
        if obj.actual_price is not None:
            try:
                return float(obj.actual_price)
            except (ValueError, TypeError):
                return None
        return None

    def get_pickup_location(self, obj):
        """Return pickup location coordinates if available from service_location"""
        if obj.service_location and hasattr(obj.service_location, 'latitude') and hasattr(obj.service_location, 'longitude'):
            return {
                'lat': float(obj.service_location.latitude) if obj.service_location.latitude else None,
                'lng': float(obj.service_location.longitude) if obj.service_location.longitude else None
            }
        return None

    def get_dropoff_location(self, obj):
        """Return dropoff location - could be user's location or another location"""
        if obj.user and hasattr(obj.user, 'latitude') and hasattr(obj.user, 'longitude'):
            return {
                'lat': float(obj.user.latitude) if obj.user.latitude else None,
                'lng': float(obj.user.longitude) if obj.user.longitude else None
            }
        return None

    def get_washer_name(self, obj):
        """Return washer's full name"""
        if obj.washer:
            return f"{obj.washer.first_name} {obj.washer.last_name}".strip() or obj.washer.username
        return None

    def get_folder_name(self, obj):
        """Return folder's full name"""
        if obj.folder:
            return f"{obj.folder.first_name} {obj.folder.last_name}".strip() or obj.folder.username
        return None

    def get_fumigator_name(self, obj):
        """Return fumigator's full name"""
        if hasattr(obj, 'fumigator') and obj.fumigator:
            return f"{obj.fumigator.first_name} {obj.fumigator.last_name}".strip() or obj.fumigator.username
        return None

    def get_rider_name(self, obj):
        """Return rider's full name"""
        if obj.rider:
            return f"{obj.rider.first_name} {obj.rider.last_name}".strip() or obj.rider.username
        return None

    def get_staff_input_details(self, obj):
        """Return all staff input details for this order"""
        details = []
        
        # Washer details
        if (obj.washer_items is not None or obj.washer_weight or obj.washer_notes or obj.washer_price):
            details.append({
                'staff_member': self.get_washer_name(obj) or 'Washer',
                'staff_role': 'Washer',
                'items': obj.washer_items,
                'weight_kg': float(obj.washer_weight) if obj.washer_weight else None,
                'description': obj.washer_notes,
                'actual_price': float(obj.washer_price) if obj.washer_price else None,
                'status_recorded': 'washed',
                'recorded_at': obj.washed_at.isoformat() if obj.washed_at else None,
            })
        
        # Folder details
        if (obj.folder_items is not None or obj.folder_weight or obj.folder_notes or obj.folder_price):
            details.append({
                'staff_member': self.get_folder_name(obj) or 'Folder',
                'staff_role': 'Folder',
                'items': obj.folder_items,
                'weight_kg': float(obj.folder_weight) if obj.folder_weight else None,
                'description': obj.folder_notes,
                'actual_price': float(obj.folder_price) if obj.folder_price else None,
                'status_recorded': 'ready',
                'recorded_at': obj.folded_at.isoformat() if obj.folded_at else None,
            })
        
        # Fumigator details
        if (hasattr(obj, 'fumigator_items') and (obj.fumigator_items is not None or obj.fumigator_weight or obj.fumigator_notes or obj.fumigator_price)):
            details.append({
                'staff_member': self.get_fumigator_name(obj) or 'Fumigator',
                'staff_role': 'Fumigator',
                'items': getattr(obj, 'fumigator_items', None),
                'weight_kg': float(obj.fumigator_weight) if getattr(obj, 'fumigator_weight', None) else None,
                'description': getattr(obj, 'fumigator_notes', None),
                'actual_price': float(obj.fumigator_price) if getattr(obj, 'fumigator_price', None) else None,
                'status_recorded': 'fumigated',
                'recorded_at': obj.fumigated_at.isoformat() if getattr(obj, 'fumigated_at', None) else None,
            })
        
        # Rider details
        if (obj.rider_items is not None or obj.rider_weight or obj.rider_notes or obj.rider_price):
            details.append({
                'staff_member': self.get_rider_name(obj) or 'Rider',
                'staff_role': 'Rider',
                'items': obj.rider_items,
                'weight_kg': float(obj.rider_weight) if obj.rider_weight else None,
                'description': obj.rider_notes or obj.description,
                'actual_price': float(obj.rider_price) if obj.rider_price else None,
                'status_recorded': 'delivered',
                'recorded_at': obj.delivered_at.isoformat() if obj.delivered_at else None,
            })
        
        return details

    class Meta:
        model = Order
        fields = [
            "id",
            "code",
            "created_at",
            "user",
            "service_name",
            "services_list",
            "service_location",
            "pickup_address",
            "dropoff_address",
            "requested_pickup_at",
            "pickup_location",
            "dropoff_location",
            "urgency",
            "items",
            "weight_kg",
            "quantity",
            "description",
            "package",
            "price",
            "actual_price",
            "total_price",
            "price_display",
            "status",
            "estimated_delivery",
            "delivered_at",
            "rider",
            "created_by",
            "timeline",
            "order_items",
            "is_paid",
            # Manual order fields
            "order_type",
            "drop_off_type",
            "customer_name",
            "customer_phone",
            # Staff detail tracking fields
            "washer_name",
            "folder_name",
            "fumigator_name",
            "rider_name",
            "staff_input_details",
            "washer_items",
            "washer_weight",
            "washer_notes",
            "washer_price",
            "folder_items",
            "folder_weight",
            "folder_notes",
            "folder_price",
            "fumigator_items",
            "fumigator_weight",
            "fumigator_notes",
            "fumigator_price",
            "rider_items",
            "rider_weight",
            "rider_notes",
            "rider_price",
            "washed_at",
            "folded_at",
            "fumigated_at",
        ]
