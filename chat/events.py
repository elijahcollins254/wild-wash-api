import asyncio
import json

from channels.layers import get_channel_layer

from .models import SupportMessage


def support_customer_group(customer_id):
    return f'support-chat-{customer_id}'


def serialize_support_message(message):
    return {
        'id': message.id,
        'body': message.body,
        'is_from_support': message.is_from_support,
        'created_at': message.created_at.isoformat(),
    }


def encode_support_event(message_data):
    return (
        f"id: {message_data['id']}\n"
        "event: support_message\n"
        f"data: {json.dumps(message_data)}\n\n"
    )


async def support_message_stream(customer_id, after_message_id):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    channel_name = await channel_layer.new_channel('support-chat')
    group_name = support_customer_group(customer_id)
    await channel_layer.group_add(group_name, channel_name)
    last_message_id = after_message_id

    try:
        missed_messages = SupportMessage.objects.filter(
            conversation__customer_id=customer_id,
            is_from_support=True,
            id__gt=after_message_id,
        ).order_by('id')
        async for message in missed_messages.aiterator():
            if message.id > last_message_id:
                last_message_id = message.id
                yield encode_support_event(serialize_support_message(message))

        while True:
            try:
                event = await asyncio.wait_for(
                    channel_layer.receive(channel_name),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                yield ': keep-alive\n\n'
                continue

            message_data = event.get('message')
            if (
                event.get('type') == 'support.message'
                and isinstance(message_data, dict)
                and isinstance(message_data.get('id'), int)
                and message_data['id'] > last_message_id
            ):
                last_message_id = message_data['id']
                yield encode_support_event(message_data)
    finally:
        await channel_layer.group_discard(group_name, channel_name)
