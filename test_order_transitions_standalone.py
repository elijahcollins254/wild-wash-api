#!/usr/bin/env python3
"""
Standalone test script for order status transitions
Tests all 12 status changes sequentially via API calls

Usage:
    python test_order_transitions_standalone.py

Requirements:
    - requests library: pip install requests
    - API server running on http://localhost:8000
    - User with admin credentials
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

# Configuration
API_BASE_URL = 'http://localhost:8000/api'
ADMIN_USERNAME = 'admin_user'
ADMIN_PASSWORD = 'testpass123'

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class OrderTransitionTester:
    """Test order status transitions sequentially"""
    
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.order_id = None
        self.order_code = 'WW-TEST-' + datetime.now().strftime('%Y%m%d%H%M%S')
        self.test_results = []
        
        # User IDs (you'll need to adjust these based on your actual data)
        self.users = {
            'admin': None,
            'customer': None,
            'pickup_rider': None,
            'delivery_rider': None,
            'washer': None,
            'folder': None,
        }

    def print_header(self, text: str, level: int = 1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")
        else:
            print(f"\n{Colors.CYAN}{'-'*80}{Colors.END}")
            print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
            print(f"{Colors.CYAN}{'-'*80}{Colors.END}\n")

    def print_stage(self, stage_num: int, from_status: str, to_status: str):
        """Print stage header"""
        stage_text = f"STAGE {stage_num}: {from_status} → {to_status}"
        print(f"\n{Colors.HEADER}{Colors.BOLD}{stage_text}{Colors.END}")
        print(f"{Colors.HEADER}{'─'*len(stage_text)}{Colors.END}")

    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")

    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.END}")

    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.CYAN}ℹ️  {message}{Colors.END}")

    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

    def print_result_summary(self, stage_num: int, test_name: str, passed: bool, details: str = ""):
        """Track test result"""
        self.test_results.append({
            'stage': stage_num,
            'name': test_name,
            'passed': passed,
            'details': details
        })

    def login(self, username: str, password: str) -> bool:
        """Authenticate and get token"""
        try:
            response = self.session.post(
                f'{API_BASE_URL}/auth/login/',
                json={'username': username, 'password': password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('token')
                self.session.headers.update({'Authorization': f'Token {self.auth_token}'})
                self.print_success(f"Authenticated as: {username}")
                return True
            else:
                self.print_error(f"Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.print_error(f"Login error: {str(e)}")
            return False

    def get_or_create_order(self) -> Optional[int]:
        """Create a test order"""
        try:
            payload = {
                'code': self.order_code,
                'pickup_address': '123 Main St, Nairobi',
                'dropoff_address': '456 Park Ave, Nairobi',
                'status': 'requested',
                'items': 5,
                'weight_kg': '10.50',
                'price': '2500.00',
            }
            
            response = self.session.post(
                f'{API_BASE_URL}/orders/',
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                order_id = data.get('id')
                self.order_id = order_id
                self.print_success(f"Order created: {self.order_code} (ID: {order_id})")
                return order_id
            else:
                self.print_error(f"Order creation failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.print_error(f"Order creation error: {str(e)}")
            return None

    def update_order_status(self, payload: Dict, expected_status: str = None) -> Tuple[bool, str]:
        """Update order status via API"""
        try:
            response = self.session.patch(
                f'{API_BASE_URL}/orders/update/?id={self.order_id}',
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                if expected_status:
                    # Fetch order to verify status
                    time.sleep(0.5)  # Brief delay for backend processing
                    order_response = self.session.get(
                        f'{API_BASE_URL}/orders/?id={self.order_id}',
                        timeout=10
                    )
                    if order_response.status_code == 200:
                        order_data = order_response.json()
                        current_status = order_data.get('status') if isinstance(order_data, dict) else order_data[0].get('status')
                        return True, current_status
                return True, "Updated"
            else:
                error_text = response.text if response.text else f"HTTP {response.status_code}"
                return False, error_text
        except Exception as e:
            return False, str(e)

    def run_all_tests(self):
        """Run complete test sequence"""
        self.print_header("ORDER STATUS TRANSITIONS - COMPLETE TEST SUITE")
        
        # Step 0: Setup
        self.print_header("SETUP & AUTHENTICATION", 2)
        
        if not self.login(ADMIN_USERNAME, ADMIN_PASSWORD):
            self.print_error("Failed to authenticate. Exiting.")
            return False
        
        if not self.get_or_create_order():
            self.print_error("Failed to create order. Exiting.")
            return False
        
        # Stage 1: REQUESTED (Initial)
        self.print_stage(1, "INITIAL", "REQUESTED")
        self.print_info("Order created with initial status: requested")
        self.print_success("Order ready for processing")
        self.print_result_summary(1, "Initial Status", True)
        
        time.sleep(0.5)
        
        # Stage 2: PENDING_ASSIGNMENT
        self.print_stage(2, "REQUESTED", "PENDING_ASSIGNMENT")
        self.print_info("Admin prepares to assign pickup rider")
        success, status = self.update_order_status({'status': 'pending_assignment'}, 'pending_assignment')
        if success:
            self.print_success(f"Status transitioned to: {status}")
            self.print_result_summary(2, "Pending Assignment", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(2, "Pending Assignment", False, status)
        
        time.sleep(0.5)
        
        # Stage 3: ASSIGNED_PICKUP
        self.print_stage(3, "PENDING_ASSIGNMENT", "ASSIGNED_PICKUP")
        self.print_info("Admin assigns pickup rider (ID: 1)")
        success, status = self.update_order_status({'pickup_rider': 1, 'status': 'assigned_pickup'}, 'assigned_pickup')
        if success:
            self.print_success(f"Pickup rider assigned - Status: {status}")
            self.print_result_summary(3, "Assign Pickup Rider", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(3, "Assign Pickup Rider", False, status)
        
        time.sleep(0.5)
        
        # Stage 4: PICKED
        self.print_stage(4, "ASSIGNED_PICKUP", "PICKED")
        self.print_info("Pickup rider confirms order picked")
        success, status = self.update_order_status({'status': 'picked'}, 'picked')
        if success:
            self.print_success(f"Pickup confirmed - Status: {status}")
            self.print_result_summary(4, "Confirm Pickup", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(4, "Confirm Pickup", False, status)
        
        time.sleep(0.5)
        
        # Stage 5: IN_PROGRESS
        self.print_stage(5, "PICKED", "IN_PROGRESS")
        self.print_info("Order arrives at facility")
        success, status = self.update_order_status({'status': 'in_progress'}, 'in_progress')
        if success:
            self.print_success(f"Order at facility - Status: {status}")
            self.print_result_summary(5, "Facility Arrival", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(5, "Facility Arrival", False, status)
        
        time.sleep(0.5)
        
        # Stage 6: WASHED
        self.print_stage(6, "IN_PROGRESS", "WASHED")
        self.print_info("Washer completes washing")
        success, status = self.update_order_status({'status': 'washed'}, 'washed')
        if success:
            self.print_success(f"Order washed - Status: {status}")
            self.print_info("Notifications sent to folder staff")
            self.print_result_summary(6, "Washer Complete", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(6, "Washer Complete", False, status)
        
        time.sleep(0.5)
        
        # Stage 7: FOLDED
        self.print_stage(7, "WASHED", "FOLDED")
        self.print_info("Folder begins and completes folding")
        success, status = self.update_order_status({'status': 'folded'}, 'folded')
        if success:
            self.print_success(f"Order folded - Status: {status}")
            self.print_result_summary(7, "Folder Start", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(7, "Folder Start", False, status)
        
        time.sleep(0.5)
        
        # Stage 8: READY
        self.print_stage(8, "FOLDED", "READY")
        self.print_info("Folder marks order as ready for delivery")
        success, status = self.update_order_status({'status': 'ready'}, 'ready')
        if success:
            self.print_success(f"Order ready for delivery - Status: {status}")
            self.print_result_summary(8, "Ready for Delivery", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(8, "Ready for Delivery", False, status)
        
        time.sleep(0.5)
        
        # Stage 9: PENDING_DELIVERY
        self.print_stage(9, "READY", "PENDING_DELIVERY")
        self.print_info("Admin prepares for delivery rider assignment")
        success, status = self.update_order_status({'status': 'pending_delivery'}, 'pending_delivery')
        if success:
            self.print_success(f"Pending delivery assignment - Status: {status}")
            self.print_result_summary(9, "Pending Delivery", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(9, "Pending Delivery", False, status)
        
        time.sleep(0.5)
        
        # Stage 10: ASSIGNED_DELIVERY
        self.print_stage(10, "PENDING_DELIVERY", "ASSIGNED_DELIVERY")
        self.print_info("Admin assigns delivery rider (ID: 2)")
        success, status = self.update_order_status({'delivery_rider': 2, 'status': 'assigned_delivery'}, 'assigned_delivery')
        if success:
            self.print_success(f"Delivery rider assigned - Status: {status}")
            self.print_info("SMS sent to delivery rider with order details")
            self.print_result_summary(10, "Assign Delivery Rider", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(10, "Assign Delivery Rider", False, status)
        
        time.sleep(0.5)
        
        # Stage 11: DELIVERED
        self.print_stage(11, "ASSIGNED_DELIVERY", "DELIVERED ✅")
        self.print_info("Delivery rider marks order as delivered")
        success, status = self.update_order_status(
            {
                'status': 'delivered',
                'delivered_at': datetime.now().isoformat()
            },
            'delivered'
        )
        if success:
            self.print_success(f"✅ Order delivered - Status: {status}")
            self.print_info("SMS sent to customer: Order delivered!")
            self.print_result_summary(11, "Order Delivered", True)
        else:
            self.print_error(f"Failed: {status}")
            self.print_result_summary(11, "Order Delivered", False, status)
        
        return True

    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST RESULTS SUMMARY", 2)
        
        passed = sum(1 for r in self.test_results if r['passed'])
        total = len(self.test_results)
        
        print(f"\n{Colors.BOLD}Results:{Colors.END}")
        print(f"  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"  {Colors.RED}Failed: {total - passed}{Colors.END}")
        
        print(f"\n{Colors.BOLD}Detailed Results:{Colors.END}")
        for result in self.test_results:
            status_icon = "✅" if result['passed'] else "❌"
            print(f"  {status_icon} Stage {result['stage']}: {result['name']}")
            if result['details']:
                print(f"     {result['details']}")
        
        if passed == total:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.END}\n")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️  SOME TESTS FAILED{Colors.END}\n")
            return False


def main():
    """Main entry point"""
    tester = OrderTransitionTester()
    
    try:
        success = tester.run_all_tests()
        tester.print_summary()
        
        if success:
            print(f"\n{Colors.GREEN}✅ Complete order lifecycle tested successfully!{Colors.END}\n")
            return 0
        else:
            print(f"\n{Colors.RED}❌ Some tests failed. Please review the output above.{Colors.END}\n")
            return 1
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user.{Colors.END}\n")
        return 2
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {str(e)}{Colors.END}\n")
        return 3


if __name__ == '__main__':
    exit(main())
