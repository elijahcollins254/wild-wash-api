from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model, authenticate
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .serializers import (
    UserSerializer, UserCreateSerializer, ChangePasswordSerializer,
    LocationSerializer, StaffCreateSerializer, ActivityLogSerializer
)
from .models import Location, ActivityLog
from .permissions import LocationBasedPermission

from http.client import HTTPException

User = get_user_model()

def log_activity(user, action, description='', request=None, admin_user=None, changes=None):
    """
    Helper function to log user activity
    """
    try:
        ip_address = None
        user_agent = ''
        
        if request:
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        ActivityLog.objects.create(
            user=user,
            action=action,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            admin_user=admin_user,
            changes=changes or {}
        )
    except Exception as e:
        # Don't fail the main operation if logging fails
        print(f"Failed to log activity: {str(e)}")


from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
def get_csrf(request):
    # ensure_csrf_cookie will set the csrftoken cookie in the response headers
    return JsonResponse({"detail": "csrf cookie set"})


class UserProfileView(APIView):
    """
    View for handling the current user's profile
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        """Get the current user's profile"""
        serializer = self.serializer_class(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update the current user's profile"""
        serializer = self.serializer_class(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-friendly user viewset for managing all users.
    """
    queryset = User.objects.all().order_by('-id')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Allow anyone to create (signup) via create()
        if self.action == 'create':
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def partial_update(self, request, *args, **kwargs):
        """
        Override partial_update to log changes
        """
        user = self.get_object()
        
        # Track what changed
        changes = {}
        for field in ['first_name', 'last_name', 'email', 'phone_number', 'role', 'is_staff', 'is_superuser', 'is_active']:
            if field in request.data:
                old_value = getattr(user, field, None)
                new_value = request.data.get(field)
                if old_value != new_value:
                    changes[field] = {'old': str(old_value), 'new': str(new_value)}
        
        # Call parent partial_update
        response = super().partial_update(request, *args, **kwargs)
        
        # Log the activity
        if changes:
            description = f"User details updated: {', '.join(changes.keys())}"
            log_activity(
                user=user,
                action='details_edit',
                description=description,
                request=request,
                admin_user=request.user if request.user.is_staff or request.user.is_superuser else None,
                changes=changes
            )
        
        return response


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Login with phone number, email, or username and password
        Supports multiple phone formats: 0718693484, +254718693484, 254718693484
        """
        from services.sms_service import format_phone_number
        
        # Try to get user identifier (could be phone, email, or username)
        phone = request.data.get('phoneNumber') or request.data.get('phone')
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not password:
            return Response({'detail': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = None
        
        # Try phone number authentication first
        if phone:
            try:
                # Format the phone number to match stored format
                formatted_phone = format_phone_number(phone)
                # Try exact match first
                user = User.objects.get(phone=formatted_phone, is_active=True)
            except User.DoesNotExist:
                # Try without formatting in case it's already formatted
                try:
                    user = User.objects.get(phone=phone, is_active=True)
                except User.DoesNotExist:
                    pass
            except User.MultipleObjectsReturned:
                # Multiple users with same phone - this is a database integrity issue
                # Try to get the most recently created active user
                try:
                    user = User.objects.filter(phone=formatted_phone, is_active=True).order_by('-date_joined').first()
                except Exception:
                    pass
        
        # Try email authentication if phone didn't work
        if not user and email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                pass
        
        # Try username authentication if phone and email didn't work
        if not user and username:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                pass
        
        # If user not found
        if not user:
            return Response(
                {'detail': 'Invalid credentials. Please check your phone/email/username and try again.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Verify password
        if not user.check_password(password):
            return Response({'detail': 'Invalid password.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user is active
        if not user.is_active:
            return Response({'detail': 'This account is inactive.'}, status=status.HTTP_401_UNAUTHORIZED)
        
        token, _ = Token.objects.get_or_create(user=user)
        
        # Log the successful login
        log_activity(
            user=user,
            action='login',
            description='User logged in successfully',
            request=request
        )
        
        return Response({
            'token': token.key, 
            'user': UserSerializer(user).data
        })


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Log the password change
        log_activity(
            user=user,
            action='password_change',
            description='User changed their password',
            request=request
        )
        
        return Response({'status': 'password set'})


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LocationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing service locations.
    Only superusers can create/update/delete locations.
    Staff can view their assigned location.
    """
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [LocationBasedPermission]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()


class AdminLoginView(APIView):
    """
    Special login view for admin users that verifies superuser status
    Supports phone, email, or username with multiple phone formats
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from services.sms_service import format_phone_number
        
        phone = request.data.get('phoneNumber') or request.data.get('phone')
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not password:
            return Response({'detail': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = None
        
        # Try phone number authentication
        if phone:
            try:
                formatted_phone = format_phone_number(phone)
                user = User.objects.get(phone=formatted_phone)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(phone=phone)
                except User.DoesNotExist:
                    pass
        
        # Try email if phone didn't work
        if not user and email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                pass
        
        # Try username if phone and email didn't work
        if not user and username:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {'detail': 'Invalid credentials or not an admin'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_superuser:
            return Response(
                {'detail': 'You do not have admin privileges.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.check_password(password):
            return Response(
                {'detail': 'Invalid password.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'detail': 'This account is inactive.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class StaffLoginView(APIView):
    """
    Special login view for staff members that checks their location assignment
    Supports phone, email, or username with multiple phone formats
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from services.sms_service import format_phone_number
        
        phone = request.data.get('phoneNumber') or request.data.get('phone')
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not password:
            return Response({'detail': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = None
        
        # Try phone number authentication
        if phone:
            try:
                formatted_phone = format_phone_number(phone)
                user = User.objects.get(phone=formatted_phone)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(phone=phone)
                except User.DoesNotExist:
                    pass
        
        # Try email if phone didn't work
        if not user and email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                pass
        
        # Try username if phone and email didn't work
        if not user and username:
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {'detail': 'Invalid credentials or not a staff member'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_staff:
            return Response(
                {'detail': 'You do not have staff privileges.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.check_password(password):
            return Response(
                {'detail': 'Invalid password.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'detail': 'This account is inactive.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })


class StaffViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing staff members.
    Only superusers can access this ViewSet.
    """
    queryset = User.objects.filter(is_staff=True)
    serializer_class = StaffCreateSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return User.objects.filter(is_staff=True).exclude(is_superuser=True)

    def perform_create(self, serializer):
        user = serializer.save(is_staff=True)
        return user


class RequestPasswordResetView(APIView):
    """
    Request a password reset code.
    Sends a 4-digit code via SMS to the user's phone number.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from services.sms_service import AfricasTalkingSMSService, format_phone_number
        from .models import PasswordResetCode
        import random
        
        phone = request.data.get('phone')
        
        if not phone:
            return Response(
                {'detail': 'Phone number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            formatted_phone = format_phone_number(phone)
            user = User.objects.filter(phone=formatted_phone, is_active=True).first()
            if not user:
                return Response(
                    {'detail': 'If this phone number exists, you will receive a reset code.'},
                    status=status.HTTP_200_OK
                )
        except Exception:
            return Response(
                {'detail': 'Invalid phone number.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        code = str(random.randint(1000, 9999))
        PasswordResetCode.objects.create(user=user, phone=formatted_phone, code=code)
        
        try:
            sms_service = AfricasTalkingSMSService()
            message = f"Your Wildwash password reset code is: {code}. This code expires in 15 minutes."
            sms_service.send_sms(phone_number=formatted_phone, message=message)
        except Exception as e:
            print(f"Failed to send SMS: {str(e)}")
            PasswordResetCode.objects.filter(user=user, code=code).delete()
            return Response(
                {'detail': 'Failed to send reset code. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(
            {'detail': 'Reset code sent to your phone number.'},
            status=status.HTTP_200_OK
        )


class VerifyPasswordResetCodeView(APIView):
    """
    Verify the password reset code.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from services.sms_service import format_phone_number
        from .models import PasswordResetCode
        
        phone = request.data.get('phone')
        code = request.data.get('code')
        
        if not phone or not code:
            return Response(
                {'detail': 'Phone number and code are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            formatted_phone = format_phone_number(phone)
            user = User.objects.filter(phone=formatted_phone, is_active=True).first()
            if not user:
                return Response(
                    {'detail': 'Invalid phone number.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception:
            return Response(
                {'detail': 'Invalid phone number.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reset_code = PasswordResetCode.objects.get(
                user=user, phone=formatted_phone, code=code, is_used=False
            )
        except PasswordResetCode.DoesNotExist:
            return Response(
                {'detail': 'Invalid reset code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if reset_code.is_expired:
            return Response(
                {'detail': 'Reset code has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {'detail': 'Code verified successfully.'},
            status=status.HTTP_200_OK
        )


class ConfirmPasswordResetView(APIView):
    """
    Confirm password reset with code and new password.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from services.sms_service import format_phone_number
        from .models import PasswordResetCode
        
        phone = request.data.get('phone')
        code = request.data.get('code')
        password = request.data.get('password')
        
        if not all([phone, code, password]):
            return Response(
                {'detail': 'Phone number, code, and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(password) < 8:
            return Response(
                {'detail': 'Password must be at least 8 characters long.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            formatted_phone = format_phone_number(phone)
            user = User.objects.filter(phone=formatted_phone, is_active=True).first()
            if not user:
                return Response(
                    {'detail': 'Invalid phone number.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception:
            return Response(
                {'detail': 'Invalid phone number.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reset_code = PasswordResetCode.objects.get(
                user=user, phone=formatted_phone, code=code, is_used=False
            )
        except PasswordResetCode.DoesNotExist:
            return Response(
                {'detail': 'Invalid reset code.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if reset_code.is_expired:
            return Response(
                {'detail': 'Reset code has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(password)
        user.save()
        reset_code.is_used = True
        reset_code.save()
        PasswordResetCode.objects.filter(user=user, is_used=False).delete()
        
        # Log the password reset
        log_activity(
            user=user,
            action='password_reset',
            description='User reset their password via SMS code',
            request=request
        )
        
        return Response(
            {'detail': 'Password reset successful.'},
            status=status.HTTP_200_OK
        )


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing activity logs.
    Only authenticated admin/staff users can view activity logs.
    """
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Return activity logs for the requested user.
        Users can only see their own logs unless they're admin/staff.
        """
        user_id = self.kwargs.get('user_id')
        
        if not user_id:
            return ActivityLog.objects.none()
        
        # Get the target user
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return ActivityLog.objects.none()
        
        # Admins and staff can view any user's logs
        if self.request.user.is_staff or self.request.user.is_superuser:
            return ActivityLog.objects.filter(user=target_user).order_by('-timestamp')
        
        # Regular users can only see their own logs
        if self.request.user.id == target_user.id:
            return ActivityLog.objects.filter(user=target_user).order_by('-timestamp')
        
        return ActivityLog.objects.none()
