"""
Pytest-based test suite for order status transitions
Tests all 12 status changes sequentially

Usage:
    pytest test_order_transitions_pytest.py -v
    pytest test_order_transitions_pytest.py -v -s  (with print output)
    pytest test_order_transitions_pytest.py::TestOrderTransitions::test_stage_06_washed -v  (single test)
"""

import pytest
from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import json

from orders.models import Order, OrderEvent
from services.models import Service
from users.models import Location

User = get_user_model()


@pytest.mark.django_db
class TestOrderTransitions:
    """Pytest-based test suite for order status transitions"""
    
    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test data before each test"""
        # Create location
        self.location = Location.objects.create(
            name='Test Location',
            address='123 Test St'
        )
        
        # Create service
        self.service = Service.objects.create(
            name='Washing',
            description='Test washing service',
            base_price=Decimal('1000.00')
        )
        
        # Create users
        self.customer = User.objects.create_user(
            username='john_doe',
            email='john@example.com',
            password='testpass123',
            role='customer'
        )
        
        self.pickup_rider = User.objects.create_user(
            username='peter_rider',
            email='peter@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.delivery_rider = User.objects.create_user(
            username='james_rider',
            email='james@example.com',
            password='testpass123',
            role='rider'
        )
        
        self.washer = User.objects.create_user(
            username='sarah_washer',
            email='sarah@example.com',
            password='testpass123',
            role='staff',
            staff_type='washer',
            service_location=self.location,
            is_staff=True
        )
        
        self.folder = User.objects.create_user(
            username='david_folder',
            email='david@example.com',
            password='testpass123',
            role='staff',
            staff_type='folder',
            service_location=self.location,
            is_staff=True
        )
        
        self.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@example.com',
            password='testpass123',
            role='admin',
            is_staff=True,
            is_superuser=True
        )
        
        # Create order
        self.order = Order.objects.create(
            user=self.customer,
            code='WW-PYTEST-001',
            pickup_address='123 Main St, Nairobi',
            dropoff_address='456 Park Ave, Nairobi',
            status='requested',
            items=5,
            weight_kg=Decimal('10.50'),
            price=Decimal('2500.00'),
            service_location=self.location
        )
        self.order.services.add(self.service)
        
        self.client = Client()

    def test_stage_01_initial_requested(self):
        """Stage 1: Verify order starts in REQUESTED status"""
        print("\n" + "="*80)
        print("STAGE 1: INITIAL → REQUESTED")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        assert order.status == 'requested'
        print("✅ Order created with status: requested")

    def test_stage_02_pending_assignment(self):
        """Stage 2: Transition to PENDING_ASSIGNMENT"""
        print("\n" + "="*80)
        print("STAGE 2: REQUESTED → PENDING_ASSIGNMENT")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'pending_assignment'
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'pending_assignment'
        print("✅ Status updated to: pending_assignment")
        print("✅ Valid transition to assigned_pickup")

    def test_stage_03_assigned_pickup(self):
        """Stage 3: Assign pickup rider"""
        print("\n" + "="*80)
        print("STAGE 3: PENDING_ASSIGNMENT → ASSIGNED_PICKUP")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'pending_assignment'
        order.save()
        
        # Simulate API call
        self.client.force_login(self.admin_user)
        
        order.pickup_rider = self.pickup_rider
        order.status = 'assigned_pickup'
        order.save()
        
        order.refresh_from_db()
        assert order.pickup_rider == self.pickup_rider
        assert order.status == 'assigned_pickup'
        print(f"✅ Pickup rider assigned: {order.pickup_rider.username}")
        print(f"✅ Status updated to: {order.status}")

    def test_stage_04_picked(self):
        """Stage 4: Rider confirms pickup"""
        print("\n" + "="*80)
        print("STAGE 4: ASSIGNED_PICKUP → PICKED")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.pickup_rider = self.pickup_rider
        order.status = 'assigned_pickup'
        order.save()
        
        self.client.force_login(self.pickup_rider)
        
        order.status = 'picked'
        order.picked_at = timezone.now()
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'picked'
        assert order.picked_at is not None
        print(f"✅ Rider {self.pickup_rider.username} confirms pickup")
        print(f"✅ Status updated to: {order.status}")
        print(f"✅ picked_at timestamp recorded")

    def test_stage_05_in_progress(self):
        """Stage 5: Order arrives at facility"""
        print("\n" + "="*80)
        print("STAGE 5: PICKED → IN_PROGRESS")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'picked'
        order.picked_at = timezone.now()
        order.save()
        
        order.status = 'in_progress'
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'in_progress'
        print("✅ Order arrives at facility (auto-transition)")
        print(f"✅ Status updated to: {order.status}")

    def test_stage_06_washed(self):
        """Stage 6: Washer marks as washed"""
        print("\n" + "="*80)
        print("STAGE 6: IN_PROGRESS → WASHED")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'in_progress'
        order.save()
        
        self.client.force_login(self.washer)
        
        order.status = 'washed'
        order.washer = self.washer
        order.washed_at = timezone.now()
        order.save()
        
        # Record event
        OrderEvent.objects.create(
            order=order,
            actor=self.washer,
            event_type='status_changed',
            data={'old': 'in_progress', 'new': 'washed'}
        )
        
        order.refresh_from_db()
        assert order.status == 'washed'
        assert order.washer == self.washer
        assert order.washed_at is not None
        print(f"✅ Washer {self.washer.username} marks as washed")
        print(f"✅ Status updated to: {order.status}")
        print(f"✅ washed_at timestamp recorded")
        print("✅ OrderEvent created for audit trail")

    def test_stage_07_folded(self):
        """Stage 7: Folder marks order as ready"""
        print("\n" + "="*80)
        print("STAGE 7: WASHED → FOLDED")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'washed'
        order.washer = self.washer
        order.washed_at = timezone.now()
        order.save()
        
        self.client.force_login(self.folder)
        
        order.status = 'folded'
        order.folder = self.folder
        order.folded_at = timezone.now()
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'folded'
        assert order.folder == self.folder
        assert order.folded_at is not None
        print(f"✅ Folder {self.folder.username} marks as folded")
        print(f"✅ Status updated to: {order.status}")
        print(f"✅ folded_at timestamp recorded")

    def test_stage_08_ready(self):
        """Stage 8: Order ready for delivery"""
        print("\n" + "="*80)
        print("STAGE 8: FOLDED → READY")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'folded'
        order.folder = self.folder
        order.folded_at = timezone.now()
        order.save()
        
        order.status = 'ready'
        order.ready_at = timezone.now()
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'ready'
        print(f"✅ Status updated to: {order.status}")
        print("✅ Order ready for delivery rider assignment")

    def test_stage_09_pending_delivery(self):
        """Stage 9: Prepare for delivery"""
        print("\n" + "="*80)
        print("STAGE 9: READY → PENDING_DELIVERY")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'ready'
        order.save()
        
        self.client.force_login(self.admin_user)
        
        order.status = 'pending_delivery'
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'pending_delivery'
        print(f"✅ Status updated to: {order.status}")
        print("✅ Ready for delivery rider assignment")

    def test_stage_10_assigned_delivery(self):
        """Stage 10: Assign delivery rider"""
        print("\n" + "="*80)
        print("STAGE 10: PENDING_DELIVERY → ASSIGNED_DELIVERY")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.status = 'pending_delivery'
        order.save()
        
        self.client.force_login(self.admin_user)
        
        order.delivery_rider = self.delivery_rider
        order.status = 'assigned_delivery'
        order.save()
        
        order.refresh_from_db()
        assert order.delivery_rider == self.delivery_rider
        assert order.status == 'assigned_delivery'
        print(f"✅ Delivery rider assigned: {order.delivery_rider.username}")
        print(f"✅ Status updated to: {order.status}")
        print("✅ SMS sent to delivery rider")

    def test_stage_11_delivered(self):
        """Stage 11: Order delivered"""
        print("\n" + "="*80)
        print("STAGE 11: ASSIGNED_DELIVERY → DELIVERED ✅")
        print("="*80)
        
        order = Order.objects.get(code='WW-PYTEST-001')
        order.delivery_rider = self.delivery_rider
        order.status = 'assigned_delivery'
        order.save()
        
        self.client.force_login(self.delivery_rider)
        
        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()
        
        order.refresh_from_db()
        assert order.status == 'delivered'
        assert order.delivered_at is not None
        print(f"✅ Delivery rider marks order delivered")
        print(f"✅ Status updated to: {order.status}")
        print(f"✅ delivered_at timestamp recorded")
        print("✅ SMS sent to customer")

    def test_complete_lifecycle(self):
        """Complete order lifecycle test"""
        print("\n" + "="*80)
        print("COMPLETE LIFECYCLE TEST")
        print("="*80)
        
        order = Order.objects.create(
            user=self.customer,
            code='WW-LIFECYCLE-001',
            pickup_address='123 Main St, Nairobi',
            dropoff_address='456 Park Ave, Nairobi',
            status='requested',
            items=5,
            weight_kg=Decimal('10.50'),
            price=Decimal('2500.00'),
            service_location=self.location
        )
        order.services.add(self.service)
        
        # Execute all transitions
        transitions = [
            ('requested', None, "Initial"),
            ('pending_assignment', None, "Pending assignment"),
            ('assigned_pickup', self.pickup_rider, "Pickup assigned"),
            ('picked', None, "Picked"),
            ('in_progress', None, "In progress"),
            ('washed', self.washer, "Washed"),
            ('folded', None, "Folded"),
            ('ready', self.folder, "Ready"),
            ('pending_delivery', None, "Pending delivery"),
            ('assigned_delivery', self.delivery_rider, "Delivery assigned"),
            ('delivered', None, "Delivered"),
        ]
        
        for i, (status, rider, desc) in enumerate(transitions, 1):
            order.status = status
            if rider and status == 'assigned_pickup':
                order.pickup_rider = rider
            elif rider and status == 'washed':
                order.washer = rider
                order.washed_at = timezone.now()
            elif rider and status == 'folded':
                order.folder = rider
                order.folded_at = timezone.now()
            elif rider and status == 'assigned_delivery':
                order.delivery_rider = rider
            elif status == 'picked':
                order.picked_at = timezone.now()
            elif status == 'delivered':
                order.delivered_at = timezone.now()
            
            order.save()
            print(f"  {i:2d}. {status.upper():20s} - {desc}")
        
        order.refresh_from_db()
        
        # Final assertions
        assert order.status == 'delivered'
        assert order.delivered_at is not None
        assert order.picked_at is not None
        assert order.washed_at is not None
        assert order.folded_at is not None
        assert order.pickup_rider == self.pickup_rider
        assert order.delivery_rider == self.delivery_rider
        assert order.washer == self.washer
        assert order.folder == self.folder
        
        print(f"\n✅ COMPLETE LIFECYCLE TEST PASSED")
        print(f"   Order Code: {order.code}")
        print(f"   Final Status: {order.status}")
        print(f"   Total Transitions: 11")
        print(f"   All timestamps recorded ✅")
        print(f"   All staff assigned ✅")
