from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import SupportConversation, SupportMessage

User = get_user_model()


class SupportChatApiTests(TestCase):
    def setUp(self):
        suffix = uuid4().hex
        self.customer = User.objects.create_user(
            username=f'chat_customer_{suffix}',
            password='testpass123',
        )
        self.other_customer = User.objects.create_user(
            username=f'other_chat_customer_{suffix}',
            password='testpass123',
        )
        self.client = APIClient()

    def test_chat_requires_authentication(self):
        self.assertEqual(self.client.get('/chat/').status_code, 401)
        self.assertEqual(
            self.client.post('/chat/', {'body': 'Hello'}).status_code,
            401,
        )
        self.assertEqual(self.client.get('/chat/unread-count/').status_code, 401)

    def test_customer_can_send_and_read_only_their_own_messages(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            '/chat/',
            {'body': '  I need help  ', 'is_from_support': True},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['body'], 'I need help')
        self.assertFalse(response.data['is_from_support'])

        other_conversation = SupportConversation.objects.create(
            customer=self.other_customer,
        )
        SupportMessage.objects.create(
            conversation=other_conversation,
            sender=self.other_customer,
            body='Private message',
        )

        response = self.client.get('/chat/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['body'], 'I need help')

    def test_customer_can_read_support_replies(self):
        conversation = SupportConversation.objects.create(customer=self.customer)
        support_user = User.objects.create_user(
            username=f'chat_support_{uuid4().hex}',
            password='testpass123',
            is_staff=True,
        )
        SupportMessage.objects.create(
            conversation=conversation,
            sender=support_user,
            is_from_support=True,
            body='How can I help?',
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.get('/chat/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['body'], 'How can I help?')
        self.assertTrue(response.data[0]['is_from_support'])

    def test_unread_count_counts_only_support_replies_for_customer(self):
        conversation = SupportConversation.objects.create(customer=self.customer)
        other_conversation = SupportConversation.objects.create(
            customer=self.other_customer,
        )
        SupportMessage.objects.create(
            conversation=conversation,
            sender=self.customer,
            body='Customer message',
        )
        SupportMessage.objects.create(
            conversation=conversation,
            body='First support reply',
            is_from_support=True,
        )
        SupportMessage.objects.create(
            conversation=conversation,
            body='Second support reply',
            is_from_support=True,
        )
        SupportMessage.objects.create(
            conversation=other_conversation,
            body='Other customer reply',
            is_from_support=True,
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.get('/chat/unread-count/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 2)

    def test_opening_chat_marks_support_replies_read(self):
        conversation = SupportConversation.objects.create(customer=self.customer)
        support_message = SupportMessage.objects.create(
            conversation=conversation,
            body='How can I help?',
            is_from_support=True,
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.get('/chat/')

        self.assertEqual(response.status_code, 200)
        support_message.refresh_from_db()
        self.assertIsNotNone(support_message.customer_read_at)
        self.assertEqual(
            self.client.get('/chat/unread-count/').data['unread_count'],
            0,
        )

    def test_customer_messages_are_not_marked_as_support_read(self):
        conversation = SupportConversation.objects.create(customer=self.customer)
        customer_message = SupportMessage.objects.create(
            conversation=conversation,
            sender=self.customer,
            body='I need help',
        )
        self.client.force_authenticate(user=self.customer)

        self.client.get('/chat/')

        customer_message.refresh_from_db()
        self.assertIsNone(customer_message.customer_read_at)

    def test_blank_message_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post('/chat/', {'body': '   '})

        self.assertEqual(response.status_code, 400)
