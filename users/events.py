import asyncio
import json

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model


USER_COUNT_GROUP = 'public-user-count'


def encode_user_count(count):
    return f'event: trusted_user_count\ndata: {json.dumps({"count": count})}\n\n'


@database_sync_to_async
def get_trusted_user_count():
    return get_user_model().objects.count()


async def trusted_user_count_stream():
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    channel_name = await channel_layer.new_channel('user-count')
    await channel_layer.group_add(USER_COUNT_GROUP, channel_name)

    try:
        yield encode_user_count(await get_trusted_user_count())

        while True:
            try:
                event = await asyncio.wait_for(
                    channel_layer.receive(channel_name),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                yield ': keep-alive\n\n'
                continue

            if event.get('type') == 'users.count_changed':
                user_count = event.get('user_count')
                if isinstance(user_count, int) and not isinstance(user_count, bool) and user_count >= 0:
                    yield encode_user_count(user_count)
    finally:
        await channel_layer.group_discard(USER_COUNT_GROUP, channel_name)
