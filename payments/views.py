import requests
import base64
import logging
import os
from datetime import datetime
from django.conf import settings
from rest_framework import views, viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import BNPLUser, Payment, TradeIn
from .serializers import BNPLUserSerializer, TradeInSerializer
from orders.models import Order

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)

class BNPLViewSet(viewsets.GenericViewSet):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = BNPLUserSerializer

    def get_queryset(self):
        return BNPLUser.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get the user's BNPL status."""
        try:
            bnpl_user = BNPLUser.objects.get(user=request.user)
            serializer = self.get_serializer(bnpl_user)
            return Response(serializer.data)
        except BNPLUser.DoesNotExist:
            return Response({
                'is_enrolled': False,
                'credit_limit': 0,
                'current_balance': 0
            })

    @action(detail=False, methods=['post'])
    def opt_in(self, request):
        """Opt in to BNPL service."""
        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response(
                {'detail': 'Phone number is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is already enrolled
        bnpl_user, created = BNPLUser.objects.get_or_create(
            user=request.user,
            defaults={
                'phone_number': phone_number,
                'is_active': True
            }
        )

        if not created:
            if not bnpl_user.is_active:
                bnpl_user.is_active = True
                bnpl_user.phone_number = phone_number
                bnpl_user.save()
                serializer = self.get_serializer(bnpl_user)
                return Response(serializer.data)
            return Response(
                {'detail': 'You are already enrolled in BNPL'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(bnpl_user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def opt_out(self, request):
        """Opt out of BNPL service."""
        try:
            bnpl_user = BNPLUser.objects.get(user=request.user)
            if bnpl_user.current_balance > 0:
                return Response(
                    {'detail': 'Cannot opt out while you have an outstanding balance'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            bnpl_user.is_active = False
            bnpl_user.save()
            return Response({'detail': 'Successfully opted out of BNPL'})
        except BNPLUser.DoesNotExist:
            return Response(
                {'detail': 'You are not enrolled in BNPL'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def process(self, request):
        """Process a BNPL payment for an order."""
        try:
            order_id = request.data.get('order_id')
            amount = request.data.get('amount')

            if not all([order_id, amount]):
                return Response(
                    {'detail': 'order_id and amount are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                amount = float(amount)
                if amount <= 0:
                    return Response(
                        {'detail': 'Amount must be greater than 0'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Invalid amount format'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # SECURITY: Validate that the amount matches the actual order price
            validation_error = self._validate_bnpl_order_amount(order_id, amount)
            if validation_error:
                return validation_error

            # Extract numeric part from order_id (e.g., 'WW-00225' -> 225)
            # For BNPL or non-numeric references, use a smaller hash
            order_id_numeric = None
            if isinstance(order_id, str):
                import re
                # Try to find regular order IDs first (WW-00225 format)
                numeric_matches = re.findall(r'\d+', order_id)
                if numeric_matches:
                    try:
                        # Use the first number (usually the order number)
                        first_num = int(numeric_matches[0])
                        # Ensure it fits in PositiveIntegerField (max 2147483647)
                        if first_num <= 2147483647:
                            order_id_numeric = first_num
                        else:
                            # If too large, use modulo
                            order_id_numeric = first_num % 1000000
                    except (ValueError, TypeError):
                        pass
                
                # If we couldn't extract a number, use hash of the string
                if order_id_numeric is None:
                    order_id_numeric = abs(hash(order_id)) % 1000000
            else:
                try:
                    order_id_numeric = int(order_id)
                    if order_id_numeric > 2147483647:
                        order_id_numeric = order_id_numeric % 1000000
                except (ValueError, TypeError):
                    order_id_numeric = None

            # Get or create BNPL user
            bnpl_user = BNPLUser.objects.get(user=request.user)

            if not bnpl_user.is_active:
                return Response(
                    {'detail': 'Your BNPL account is inactive'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate available credit (convert to Decimal for proper calculation)
            from decimal import Decimal
            amount_decimal = Decimal(str(amount))
            available_credit = bnpl_user.credit_limit - bnpl_user.current_balance

            # Check if order amount exceeds available credit
            if amount_decimal > available_credit:
                return Response(
                    {
                        'detail': f'Order amount exceeds available credit',
                        'required_amount': amount,
                        'available_credit': float(available_credit),
                        'credit_limit': float(bnpl_user.credit_limit),
                        'current_balance': float(bnpl_user.current_balance)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update BNPL balance
            bnpl_user.current_balance += amount_decimal
            bnpl_user.save()

            # Create Payment record
            payment = Payment.objects.create(
                user=request.user,
                order_id=order_id_numeric,
                amount=amount_decimal,
                phone_number=bnpl_user.phone_number,
                provider='bnpl',
                status='success',
                raw_payload={
                    'order_reference': order_id,
                    'credit_limit': str(bnpl_user.credit_limit),
                    'new_balance': str(bnpl_user.current_balance)
                }
            )
            payment.mark_success()

            serializer = self.get_serializer(bnpl_user)
            return Response(
                {
                    'detail': 'BNPL payment processed successfully',
                    'bnpl_status': serializer.data,
                    'payment_id': payment.id
                },
                status=status.HTTP_201_CREATED
            )

        except BNPLUser.DoesNotExist:
            return Response(
                {'detail': 'You are not enrolled in BNPL. Please enroll first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error processing BNPL payment: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error processing BNPL payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_bnpl_order_amount(self, order_id, amount):
        """Validate that the provided amount matches the actual order price.
        
        SECURITY: This prevents users from modifying the amount in the URL
        to pay less than the actual order requires.
        
        Args:
            order_id: The order code (e.g., 'WW-00225')
            amount: The amount being paid
            
        Returns:
            None if valid, or a Response object with error details if invalid
        """
        try:
            from decimal import Decimal
            
            # Game wallet or non-order payments don't need validation
            if order_id == 'GAME_WALLET_TOPUP' or order_id is None:
                return None

            # Try to find the order by its code
            try:
                order = Order.objects.get(code=order_id)
            except Order.DoesNotExist:
                logger.warning(f"[SECURITY] BNPL: Order not found with code: {order_id}")
                return Response(
                    {'detail': f'Order not found: {order_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the actual order price
            order_price = order.actual_price or order.price
            
            if order_price is None:
                logger.error(f"[SECURITY] BNPL: Order {order_id} has no price set")
                return Response(
                    {'detail': f'Order price is not set'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Convert to Decimal for accurate comparison
            order_price_decimal = Decimal(str(order_price))
            amount_decimal = Decimal(str(amount))
            
            # Check if amounts match (allow 0.01 tolerance for rounding)
            if abs(order_price_decimal - amount_decimal) > Decimal('0.01'):
                logger.warning(
                    f"[SECURITY] FRAUD ALERT - BNPL Amount mismatch for order {order_id}: "
                    f"requested={amount}, actual={order_price}"
                )
                return Response(
                    {
                        'detail': f'Payment amount does not match order total',
                        'expected_amount': float(order_price),
                        'provided_amount': amount,
                        'order_id': order_id
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"[SECURITY] BNPL order amount validated for {order_id}: {amount} KES")
            return None
            
        except Exception as e:
            logger.error(f"[SECURITY] Error validating BNPL order amount: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error validating order: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def users(self, request):
        """Get all BNPL users (for admin)."""
        # Allow only staff/admin to view all users
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied. Admin access required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        page_size = request.query_params.get('page_size', 100)
        bnpl_users = BNPLUser.objects.all().order_by('-created_at')
        
        try:
            page_size = int(page_size)
            bnpl_users = bnpl_users[:page_size]
        except (ValueError, TypeError):
            pass
        
        serializer = self.get_serializer(bnpl_users, many=True)
        return Response(serializer.data)


class MpesaSTKPushView(views.APIView):
    permission_classes = []  # Allow unauthenticated access
    authentication_classes = []

    def get(self, request):
        """Get user's phone number for checkout (if authenticated)."""
        if request.user.is_authenticated:
            phone = None
            if hasattr(request.user, 'phone_number'):
                phone = request.user.phone_number
            elif hasattr(request.user, 'profile') and hasattr(request.user.profile, 'phone_number'):
                phone = request.user.profile.phone_number
            
            if phone:
                return Response({'phone_number': phone})
        
        return Response({'phone_number': None})

    def post(self, request):
        """Initiate M-Pesa STK Push payment."""
        amount = request.data.get('amount')
        phone = request.data.get('phone')
        order_id = request.data.get('order_id')  # Can be null for game wallet top-ups
        
        logger.info(f"STK Push request: amount={amount}, phone={phone}, order_id={order_id}")
        
        # If no phone provided and user is authenticated, try to get from user profile
        if not phone and request.user.is_authenticated:
            # Try to get phone from user profile
            if hasattr(request.user, 'phone_number'):
                phone = request.user.phone_number
                logger.info(f"Using phone from user profile: {phone}")
            elif hasattr(request.user, 'profile') and hasattr(request.user.profile, 'phone_number'):
                phone = request.user.profile.phone_number
                logger.info(f"Using phone from user.profile: {phone}")
        
        # Validate input - order_id is optional (null for game wallet top-ups)
        if not all([amount, phone]):
            error_msg = f'Missing required fields: amount={bool(amount)}, phone={bool(phone)}'
            logger.error(error_msg)
            return Response(
                {'detail': 'amount and phone are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert amount to numeric
        try:
            amount_float = float(amount)
            amount = int(amount_float)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # SECURITY: Validate that the amount matches the actual order price
        validation_error = self._validate_mpesa_order_amount(order_id, amount_float)
        if validation_error:
            return validation_error
        
        # Store original order_id for reference, extract numeric part if available
        order_reference = order_id
        order_id_numeric = None
        
        # Try to extract numeric part from order_id (e.g., 'WW-00176' -> 176)
        if isinstance(order_id, str):
            import re
            # Try to find regular order IDs first (WW-00225 format)
            numeric_matches = re.findall(r'\d+', order_id)
            if numeric_matches:
                try:
                    # Use the first number (usually the order number)
                    first_num = int(numeric_matches[0])
                    # Ensure it fits in PositiveIntegerField (max 2147483647)
                    if first_num <= 2147483647:
                        order_id_numeric = first_num
                    else:
                        # If too large, use modulo
                        order_id_numeric = first_num % 1000000
                except (ValueError, TypeError):
                    pass
            
            # If we couldn't extract a number, use hash of the string
            if order_id_numeric is None:
                order_id_numeric = abs(hash(order_id)) % 1000000
        else:
            try:
                order_id_numeric = int(order_id)
                if order_id_numeric > 2147483647:
                    order_id_numeric = order_id_numeric % 1000000
            except (ValueError, TypeError):
                order_id_numeric = None
        
        # Validate phone number format (Kenyan format)
        if not self._validate_phone(phone):
            return Response(
                {'detail': 'Invalid phone number. Use format: 254712345678 or 0712345678'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Clean up phone number - remove + prefix if present
        if phone.startswith('+'):
            phone = phone[1:]
            logger.info(f"Cleaned phone number from request: {phone}")
        
        # Log the phone being used
        logger.info(f"Using phone number for STK Push: {phone}")
        
        try:
            # Verify credentials are set
            if not settings.MPESA_CONSUMER_KEY or not settings.MPESA_CONSUMER_SECRET:
                error_msg = 'M-Pesa credentials not configured. Check your .env file for MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET'
                logger.error(error_msg)
                return Response(
                    {'detail': error_msg},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Get access token from Daraja API
            access_token = self._get_access_token()
            
            # Determine if this is a game wallet top-up (order_id is null)
            is_game_wallet_topup = order_id is None
            account_reference = order_id if order_id else 'GAME_WALLET_TOPUP'
            
            # Initiate STK Push
            stk_response = self._initiate_stk_push(
                access_token, amount, phone, account_reference
            )
            
            # Create Payment record
            checkout_request_id = stk_response.get('CheckoutRequestID', '')
            payment = Payment.objects.create(
                user=request.user if request.user.is_authenticated else None,
                order_id=order_id_numeric,
                amount=amount,
                phone_number=phone,
                provider='mpesa',
                provider_reference=checkout_request_id,
                status='pending',
                raw_payload={
                    'order_reference': account_reference,
                    'is_game_wallet': is_game_wallet_topup
                }
            )
            payment.mark_initiated(provider_reference=checkout_request_id)
            
            logger.info(f"Payment initiated successfully: {checkout_request_id}, is_game_wallet: {is_game_wallet_topup}")
            return Response({
                'status': 'success',
                'message': 'STK push sent to your phone',
                'checkout_request_id': stk_response.get('CheckoutRequestID'),
                'order_id': order_id or 'GAME_WALLET_TOPUP',
                'amount': amount
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error initiating payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_mpesa_order_amount(self, order_id, amount):
        """Validate that the provided amount matches the actual order price.
        
        SECURITY: This prevents users from modifying the amount in the URL
        to pay less than the actual order requires.
        
        Args:
            order_id: The order code (e.g., 'WW-00225') or None for game wallet top-ups
            amount: The amount being paid
            
        Returns:
            None if valid, or a Response object with error details if invalid
        """
        try:
            # Game wallet top-ups don't need order validation
            if order_id is None or order_id == 'GAME_WALLET_TOPUP':
                return None

            # Try to find the order by its code
            try:
                order = Order.objects.get(code=order_id)
            except Order.DoesNotExist:
                logger.warning(f"[SECURITY] Order not found with code: {order_id}")
                return Response(
                    {'detail': f'Order not found: {order_id}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the actual order price
            from decimal import Decimal
            order_price = order.actual_price or order.price
            
            if order_price is None:
                logger.error(f"[SECURITY] Order {order_id} has no price set")
                return Response(
                    {'detail': f'Order price is not set'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Convert to Decimal for accurate comparison
            order_price_decimal = Decimal(str(order_price))
            amount_decimal = Decimal(str(amount))
            
            # Check if amounts match (allow 0.01 tolerance for rounding)
            if abs(order_price_decimal - amount_decimal) > Decimal('0.01'):
                logger.warning(
                    f"[SECURITY] FRAUD ALERT - Amount mismatch for order {order_id}: "
                    f"requested={amount}, actual={order_price}"
                )
                return Response(
                    {
                        'detail': f'Payment amount does not match order total',
                        'expected_amount': float(order_price),
                        'provided_amount': amount,
                        'order_id': order_id
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"[SECURITY] Order amount validated successfully for {order_id}: {amount} KES")
            return None
            
        except Exception as e:
            logger.error(f"[SECURITY] Error validating M-Pesa order amount: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error validating order: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _validate_phone(self, phone):
        """Validate Kenyan phone number."""
        # Remove + prefix if present
        clean_phone = phone.lstrip('+')
        
        # Accept formats: 254712345678 or 0712345678 or +254712345678
        if clean_phone.startswith('0') and len(clean_phone) == 10:
            return True
        if clean_phone.startswith('254') and len(clean_phone) == 12:
            return True
        return False

    def _get_mpesa_config(self):
        """Get M-Pesa configuration based on environment setting."""
        environment = os.getenv('MPESA_ENVIRONMENT', 'production').lower()
        
        if environment == 'sandbox':
            logger.info("Using SANDBOX M-Pesa environment")
            return {
                'consumer_key': os.getenv('MPESA_SANDBOX_CONSUMER_KEY'),
                'consumer_secret': os.getenv('MPESA_SANDBOX_CONSUMER_SECRET'),
                'business_shortcode': os.getenv('MPESA_SANDBOX_BUSINESS_SHORTCODE', '174379'),
                'passkey': os.getenv('MPESA_SANDBOX_PASSKEY'),
                'oauth_url': 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
                'stk_push_url': 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            }
        else:
            logger.info("Using PRODUCTION M-Pesa environment")
            return {
                'consumer_key': settings.MPESA_CONSUMER_KEY,
                'consumer_secret': settings.MPESA_CONSUMER_SECRET,
                'business_shortcode': settings.MPESA_BUSINESS_SHORTCODE,
                'passkey': settings.MPESA_PASSKEY,
                'oauth_url': 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
                'stk_push_url': 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            }

    def _get_access_token(self):
        """Get access token from Safaricom Daraja API."""
        config = self._get_mpesa_config()
        url = config['oauth_url']
        
        logger.info(f"Requesting access token from {url}")
        logger.info(f"Consumer Key (first 20 chars): {config['consumer_key'][:20] if config['consumer_key'] else 'NOT SET'}")
        
        try:
            response = requests.get(
                url,
                auth=(config['consumer_key'], config['consumer_secret']),
                timeout=10
            )
            logger.info(f"OAuth Response status: {response.status_code}")
            logger.info(f"OAuth Response body: {response.text}")
            
            response.raise_for_status()
            token = response.json()['access_token']
            logger.info(f"✓ Access token obtained successfully (length: {len(token)})")
            logger.info(f"Access token (first 20 chars): {token[:20]}...")
            return token
        except requests.exceptions.RequestException as e:
            # Log detailed response information
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Failed to get access token: HTTP {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
                logger.error(f"Response headers: {dict(e.response.headers)}")
            else:
                logger.error(f"Failed to get access token: {str(e)}")
            logger.error(f"Credentials issue check:")
            logger.error(f"  - Consumer Key: {repr(config['consumer_key'][:50] if config['consumer_key'] else 'NOT SET')}...")
            logger.error(f"  - Consumer Secret: {repr(config['consumer_secret'][:20] if config['consumer_secret'] else 'NOT SET')}...")
            raise Exception(f'Failed to get access token: {str(e)}')

    def _initiate_stk_push(self, access_token, amount, phone, order_id):
        """Send STK Push request to Daraja API."""
        config = self._get_mpesa_config()
        url = config['stk_push_url']
        
        # Generate timestamp and password
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self._encode_password(
            config['business_shortcode'],
            config['passkey'],
            timestamp
        )
        
        # Format phone number to 254 format
        formatted_phone = phone.replace('0', '254', 1) if phone.startswith('0') else phone
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": config['business_shortcode'],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": formatted_phone,
            "PartyB": config['business_shortcode'],
            "PhoneNumber": formatted_phone,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": order_id,
            "TransactionDesc": f"Wildwash Order {order_id}"
        }
        
        logger.info(f"Initiating STK Push to {formatted_phone} for amount {amount} KES")
        logger.info(f"STK Push URL: {url}")
        logger.info(f"STK Push Authorization header: Bearer {access_token[:20]}...")
        logger.info(f"STK Push payload: {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            logger.info(f"STK Push response status: {response.status_code}")
            logger.info(f"STK Push response body: {response.text}")
            logger.info(f"STK Push response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"STK Push returned non-200 status: {response.status_code}")
                logger.error(f"Full response: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            logger.info(f"STK Push successful. CheckoutRequestID: {result.get('CheckoutRequestID')}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"STK push request exception: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
                logger.error(f"Response content type: {e.response.headers.get('content-type')}")
            raise Exception(f'STK push failed: {str(e)}')

    @staticmethod
    def _encode_password(shortcode, passkey, timestamp):
        """Encode password for M-Pesa authentication."""
        password_string = f"{shortcode}{passkey}{timestamp}"
        return base64.b64encode(password_string.encode()).decode()


class MpesaCallbackView(views.APIView):
    """Handle M-Pesa callback notifications."""
    permission_classes = []  # Allow unauthenticated access for M-Pesa callbacks
    authentication_classes = []
    
    def post(self, request):
        """Process M-Pesa callback."""
        try:
            data = request.data
            checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
            result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            
            # Update payment status
            if checkout_request_id:
                payment = Payment.objects.get(provider_reference=checkout_request_id)
                
                if result_code == 0:
                    payment.mark_success(payload=data)
                    
                    # Check if this is a game wallet top-up
                    is_game_wallet = (payment.raw_payload or {}).get('is_game_wallet', False)
                    
                    if is_game_wallet and payment.user:
                        # Credit the game wallet
                        try:
                            from decimal import Decimal
                            from casino.models import GameWallet
                            
                            wallet, _ = GameWallet.objects.get_or_create(user=payment.user)
                            amount_decimal = Decimal(str(payment.amount))
                            wallet.add_funds(
                                amount_decimal,
                                source='mpesa',
                                payment_id=payment.pk,
                                notes=f'M-Pesa top-up via STK Push'
                            )
                            logger.info(f"Updated game wallet for user {payment.user}: added KES {amount_decimal}, new balance: {wallet.balance}")
                        except Exception as e:
                            logger.error(f"Error updating game wallet: {str(e)}", exc_info=True)
                    
                    # If this is a BNPL payment, update the user's BNPL balance
                    elif payment.provider == 'mpesa' and payment.user and 'BNPL' in (payment.raw_payload or {}).get('order_reference', ''):
                        try:
                            from decimal import Decimal
                            bnpl_user = BNPLUser.objects.get(user=payment.user)
                            # Reduce the balance by the payment amount
                            amount_decimal = Decimal(str(payment.amount))
                            bnpl_user.current_balance -= amount_decimal
                            if bnpl_user.current_balance < 0:
                                bnpl_user.current_balance = Decimal('0')
                            bnpl_user.save()
                            logger.info(f"Updated BNPL balance for user {payment.user}: {bnpl_user.current_balance}")
                        except BNPLUser.DoesNotExist:
                            logger.warning(f"BNPL user not found for payment user {payment.user}")
                        except Exception as e:
                            logger.error(f"Error updating BNPL balance: {str(e)}", exc_info=True)
                else:
                    payment.mark_failed(payload=data, note=f'Result Code: {result_code}')
            
            return Response({'status': 'success'})
        except Exception as e:
            logger.error(f"Callback processing error: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Callback processing error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentStatusView(views.APIView):
    """Check payment status by checkout request ID."""
    permission_classes = []
    authentication_classes = []
    
    def get(self, request):
        """Get payment status."""
        checkout_request_id = request.query_params.get('checkout_request_id')
        
        if not checkout_request_id:
            return Response(
                {'detail': 'checkout_request_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payment = Payment.objects.get(provider_reference=checkout_request_id)
            
            return Response({
                'status': payment.status,
                'amount': float(payment.amount),
                'phone': payment.phone_number,
                'initiated_at': payment.initiated_at,
                'completed_at': payment.completed_at,
                'error_message': payment.notes if payment.status == 'failed' else None
            }, status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return Response(
                {'detail': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching payment status: {str(e)}", exc_info=True)
            return Response(
                {'detail': f'Error fetching payment status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TradeInView(views.APIView):
    """Accept trade-in submissions from users and retrieve all trade-ins."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all trade-ins for the authenticated user."""
        try:
            tradeins = TradeIn.objects.filter(user=request.user).order_by('-created_at')
            serializer = TradeInSerializer(tradeins, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching trade-ins: {str(e)}", exc_info=True)
            return Response({'detail': f'Error fetching trade-ins: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            description = request.data.get('description')
            estimated_price = request.data.get('estimated_price')
            contact_phone = request.data.get('contact_phone')

            if not description or estimated_price is None:
                return Response({'detail': 'description and estimated_price are required'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                from decimal import Decimal
                estimated_price_dec = Decimal(str(estimated_price))
            except Exception:
                return Response({'detail': 'Invalid estimated_price'}, status=status.HTTP_400_BAD_REQUEST)

            tradein = TradeIn.objects.create(
                user=request.user,
                description=description,
                estimated_price=estimated_price_dec,
                contact_phone=contact_phone or ''
            )

            serializer = TradeInSerializer(tradein)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating trade-in: {str(e)}", exc_info=True)
            return Response({'detail': f'Error creating trade-in: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)