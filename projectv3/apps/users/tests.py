from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class UserListTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='secret1234',
        )
        User.objects.create_user(
            username='real_user',
            email='real@example.com',
            password='secret1234',
        )
        User.objects.create_user(
            username='techfix_sample_01',
            email='sample@example.invalid',
            password='secret1234',
        )
        self.client.force_login(self.admin)

    def test_sample_reviewer_accounts_are_hidden_from_user_list(self):
        response = self.client.get(reverse('users:user_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'real_user')
        self.assertNotContains(response, 'techfix_sample_01')

    def test_sample_reviewer_accounts_are_hidden_from_ajax_list(self):
        response = self.client.get(reverse('users:user_list_ajax'))

        self.assertEqual(response.status_code, 200)
        usernames = [row['username'] for row in response.json()['data']]
        self.assertIn('real_user', usernames)
        self.assertNotIn('techfix_sample_01', usernames)
