# orders/urls.py

from django.urls import path
from .views import (
    OrderListCreateView, 
    OrderUpdateView, 
    RiderOrderListView,
    RequestedOrdersListView,
    StaffCreateOrderView,
    OrderPaymentStatusView,
    RequestDeliveryView,
    AssignOrderLocationView,
)

urlpatterns = [
    path('', OrderListCreateView.as_view(), name='order-list'),
    path('assign-location/', AssignOrderLocationView.as_view(), name='order-assign-location'),
    path('update/', OrderUpdateView.as_view(), name='order-update'),
    path('rider/', RiderOrderListView.as_view(), name='rider-order-list'),
    path('requested/', RequestedOrdersListView.as_view(), name='requested-orders-list'),
    path('create/', StaffCreateOrderView.as_view(), name='staff-create-order'),
    path('<str:code>/payment-status/', OrderPaymentStatusView.as_view(), name='order-payment-status'),
    path('<str:code>/request-delivery/', RequestDeliveryView.as_view(), name='request-delivery'),
]
