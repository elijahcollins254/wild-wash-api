import asyncio
import json

from channels.layers import get_channel_layer


def customer_orders_group(user_id):
    return f'orders-customer-{user_id}'


def staff_orders_group(location_id):
    return f'orders-staff-location-{location_id}'


def order_event_groups(order):
    groups = {'orders-staff-all', 'orders-riders'}
    if order.user_id:
        groups.add(customer_orders_group(order.user_id))
    if order.service_location_id:
        groups.add(staff_orders_group(order.service_location_id))
    return groups


def user_order_event_groups(user):
    if user.role == 'rider':
        return ['orders-riders']
    if user.is_superuser:
        return ['orders-staff-all']
    if user.is_staff or user.role in {'staff', 'washer', 'folder', 'fumigator'}:
        if user.service_location_id:
            return [staff_orders_group(user.service_location_id)]
        return []
    return [customer_orders_group(user.pk)]


def encode_order_event(order_id=None):
    return (
        'event: order_update\n'
        f'data: {json.dumps({"order_id": order_id})}\n\n'
    )


async def order_event_stream(groups):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    channel_name = await channel_layer.new_channel('orders')
    for group in groups:
        await channel_layer.group_add(group, channel_name)

    try:
        yield encode_order_event()
        while True:
            try:
                event = await asyncio.wait_for(
                    channel_layer.receive(channel_name),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                yield ': keep-alive\n\n'
                continue

            if event.get('type') == 'orders.changed':
                yield encode_order_event(event.get('order_id'))
    finally:
        for group in groups:
            await channel_layer.group_discard(group, channel_name)
