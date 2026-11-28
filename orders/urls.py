# orders/urls.py

from django.urls import path
from .views import (
    OrderListCreateView, 
    OrderUpdateView, 
    RiderOrderListView,
    RequestedOrdersListView,
    StaffCreateOrderView,
    OrderPaymentStatusView,
    OrderReviewView,
    RequestDeliveryView,
    AssignOrderLocationView,
    WasherAnalyticsView,
    OrderEventsView,
    PartnerCreateOrderView,
    PartnerOrderTrackingView,
)

urlpatterns = [
    path('', OrderListCreateView.as_view(), name='order-list'),
    path('events/', OrderEventsView.as_view(), name='order-events'),
    path('washer-analytics/', WasherAnalyticsView.as_view(), name='washer-analytics'),
    path('assign-location/', AssignOrderLocationView.as_view(), name='order-assign-location'),
    path('update/', OrderUpdateView.as_view(), name='order-update'),
    path('rider/', RiderOrderListView.as_view(), name='rider-order-list'),
    path('requested/', RequestedOrdersListView.as_view(), name='requested-orders-list'),
    path('create/', StaffCreateOrderView.as_view(), name='staff-create-order'),
    path('partner-create/', PartnerCreateOrderView.as_view(), name='partner-create-order'),
    path('<str:code>/track/', PartnerOrderTrackingView.as_view(), name='partner-order-tracking'),
    path('<str:code>/payment-status/', OrderPaymentStatusView.as_view(), name='order-payment-status'),
    path('<str:code>/rating/', OrderReviewView.as_view(), name='order-rating'),
    path('<str:code>/review/', OrderReviewView.as_view(), name='order-review'),
    path('<str:code>/request-delivery/', RequestDeliveryView.as_view(), name='request-delivery'),
]
