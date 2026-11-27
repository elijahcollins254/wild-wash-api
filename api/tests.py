from unittest.mock import Mock, patch

import requests

from django.test import SimpleTestCase
from django.urls import reverse

from api.settings import _get_ec2_private_ip


class HealthCheckTests(SimpleTestCase):
    def test_root_lists_backend_endpoints(self):
        response = self.client.get(reverse('endpoint-index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'API directory')
        self.assertContains(response, 'href="/orders/"')
        self.assertContains(response, 'href="/users/register/"')
        self.assertContains(response, 'href="/health/"')

    def test_health_path_returns_success(self):
        response = self.client.get(reverse('health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class Ec2PrivateIpTests(SimpleTestCase):
    @patch.dict('os.environ', {'AWS_EC2_METADATA_DISABLED': 'false'})
    @patch('api.settings.requests.get')
    @patch('api.settings.requests.put')
    def test_reads_private_ip_from_imdsv2(self, put, get):
        put.return_value = Mock(text='metadata-token')
        get.return_value = Mock(text='172.31.33.79')

        self.assertEqual(_get_ec2_private_ip(), '172.31.33.79')
        put.assert_called_once_with(
            'http://169.254.169.254/latest/api/token',
            headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
            timeout=1,
        )
        get.assert_called_once_with(
            'http://169.254.169.254/latest/meta-data/local-ipv4',
            headers={'X-aws-ec2-metadata-token': 'metadata-token'},
            timeout=1,
        )

    @patch.dict('os.environ', {'AWS_EC2_METADATA_DISABLED': 'false'})
    @patch('api.settings.requests.put')
    def test_returns_none_when_metadata_is_unavailable(self, put):
        put.side_effect = requests.RequestException('metadata unavailable')

        self.assertIsNone(_get_ec2_private_ip())

    @patch.dict('os.environ', {'AWS_EC2_METADATA_DISABLED': 'false'})
    @patch('api.settings.requests.get')
    @patch('api.settings.requests.put')
    def test_rejects_invalid_metadata_ip(self, put, get):
        put.return_value = Mock(text='metadata-token')
        get.return_value = Mock(text='not-an-ip')

        self.assertIsNone(_get_ec2_private_ip())
