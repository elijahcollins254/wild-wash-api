# riders/views.py
import logging
import os
import re
import secrets
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from .models import RiderLocation, RiderProfile, RiderWallet, RiderWalletTransaction
from .serializers import RiderLocationSerializer, RiderProfileSerializer

logger = logging.getLogger(__name__)


def _is_rider(user):
    return getattr(user, 'role', None) == 'rider'


def _can_manage_rider_wallet(admin_user, rider):
    if admin_user.is_superuser:
        return True
    return bool(
        admin_user.is_staff
        and admin_user.service_location_id
        and rider.service_location_id == admin_user.service_location_id
    )


def _format_ke_phone(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('0') and len(digits) == 10:
        digits = '254' + digits[1:]
    elif digits.startswith('7') and len(digits) == 9:
        digits = '254' + digits
    if len(digits) != 12 or not digits.startswith('254') or digits[3] not in '17':
        return None
    return digits


def _wallet_payload(wallet):
    return {
        'balance': str(wallet.balance),
        'payout_phone': wallet.payout_phone or wallet.rider.phone or '',
        'transactions': [
            {
                'id': item.id,
                'reference': str(item.reference),
                'type': item.transaction_type,
                'status': item.status,
                'amount': str(item.amount),
                'balance_after': str(item.balance_after),
                'reason': item.reason,
                'payout_phone': item.payout_phone,
                'provider_transaction_id': item.provider_transaction_id,
                'created_at': item.created_at,
            }
            for item in wallet.transactions.all()[:100]
        ],
    }


class RiderWalletView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _is_rider(request.user):
            return Response({'detail': 'Rider account required.'}, status=status.HTTP_403_FORBIDDEN)
        wallet, _ = RiderWallet.objects.get_or_create(
            rider=request.user,
            defaults={'payout_phone': _format_ke_phone(request.user.phone) or ''},
        )
        return Response(_wallet_payload(wallet))

    def patch(self, request):
        if not _is_rider(request.user):
            return Response({'detail': 'Rider account required.'}, status=status.HTTP_403_FORBIDDEN)
        phone = _format_ke_phone(request.data.get('payout_phone'))
        if not phone:
            return Response({'detail': 'Enter a valid Kenyan M-Pesa number.'}, status=status.HTTP_400_BAD_REQUEST)
        wallet, _ = RiderWallet.objects.get_or_create(rider=request.user)
        wallet.payout_phone = phone
        wallet.save(update_fields=['payout_phone', 'updated_at'])
        return Response(_wallet_payload(wallet))

    def post(self, request):
        if not _is_rider(request.user):
            return Response({'detail': 'Rider account required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            amount = Decimal(str(request.data.get('amount', '')))
        except (InvalidOperation, ValueError, TypeError):
            return Response({'detail': 'Enter a valid withdrawal amount.'}, status=status.HTTP_400_BAD_REQUEST)
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999') or amount != amount.to_integral_value():
            return Response({'detail': 'Withdrawal amount must be a positive whole number of KES.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            wallet, _ = RiderWallet.objects.get_or_create(rider=request.user)
            wallet = RiderWallet.objects.select_for_update().get(pk=wallet.pk)
            existing_pending = wallet.transactions.filter(
                transaction_type=RiderWalletTransaction.TYPE_WITHDRAWAL,
                status=RiderWalletTransaction.STATUS_PENDING,
            ).first()
            if existing_pending:
                return Response(
                    {'detail': 'A withdrawal is already being processed.', 'reference': str(existing_pending.reference)},
                    status=status.HTTP_409_CONFLICT,
                )
            phone = wallet.payout_phone or _format_ke_phone(request.user.phone)
            if not phone:
                return Response({'detail': 'Add a valid M-Pesa payout number to your profile first.'}, status=status.HTTP_400_BAD_REQUEST)
            b2c_environment = getattr(settings, 'MPESA_ENVIRONMENT', 'production').lower()
            mpesa_credentials_ready = (
                bool(getattr(settings, 'MPESA_SANDBOX_CONSUMER_KEY', '') and getattr(settings, 'MPESA_SANDBOX_CONSUMER_SECRET', ''))
                if b2c_environment == 'sandbox'
                else bool(settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET)
            )
            if not all([
                mpesa_credentials_ready,
                getattr(settings, 'MPESA_B2C_INITIATOR_NAME', ''),
                getattr(settings, 'MPESA_B2C_SECURITY_CREDENTIAL', ''),
                getattr(settings, 'MPESA_B2C_RESULT_URL', ''),
                getattr(settings, 'MPESA_B2C_TIMEOUT_URL', ''),
                getattr(settings, 'MPESA_B2C_CALLBACK_TOKEN', ''),
            ]):
                return Response({'detail': 'M-Pesa withdrawals are not configured yet. Contact support.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            if wallet.balance < amount:
                return Response({'detail': 'Insufficient available balance.', 'balance': str(wallet.balance)}, status=status.HTTP_400_BAD_REQUEST)

            wallet.balance -= amount
            wallet.save(update_fields=['balance', 'updated_at'])
            payout = RiderWalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=RiderWalletTransaction.TYPE_WITHDRAWAL,
                status=RiderWalletTransaction.STATUS_PENDING,
                amount=amount,
                balance_after=wallet.balance,
                payout_phone=phone,
                reason='Rider M-Pesa withdrawal',
            )

        try:
            response_data = _submit_b2c_payout(payout, phone)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            # The request may have reached Safaricom even if the response was lost.
            # Keep funds reserved and let Daraja callback/reconciliation resolve it.
            logger.exception('B2C submission outcome is unknown for %s', payout.reference)
            payout.provider_payload = {'submission_outcome': 'unknown', 'error': str(exc)}
            payout.save(update_fields=['provider_payload', 'updated_at'])
            return Response({
                'message': 'M-Pesa did not return a response. The withdrawal remains pending while we confirm its status; do not submit another request.',
                'reference': str(payout.reference),
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            logger.exception('Unable to submit rider B2C payout %s', payout.reference)
            _fail_rider_withdrawal(payout.pk, {'error': str(exc)}, 'Could not submit payout to M-Pesa')
            return Response({'detail': 'M-Pesa payout could not be initiated. The amount was returned to your wallet.'}, status=status.HTTP_502_BAD_GATEWAY)

        payout.conversation_id = str(response_data.get('ConversationID') or '')
        payout.originator_conversation_id = str(response_data.get('OriginatorConversationID') or '')
        payout.provider_payload = response_data
        payout.save(update_fields=['conversation_id', 'originator_conversation_id', 'provider_payload', 'updated_at'])
        payout.refresh_from_db()
        return Response({
            'message': 'Withdrawal request submitted. The wallet balance is reserved until M-Pesa confirms the result.',
            'transaction': _wallet_payload(payout.wallet)['transactions'][0],
        }, status=status.HTTP_202_ACCEPTED)


class AdminRiderWalletsView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        riders = User.objects.filter(role='rider').order_by('first_name', 'username')
        if not request.user.is_superuser:
            if not request.user.is_staff or not request.user.service_location_id:
                return Response({'detail': 'You do not have permission to manage rider wallets.'}, status=status.HTTP_403_FORBIDDEN)
            riders = riders.filter(service_location_id=request.user.service_location_id)
        wallets = {wallet.rider_id: wallet for wallet in RiderWallet.objects.filter(rider__in=riders)}
        return Response([
            {
                'rider_id': rider.id,
                'username': rider.username,
                'name': (f'{rider.first_name} {rider.last_name}'.strip() or rider.username),
                'phone': rider.phone or '',
                'balance': str(wallets[rider.id].balance) if rider.id in wallets else '0.00',
            }
            for rider in riders
        ])


class AdminRiderWalletCreditView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, rider_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        rider = User.objects.filter(pk=rider_id, role='rider').first()
        if rider is None:
            return Response({'detail': 'Rider not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_manage_rider_wallet(request.user, rider):
            return Response({'detail': 'You do not have permission to credit this rider wallet.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            amount = Decimal(str(request.data.get('amount', '')))
        except (InvalidOperation, ValueError, TypeError):
            return Response({'detail': 'Enter a valid credit amount.'}, status=status.HTTP_400_BAD_REQUEST)
        if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99') or amount != amount.quantize(Decimal('0.01')):
            return Response({'detail': 'Credit amount must be positive and have at most two decimal places.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get('reason', '')).strip()
        if not reason:
            return Response({'detail': 'A credit reason is required for the audit record.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            wallet, _ = RiderWallet.objects.get_or_create(rider=rider)
            wallet = RiderWallet.objects.select_for_update().get(pk=wallet.pk)
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
            entry = RiderWalletTransaction.objects.create(
                wallet=wallet,
                transaction_type=RiderWalletTransaction.TYPE_CREDIT,
                status=RiderWalletTransaction.STATUS_COMPLETED,
                amount=amount,
                balance_after=wallet.balance,
                reason=reason,
                created_by=request.user,
            )
        return Response({'balance': str(wallet.balance), 'transaction_id': entry.id}, status=status.HTTP_201_CREATED)


class MpesaB2CResultView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not _valid_b2c_callback(request):
            return Response({'detail': 'Invalid callback credential.'}, status=status.HTTP_403_FORBIDDEN)
        result = request.data.get('Result', {})
        if not isinstance(result, dict) or result.get('ResultCode') is None:
            return Response({'detail': 'Malformed B2C result callback.'}, status=status.HTTP_400_BAD_REQUEST)
        originator_id = result.get('OriginatorConversationID')
        conversation_id = result.get('ConversationID')
        payout = RiderWalletTransaction.objects.filter(
            transaction_type=RiderWalletTransaction.TYPE_WITHDRAWAL,
        ).filter(
            originator_conversation_id=originator_id
        ).first() if originator_id else None
        if payout is None and conversation_id:
            payout = RiderWalletTransaction.objects.filter(conversation_id=conversation_id).first()
        if payout is None:
            logger.warning('Unmatched Daraja B2C result callback (originator id=%s)', originator_id)
            return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        if str(result.get('ResultCode')) == '0':
            with transaction.atomic():
                locked = RiderWalletTransaction.objects.select_for_update().get(pk=payout.pk)
                if locked.status == RiderWalletTransaction.STATUS_PENDING:
                    locked.status = RiderWalletTransaction.STATUS_COMPLETED
                    locked.provider_transaction_id = str(result.get('TransactionID') or '')
                    locked.provider_payload = request.data
                    locked.save(update_fields=['status', 'provider_transaction_id', 'provider_payload', 'updated_at'])
        else:
            _fail_rider_withdrawal(payout.pk, request.data, str(result.get('ResultDesc') or 'M-Pesa payout failed'))
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class MpesaB2CTimeoutView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not _valid_b2c_callback(request):
            return Response({'detail': 'Invalid callback credential.'}, status=status.HTTP_403_FORBIDDEN)
        callback_data = request.data.get('Result', request.data)
        originator_id = callback_data.get('OriginatorConversationID') if isinstance(callback_data, dict) else None
        logger.warning('Daraja B2C timeout callback received (originator id=%s)', originator_id)
        payout = RiderWalletTransaction.objects.filter(originator_conversation_id=originator_id).first() if originator_id else None
        if payout:
            payout.provider_payload = {'timeout': callback_data}
            payout.save(update_fields=['provider_payload', 'updated_at'])
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


def _valid_b2c_callback(request):
    expected = getattr(settings, 'MPESA_B2C_CALLBACK_TOKEN', '')
    supplied = request.query_params.get('token', '')
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def _fail_rider_withdrawal(transaction_id, payload, reason):
    with transaction.atomic():
        payout = RiderWalletTransaction.objects.select_for_update().select_related('wallet').get(pk=transaction_id)
        if payout.status != RiderWalletTransaction.STATUS_PENDING:
            return
        wallet = RiderWallet.objects.select_for_update().get(pk=payout.wallet_id)
        wallet.balance += payout.amount
        wallet.save(update_fields=['balance', 'updated_at'])
        payout.status = RiderWalletTransaction.STATUS_FAILED
        payout.reason = reason
        payout.provider_payload = payload if isinstance(payload, dict) else {'detail': str(payload)}
        payout.save(update_fields=['status', 'reason', 'provider_payload', 'updated_at'])
        RiderWalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=RiderWalletTransaction.TYPE_REVERSAL,
            status=RiderWalletTransaction.STATUS_COMPLETED,
            amount=payout.amount,
            balance_after=wallet.balance,
            reason=f'Reversal for withdrawal {payout.reference}: {reason}',
            created_by=None,
        )


def _submit_b2c_payout(payout, phone):
    environment = getattr(settings, 'MPESA_ENVIRONMENT', os.getenv('MPESA_ENVIRONMENT', 'production')).lower()
    is_sandbox = environment == 'sandbox'
    initiator = getattr(settings, 'MPESA_B2C_INITIATOR_NAME', '')
    security_credential = getattr(settings, 'MPESA_B2C_SECURITY_CREDENTIAL', '')
    shortcode = getattr(settings, 'MPESA_B2C_SHORTCODE', '')
    result_url = getattr(settings, 'MPESA_B2C_RESULT_URL', '')
    timeout_url = getattr(settings, 'MPESA_B2C_TIMEOUT_URL', '')
    callback_token = getattr(settings, 'MPESA_B2C_CALLBACK_TOKEN', '')
    if not all([initiator, security_credential, shortcode, result_url, timeout_url, callback_token]):
        raise RuntimeError('B2C credentials, callback URLs, and callback token are not fully configured.')

    def secure_callback_url(url):
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query['token'] = callback_token
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))

    from payments.views import MpesaSTKPushView
    access_token = MpesaSTKPushView()._get_access_token()
    endpoint = (
        'https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest'
        if is_sandbox else 'https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest'
    )
    payload = {
        'InitiatorName': initiator,
        'SecurityCredential': security_credential,
        'CommandID': getattr(settings, 'MPESA_B2C_COMMAND_ID', 'BusinessPayment'),
        'Amount': int(payout.amount),
        'PartyA': shortcode,
        'PartyB': phone,
        'Remarks': f'Rider withdrawal {payout.reference}',
        'QueueTimeOutURL': secure_callback_url(timeout_url),
        'ResultURL': secure_callback_url(result_url),
        'Occasion': str(payout.reference)[:20],
    }
    response = requests.post(
        endpoint,
        json=payload,
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if str(data.get('ResponseCode')) != '0':
        raise RuntimeError(data.get('ResponseDescription') or 'Daraja rejected the B2C request.')
    payout.conversation_id = str(data.get('ConversationID') or '')
    payout.originator_conversation_id = str(data.get('OriginatorConversationID') or '')
    payout.provider_payload = data
    payout.save(update_fields=['conversation_id', 'originator_conversation_id', 'provider_payload', 'updated_at'])
    return data


class RiderLocationViewSet(viewsets.ModelViewSet):
    """Private viewset: riders push GPS updates. Auth required for create/update."""
    queryset = RiderLocation.objects.all().order_by('-id')
    serializer_class = RiderLocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Riders see their own locations; staff can see all
        if self.request.user.is_staff:
            return super().get_queryset()
        return self.queryset.filter(rider=self.request.user)

    def perform_create(self, serializer):
        serializer.save(rider=self.request.user)


class PublicRiderLocationsView(APIView):
    """
    Public endpoint: GET /riders/ -> returns an array of latest RiderLocation entries,
    one per rider, newest first. No authentication required.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        qs = RiderLocation.objects.all().order_by("-recorded_at", "-created_at")
        latest_by_rider = {}
        for loc in qs:
            rider_id = getattr(loc, "rider_id", None)
            rider_key = f"anon-{loc.id}" if rider_id is None else str(rider_id)
            if rider_key not in latest_by_rider:
                latest_by_rider[rider_key] = loc

        latest_list = list(latest_by_rider.values())
        serializer = RiderLocationSerializer(latest_list, many=True, context={"request": request})
        return Response(serializer.data)


class RiderProfileViewSet(viewsets.ModelViewSet):
    """
    Read (public) access to rider profiles. Creation/updates/deletes restricted to admin.
    Routes:
      - GET /riders/profiles/         -> list
      - GET /riders/profiles/<pk>/    -> retrieve
      - POST/PUT/PATCH/DELETE         -> admin only
    """
    queryset = RiderProfile.objects.select_related("user", "user__service_location").all().order_by("-created_at")
    serializer_class = RiderProfileSerializer

    def get_permissions(self):
        # Public read access, admin required for write
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
