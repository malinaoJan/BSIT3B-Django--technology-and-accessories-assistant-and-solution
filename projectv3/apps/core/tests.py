import base64
import json
import os
import tempfile
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .assistant import build_answer
from .gemini import (
    _attachment_parts,
    _build_prompt,
    _extract_text,
    _parse_gemini_data,
    enhance_answer,
)
from .models import Accessory, Category, Product, Review, Solution
from .views import CHAT_SESSION_KEY, _context_query
from .management.commands.import_online_ratings import (
    _candidate_conflicts,
    pick_candidate,
    product_search_variants,
)
from apps.users.models import PhoneProfile


def ai_answer(**overrides):
    answer = {
        'kind': 'fallback',
        'badge': 'AI answer',
        'title': 'Charging help',
        'summary': 'Check the cable and charger.',
        'first_step': '',
        'steps': ['Try another cable.', 'Try another wall outlet.'],
        'steps_title': 'Step-by-step process',
        'difficulty': 'Easy',
        'category': '',
        'product': None,
        'accessory': None,
        'video_url': '',
        'safety': '',
        'suggestions': [],
        'ai': True,
        'notice': '',
    }
    answer.update(overrides)
    return answer


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, reverse('assistant_chat'))
        self.assertContains(response, 'data-csrf-token')
        self.assertContains(response, 'chat-thread')
        self.assertContains(response, 'data-chat-retry')
        self.assertContains(response, 'Try again')
        self.assertContains(response, 'Assistant')
        self.assertNotContains(response, '<body class="chat-active">')
        self.assertContains(response, 'No recent activity yet')
        sidebar = response.content.decode().split(
            '<aside class="app-sidebar"', 1
        )[1].split('</aside>', 1)[0]
        for label in (
            'Images', 'Plugins', 'Codex', 'Projects', 'TechFix catalog',
            'Repair guides', 'Info records', 'Manage users', 'Admin panel',
        ):
            self.assertNotIn(label, sidebar)

    def test_administrator_and_logout_render_in_topbar(self):
        user = get_user_model().objects.create_superuser(
            username='site-admin', email='admin@example.com', password='secret1234'
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'class="mobile-topbar auth-topbar"')
        self.assertContains(response, 'Administrator')
        self.assertContains(response, 'Log out')
        self.assertContains(response, 'action="%s"' % reverse('logout'))
        self.assertNotContains(response, 'class="sidebar-user"')

    def test_guest_can_open_home_and_browse_links(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('assistant_chat'))
        self.assertContains(response, 'id="appSidebar"')
        self.assertContains(response, 'guest-top-actions')
        self.assertContains(response, 'Guest mode')
        self.assertContains(response, 'Create account')
        self.assertContains(response, 'id="techfix-search-form"')
        self.assertNotContains(response, 'Answers you can see and play with.')
        self.assertNotContains(response, 'guest-sidebar-actions')
        self.assertNotContains(response, 'Scheduled')
        sidebar = response.content.decode().split(
            '<aside class="app-sidebar"', 1
        )[1].split('</aside>', 1)[0]
        for label in ('Products', 'Accessories', 'TechFix catalog', 'Repair guides'):
            self.assertNotIn(label, sidebar)
        self.assertNotIn(reverse('product_list'), sidebar)
        self.assertNotIn(reverse('accessory_list'), sidebar)
        self.assertNotIn('Recents', sidebar)

    def test_login_and_register_pages_have_close_button(self):
        for route in ('login', 'register'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-smart-back')
                self.assertContains(response, 'auth-close')
                self.assertContains(response, 'aria-label="Close"')
                self.assertNotContains(response, '>Back</a>')

    def test_login_accepts_registered_phone_number(self):
        user = get_user_model().objects.create_user(
            username='phone-user',
            email='phone-user@example.com',
            password='SecurePassword123!',
        )
        PhoneProfile.objects.create(user=user, phone_number='+639171234567')

        response = self.client.post(reverse('login'), {
            'identifier': '+63 (917) 123-4567',
            'password': 'SecurePassword123!',
        })

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_registration_saves_optional_international_phone_number(self):
        response = self.client.post(reverse('register'), {
            'username': 'new-phone-user',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new-phone-user@example.com',
            'phone_number': '+63 (917) 123-4567',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        })

        self.assertRedirects(response, reverse('dashboard'))
        user = get_user_model().objects.get(username='new-phone-user')
        self.assertEqual(user.phone_profile.phone_number, '+639171234567')

    @override_settings(GOOGLE_OAUTH_ENABLED=False)
    def test_login_page_explains_google_setup_when_credentials_are_missing(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'Username, email, or phone number')
        self.assertContains(response, 'Continue with Google')
        self.assertContains(response, 'GOOGLE_OAUTH_CLIENT_ID')
        self.assertContains(response, 'googleSetupNotice')
        self.assertContains(response, 'Continue with phone')
        self.assertNotContains(response, 'Continue with Apple')

    @override_settings(
        GOOGLE_OAUTH_ENABLED=True,
        SOCIALACCOUNT_PROVIDERS={
            'google': {
                'APPS': [{
                    'client_id': 'test-client-id',
                    'secret': 'test-client-secret',
                    'key': '',
                }],
            },
        },
    )
    def test_login_page_shows_google_sign_in_when_configured(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'Continue with Google')
        self.assertNotContains(response, 'Google sign-in setup required')

    def test_recent_activities_persist_for_each_account(self):
        first_user = get_user_model().objects.create_user(
            username='first-user', password='secret1234'
        )
        get_user_model().objects.create_user(
            username='second-user', password='secret1234'
        )
        category = Category.objects.create(name='Recent activity laptops')
        product = Product.objects.create(
            name='Saved Recent Laptop',
            category=category,
            brand='TestBrand',
            description='A laptop for recent activity testing.',
            price='999.00',
            stock_quantity=1,
        )

        self.client.force_login(first_user)
        self.client.get(reverse('product_detail', args=[product.pk]))
        self.client.post(reverse('logout'))
        self.client.post(
            reverse('login'),
            {'username': 'first-user', 'password': 'secret1234'},
        )

        response = self.client.get(reverse('dashboard'))
        sidebar = response.content.decode().split(
            '<div class="sidebar-nav" id="recentActivities"', 1
        )[1].split('</div>', 1)[0]
        self.assertIn('Product: Saved Recent Laptop', sidebar)

        self.client.post(reverse('logout'))
        self.client.post(
            reverse('login'),
            {'username': 'second-user', 'password': 'secret1234'},
        )
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Product: Saved Recent Laptop')

    def test_logout_returns_user_to_guest_dashboard(self):
        user = get_user_model().objects.create_user(
            username='logout-user', password='secret1234'
        )
        self.client.force_login(user)

        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_home_renders_existing_chat_history(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')
        self.client.force_login(user)
        session = self.client.session
        session[CHAT_SESSION_KEY] = [
            {'role': 'user', 'text': 'My phone will not charge'},
            {'role': 'assistant', 'answer': ai_answer()},
        ]
        session.save()

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'My phone will not charge')
        self.assertContains(response, 'Check the cable and charger.')
        self.assertContains(response, '<body class="chat-active">')

    @patch('apps.core.views._create_chat_answer', return_value=None)
    def test_legacy_query_redirects_to_chat_anchor(self, mocked_answer):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(
            reverse('dashboard') + '?q=My+phone+will+not+charge'
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard') + '#techfix')
        mocked_answer.assert_called_once_with('My phone will not charge', [])

    @patch('apps.core.views._create_chat_answer')
    def test_legacy_query_stores_chat_turn(self, mocked_answer):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')
        self.client.force_login(user)
        mocked_answer.return_value = ai_answer()

        response = self.client.get(
            reverse('dashboard') + '?q=My+phone+will+not+charge'
        )

        self.assertEqual(response.status_code, 302)
        history = self.client.session[CHAT_SESSION_KEY]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['text'], 'My phone will not charge')
        self.assertEqual(
            history[1]['answer']['summary'], 'Check the cable and charger.'
        )

    def test_new_chat_clears_session_history(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')
        self.client.force_login(user)
        session = self.client.session
        session[CHAT_SESSION_KEY] = [
            {'role': 'user', 'text': 'My phone will not charge'},
            {'role': 'assistant', 'answer': ai_answer()},
        ]
        session.save()

        response = self.client.get(reverse('dashboard') + '?new=1')

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(CHAT_SESSION_KEY, self.client.session)


class ScheduledAssistantViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='scheduled', password='secret1234'
        )
        self.client.force_login(self.user)

    def test_scheduled_page_renders_assistant_ui(self):
        response = self.client.get(reverse('scheduled_assistant'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'scheduled.html')
        self.assertContains(response, 'TECHFIX AI Assistant')
        self.assertContains(response, 'Your smart technology and accessories assistant')
        self.assertContains(response, 'Recommended')
        for title in (
            'Technology Troubleshooting',
            'Find the Right Accessories',
            'Gadget Recommendations',
            'Device Compatibility',
            'Quick Tech Solutions',
        ):
            self.assertContains(response, title)
        self.assertContains(response, reverse('assistant_chat'))
        self.assertContains(response, 'data-csrf-token')
        self.assertContains(response, 'data-chat-retry')
        self.assertContains(response, 'Try again')
        self.assertContains(response, 'data-sa-prompt')
        self.assertEqual(response.content.decode().count('class="scheduled-action-use"'), 5)
        self.assertContains(response, "sendMessage(button.getAttribute('data-sa-prompt') || '')")
        self.assertContains(response, 'scheduledComposer')
        self.assertNotContains(response, 'scheduled-assistant-page has-conversation')

        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(
            dashboard,
            'href="%s"' % reverse('scheduled_assistant'),
        )

    def test_scheduled_page_renders_existing_chat_history(self):
        session = self.client.session
        session[CHAT_SESSION_KEY] = [
            {'role': 'user', 'text': 'My phone will not charge'},
            {'role': 'assistant', 'answer': ai_answer()},
        ]
        session.save()

        response = self.client.get(reverse('scheduled_assistant'))

        self.assertContains(response, 'My phone will not charge')
        self.assertContains(response, 'Check the cable and charger.')
        self.assertContains(response, 'scheduled-assistant-page has-conversation')
        self.assertContains(response, 'id="scheduledRecommended" hidden')

    def test_scheduled_page_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse('scheduled_assistant'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_new_chat_clears_session_history(self):
        session = self.client.session
        session[CHAT_SESSION_KEY] = [
            {'role': 'user', 'text': 'My phone will not charge'},
            {'role': 'assistant', 'answer': ai_answer()},
        ]
        session.save()

        response = self.client.get(reverse('scheduled_assistant') + '?new=1')

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(CHAT_SESSION_KEY, self.client.session)


class LibraryViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='library', password='secret1234'
        )
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Laptops')
        Product.objects.create(
            name='Test Laptop',
            category=self.category,
            brand='TestBrand',
            description='A test laptop.',
            specifications='RAM: 8GB',
            price='999.00',
            stock_quantity=1,
        )
        Product.objects.create(
            name='Other Laptop',
            category=self.category,
            brand='OtherBrand',
            description='Another test laptop.',
            price='499.00',
            stock_quantity=1,
        )

    def test_guest_can_browse_catalog_pages(self):
        self.client.logout()
        routes = (
            reverse('product_list'),
            reverse('product_detail', args=[Product.objects.first().pk]),
            reverse('accessory_list'),
            reverse('solution_list'),
            reverse('brand_list'),
            reverse('brand_detail', args=['TestBrand']),
        )

        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def test_product_detail_back_button_returns_to_brand_folder(self):
        product = Product.objects.first()
        response = self.client.get(
            reverse('product_detail', args=[product.pk])
        )

        self.assertContains(response, 'data-smart-back')
        self.assertContains(
            response,
            'href="%s"' % reverse('brand_detail', args=[product.brand]),
        )
        self.assertNotContains(response, 'All products')

    def test_product_and_accessory_prices_use_thousands_separators(self):
        product = Product.objects.create(
            name='Premium Laptop',
            category=self.category,
            brand='TestBrand',
            description='A premium laptop.',
            price='1299.00',
            stock_quantity=1,
        )
        accessory = Accessory.objects.create(
            name='Premium Dock',
            category=self.category,
            brand='TestBrand',
            description='A premium dock.',
            price='2345.67',
            stock_quantity=1,
        )
        accessory.compatible_products.add(product)

        product_list = self.client.get(reverse('product_list'))
        self.assertContains(product_list, '₱1,299.00')
        product_detail = self.client.get(
            reverse('product_detail', args=[product.pk])
        )
        self.assertContains(product_detail, '₱1,299.00')
        self.assertContains(product_detail, '₱2,345.67')

        accessory_list = self.client.get(reverse('accessory_list'))
        self.assertContains(accessory_list, '₱2,345.67')
        accessory_detail = self.client.get(
            reverse('accessory_detail', args=[accessory.pk])
        )
        self.assertContains(accessory_detail, '₱2,345.67')
        self.assertContains(accessory_detail, '₱1,299.00')

    def test_unpriced_catalog_items_show_official_source_without_zero_price(self):
        product = Product.objects.create(
            name='Official Product Without Listed Price',
            category=self.category,
            brand='TestBrand',
            description='Product with verified official source.',
            source_url='https://www.example.com/product',
        )
        accessory = Accessory.objects.create(
            name='Official Accessory Without Listed Price',
            category=self.category,
            brand='TestBrand',
            description='Accessory with verified official source.',
            source_url='https://www.example.com/accessory',
        )

        product_detail = self.client.get(
            reverse('product_detail', args=[product.pk])
        )
        accessory_detail = self.client.get(
            reverse('accessory_detail', args=[accessory.pk])
        )

        self.assertContains(product_detail, 'https://www.example.com/product')
        self.assertContains(product_detail, 'Official product page')
        self.assertNotContains(product_detail, '₱0.00')
        self.assertNotContains(product_detail, '>Price</td>')
        self.assertNotContains(product_detail, 'Out of stock')
        self.assertContains(accessory_detail, 'https://www.example.com/accessory')
        self.assertContains(accessory_detail, 'Official product page')
        self.assertNotContains(accessory_detail, '₱0.00')
        self.assertNotContains(accessory_detail, '>Price</td>')
        self.assertNotContains(accessory_detail, 'Out of stock')

    def test_brand_detail_back_button_returns_to_brands(self):
        response = self.client.get(reverse('brand_detail', args=['TestBrand']))

        self.assertContains(response, 'data-smart-back')
        self.assertContains(
            response,
            'href="%s"' % reverse('brand_list'),
        )
        self.assertNotContains(response, 'All brands')
        self.assertNotContains(response, '>Dashboard</a>')

    def test_library_page_renders_new_layout(self):
        response = self.client.get(reverse('brand_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/brands.html')
        self.assertContains(response, 'Search library')
        for tab in ('suggested', 'favorites', 'folders', 'images'):
            self.assertContains(response, 'data-library-tab="%s"' % tab)
        self.assertNotContains(response, 'data-library-tab="all"')
        self.assertNotContains(response, 'library-new')
        self.assertContains(response, 'TestBrand')
        self.assertContains(response, 'data-library-favorite="TestBrand"')

    def test_recent_page_activity_is_shown_to_signed_in_user(self):
        product = Product.objects.first()
        self.client.get(reverse('product_detail', args=[product.pk]))
        self.client.get(reverse('brand_detail', args=['TestBrand']))

        response = self.client.get(reverse('dashboard'))
        sidebar = response.content.decode().split(
            '<div class="sidebar-nav" id="recentActivities"', 1
        )[1].split('</div>', 1)[0]

        self.assertIn('Brand: TestBrand', sidebar)
        self.assertIn('Product: ' + product.name, sidebar)
        self.assertLess(
            sidebar.index('Brand: TestBrand'),
            sidebar.index('Product: ' + product.name),
        )

    def test_library_search_filters_folders(self):
        response = self.client.get(reverse('brand_list'), {'q': 'TestBrand'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TestBrand')
        self.assertNotContains(response, 'OtherBrand')
        self.assertContains(response, 'data-initial-tab="suggested"')

    def test_library_search_empty_state(self):
        response = self.client.get(reverse('brand_list'), {'q': 'MissingBrand'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No folders match')
        self.assertContains(response, 'Clear search')

    def test_library_search_images_ignore_description_only_matches(self):
        Product.objects.create(
            name='Sony Camera Phone',
            category=self.category,
            brand='Sony',
            description='A phone.',
            price='599.00',
            stock_quantity=1,
            image='products/sony-camera-phone.jpg',
        )
        Product.objects.create(
            name='Unrelated Camera Phone',
            category=self.category,
            brand='OtherBrand',
            description='Uses a Sony image sensor.',
            price='399.00',
            stock_quantity=1,
            image='products/unrelated-camera-phone.jpg',
        )

        response = self.client.get(reverse('brand_list'), {'q': 'Sony'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sony Camera Phone')
        self.assertNotContains(response, 'Unrelated Camera Phone')

    def test_library_images_show_all_products_and_accessories(self):
        Product.objects.create(
            name='Old Catalog Laptop',
            category=self.category,
            brand='OldBrand',
            description='An older catalog laptop.',
            price='399.00',
            stock_quantity=1,
            image='products/old-catalog-laptop.jpg',
        )
        Product.objects.create(
            name='Latest Laptop',
            category=self.category,
            brand='NewBrand',
            description='A current laptop.',
            price='1299.00',
            stock_quantity=1,
            image='products/latest-laptop.jpg',
        )
        Product.objects.create(
            name='Latest Travel Backpack',
            category=self.category,
            brand='NewBrand',
            description='A current product backpack.',
            price='89.00',
            stock_quantity=1,
            image='products/latest-travel-backpack.jpg',
        )
        Accessory.objects.create(
            name='Old Catalog Charger',
            category=self.category,
            brand='OldBrand',
            description='An older catalog charger.',
            price='19.00',
            stock_quantity=1,
            image='accessories/old-catalog-charger.jpg',
        )
        Accessory.objects.create(
            name='Latest USB-C Charger',
            category=self.category,
            brand='NewBrand',
            description='A current charger.',
            price='49.00',
            stock_quantity=1,
            image='accessories/latest-usb-c-charger.jpg',
        )
        Accessory.objects.create(
            name='Latest Laptop Backpack',
            category=self.category,
            brand='NewBrand',
            description='A current laptop backpack.',
            price='89.00',
            stock_quantity=1,
            image='accessories/latest-laptop-backpack.jpg',
        )
        Accessory.objects.create(
            name='Latest Camera Bag',
            category=self.category,
            brand='NewBrand',
            description='A current camera bag.',
            price='69.00',
            stock_quantity=1,
            image='accessories/latest-camera-bag.jpg',
        )
        Accessory.objects.create(
            name='Laptop Sleeve Case for Latest Laptop',
            category=self.category,
            brand='NewBrand',
            description='A current laptop sleeve.',
            price='59.00',
            stock_quantity=1,
            image='accessories/latest-laptop-sleeve.jpg',
        )
        Product.objects.create(
            name='No Photo Product',
            category=self.category,
            brand='NewBrand',
            description='A product without an uploaded image.',
            price='199.00',
            stock_quantity=1,
        )
        Accessory.objects.create(
            name='No Photo Accessory',
            category=self.category,
            brand='NewBrand',
            description='An accessory without an uploaded image.',
            price='9.00',
            stock_quantity=1,
        )
        for index in range(13):
            Product.objects.create(
                name='Additional Product %s' % index,
                category=self.category,
                brand='NewBrand',
                description='An additional catalog product.',
                price='199.00',
                stock_quantity=1,
                image='products/additional-product-%s.jpg' % index,
            )
            Accessory.objects.create(
                name='Additional Accessory %s' % index,
                category=self.category,
                brand='NewBrand',
                description='An additional catalog accessory.',
                price='9.00',
                stock_quantity=1,
                image='accessories/additional-accessory-%s.jpg' % index,
            )

        response = self.client.get(reverse('brand_list'))

        self.assertEqual(response.status_code, 200)
        image_names = [item['name'] for item in response.context['image_items']]
        self.assertIn('Latest Laptop', image_names)
        self.assertIn('Old Catalog Laptop', image_names)
        self.assertIn('Latest Travel Backpack', image_names)
        self.assertIn('Latest USB-C Charger', image_names)
        self.assertIn('Old Catalog Charger', image_names)
        self.assertIn('Latest Laptop Backpack', image_names)
        self.assertIn('Latest Camera Bag', image_names)
        self.assertIn('Laptop Sleeve Case for Latest Laptop', image_names)
        self.assertIn('No Photo Product', image_names)
        self.assertIn('No Photo Accessory', image_names)
        self.assertEqual(
            sum(item['kind'] == 'Product' for item in response.context['image_items']),
            19,
        )
        self.assertEqual(
            sum(item['kind'] == 'Accessory' for item in response.context['image_items']),
            19,
        )
        self.assertContains(response, 'library-image-placeholder')

    def test_library_images_put_latest_iphone_and_samsung_photos_first(self):
        featured_products = (
            ('Samsung', 'Galaxy S26'),
            ('Samsung', 'Galaxy S26+'),
            ('Apple', 'iPhone 18 Pro'),
            ('Apple', 'iPhone 17e'),
        )
        for index, (brand, name) in enumerate(featured_products):
            Product.objects.create(
                name=name,
                category=self.category,
                brand=brand,
                description='Current official product.',
                image='products/featured-%s.jpg' % index,
            )
        Product.objects.create(
            name='Recent unrelated product',
            category=self.category,
            brand='OtherBrand',
            description='Another catalog product.',
        )

        response = self.client.get(reverse('brand_list'))
        image_items = response.context['image_items']
        self.assertEqual(
            [(item['brand'], item['name']) for item in image_items[:4]],
            list(featured_products),
        )
        rendered = response.content.decode()
        positions = [
            rendered.index('class="library-image-name" title="%s"' % name)
            for _, name in featured_products
        ]
        self.assertEqual(positions, sorted(positions))

    def test_library_images_do_not_feature_products_without_real_photos(self):
        Product.objects.create(
            name='Galaxy S26',
            category=self.category,
            brand='Samsung',
            description='Current official product without a real photo.',
            image='products/old_products_tile_999.jpg',
        )
        Product.objects.create(
            name='Recent unrelated photo product',
            category=self.category,
            brand='OtherBrand',
            description='Another catalog product with a real photo.',
            image='products/recent-unrelated.jpg',
        )

        response = self.client.get(reverse('brand_list'))
        names = [item['name'] for item in response.context['image_items']]
        self.assertLess(
            names.index('Recent unrelated photo product'),
            names.index('Galaxy S26'),
        )

    def test_text_tiles_are_not_rendered_as_product_photos(self):
        product = Product.objects.create(
            name='Tile Product Name',
            category=self.category,
            brand='TestBrand',
            description='Uses a generated text tile.',
            image='products/old_products_tile_999.jpg',
        )
        accessory = Accessory.objects.create(
            name='Tile Accessory Name',
            category=self.category,
            brand='TestBrand',
            description='Uses a generated text tile.',
            image='accessories/old_accessories_tile_999.jpg',
        )

        self.assertFalse(product.has_real_photo)
        self.assertFalse(accessory.has_real_photo)

        library = self.client.get(reverse('brand_list'))
        library_images = {
            (entry['brand'], entry['name']): entry
            for entry in library.context['image_items']
        }
        self.assertEqual(
            library_images[('TestBrand', product.name)]['image_url'],
            '',
        )
        self.assertEqual(
            library_images[('TestBrand', accessory.name)]['image_url'],
            '',
        )
        self.assertContains(library, 'library-image-placeholder')

        for route in (
            reverse('product_list'),
            reverse('brand_detail', args=['TestBrand']),
            reverse('product_detail', args=[product.pk]),
            reverse('accessory_detail', args=[accessory.pk]),
        ):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'old_products_tile_999.jpg')
                self.assertNotContains(response, 'old_accessories_tile_999.jpg')
                self.assertNotContains(response, 'prod-media-name')


class ChatEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', password='secret1234'
        )
        self.client.force_login(self.user)

    def post_message(self, message):
        return self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': message}),
            content_type='application/json',
        )

    @patch('apps.core.views.enhance_answer')
    def test_guest_can_chat(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer()
        self.client.logout()

        response = self.post_message('My phone will not charge')

        self.assertEqual(response.status_code, 200)
        self.assertIn('html', response.json())
        self.assertEqual(response.json()['recent_activities'], [])
        self.assertEqual(len(self.client.session[CHAT_SESSION_KEY]), 2)
        self.assertNotIn('techfix_recent_activity', self.client.session)

    def test_chat_rejects_empty_message(self):
        response = self.post_message('   ')

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_chat_rejects_non_string_message(self):
        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 5}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_chat_rejects_long_message(self):
        response = self.post_message('x' * 1001)

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    @patch('apps.core.views.enhance_answer')
    def test_chat_returns_html_and_stores_history(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer()

        response = self.post_message('My phone will not charge')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('assistant-thread', data['html'])
        self.assertIn('Check the cable and charger.', data['html'])
        self.assertEqual(mocked_enhance.call_args.args[0], 'My phone will not charge')
        self.assertEqual(mocked_enhance.call_args.kwargs['history'], [])

        history = self.client.session[CHAT_SESSION_KEY]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], {'role': 'user', 'text': 'My phone will not charge'})
        self.assertEqual(history[1]['role'], 'assistant')
        self.assertEqual(
            history[1]['answer']['summary'], 'Check the cable and charger.'
        )
        self.assertEqual(
            data['recent_activities'][0]['title'],
            'My phone will not charge',
        )
        self.assertEqual(
            data['recent_activities'][0]['url'],
            reverse('dashboard') + '#techfix',
        )

    @patch('apps.core.views.enhance_answer')
    def test_chat_accepts_file_attachments(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer()

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = SimpleUploadedFile(
                    'phone photo.png',
                    b'fake-image-data',
                    content_type='image/png',
                )
                response = self.client.post(
                    reverse('assistant_chat'),
                    data={
                        'message': 'My phone will not charge',
                        'attachments': upload,
                    },
                )
                stored_files = [
                    name
                    for _, _, files in os.walk(media_root)
                    for name in files
                ]

        self.assertEqual(response.status_code, 200)
        history = self.client.session[CHAT_SESSION_KEY]
        self.assertEqual(history[0]['text'], 'My phone will not charge')
        attachment = history[0]['attachments'][0]
        self.assertEqual(attachment['name'], 'phone_photo.png')
        self.assertTrue(attachment['is_image'])
        self.assertTrue(attachment['url'].startswith('/media/chat_uploads/'))
        self.assertTrue(stored_files)
        mocked_enhance.assert_called_once()
        ai_attachments = mocked_enhance.call_args.kwargs['attachments']
        self.assertEqual(ai_attachments[0]['type'], 'image')
        self.assertEqual(ai_attachments[0]['data'], b'fake-image-data')
        self.assertIn(
            'Attached file: phone_photo.png.',
            response.json()['html'],
        )

    @patch('apps.core.views.enhance_answer')
    def test_chat_answers_attachment_without_text_using_ai(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer(
            title='Charging port damage',
            summary='The photo shows a damaged charging port.',
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = SimpleUploadedFile(
                    'notes.txt', b'hello', content_type='text/plain'
                )
                response = self.client.post(
                    reverse('assistant_chat'),
                    data={'attachments': upload},
                )

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        question = mocked_enhance.call_args.args[0]
        self.assertIn('attached file or photo', question)
        ai_attachments = mocked_enhance.call_args.kwargs['attachments']
        self.assertEqual(ai_attachments[0]['type'], 'text')
        self.assertIn('hello', ai_attachments[0]['text'])
        self.assertIn(
            'The photo shows a damaged charging port.',
            response.json()['html'],
        )
        history = self.client.session[CHAT_SESSION_KEY]
        self.assertEqual(history[0]['text'], '')
        self.assertEqual(history[0]['attachments'][0]['name'], 'notes.txt')

    def test_chat_rejects_unsupported_attachment(self):
        upload = SimpleUploadedFile('malware.exe', b'boom')
        response = self.client.post(
            reverse('assistant_chat'),
            data={'message': 'Open this', 'attachments': upload},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('not a supported file type', response.json()['error'])

    @patch('apps.core.views.record_recent_activity', side_effect=RuntimeError('db down'))
    @patch('apps.core.views.enhance_answer')
    def test_chat_survives_recent_activity_failure(
        self, mocked_enhance, mocked_record
    ):
        mocked_enhance.return_value = ai_answer()

        with self.assertLogs('apps.core.views', level='ERROR'):
            response = self.post_message('My phone will not charge')

        self.assertEqual(response.status_code, 200)
        self.assertIn('html', response.json())
        mocked_record.assert_called_once()

    @patch('apps.core.views.enhance_answer')
    def test_follow_up_receives_previous_history(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer()
        self.post_message('My phone will not charge')

        mocked_enhance.return_value = ai_answer(
            summary='A follow-up answer about battery drain.'
        )
        response = self.post_message('The battery still drains fast')

        self.assertEqual(response.status_code, 200)
        history_arg = mocked_enhance.call_args.kwargs['history']
        self.assertEqual(len(history_arg), 2)
        self.assertEqual(history_arg[0]['text'], 'My phone will not charge')
        self.assertEqual(history_arg[1]['role'], 'assistant')

    def test_chat_rejects_invalid_json(self):
        response = self.client.post(
            reverse('assistant_chat'),
            data='{not-json',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    @patch('apps.core.views.enhance_answer')
    def test_chat_accepts_csrf_header(self, mocked_enhance):
        from django.test import Client

        mocked_enhance.return_value = ai_answer()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        page = client.get(reverse('dashboard'))
        token = page.cookies['csrftoken'].value

        response = client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'My phone will not charge'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('html', response.json())

    @patch('apps.core.views.enhance_answer')
    def test_general_tech_question_uses_ai(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer(
            kind='answer',
            title='SSD vs HDD',
            summary=(
                'An SSD uses flash memory and has no moving parts, while an HDD '
                'uses spinning magnetic platters.'
            ),
            steps=[],
            steps_title='',
            difficulty='',
        )

        response = self.post_message(
            'What is the difference between SSD and HDD?'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mocked_enhance.call_args.args[0],
            'What is the difference between SSD and HDD?',
        )
        html = response.json()['html']
        self.assertIn('SSD vs HDD', html)
        self.assertIn('An SSD uses flash memory', html)
        self.assertNotIn('No exact match', html)
        self.assertNotIn('Troubleshooting guide', html)

    @patch('apps.core.gemini.ask_gemini')
    def test_off_topic_question_gets_techfix_refusal(self, mocked_ask):
        mocked_ask.return_value = {
            'is_tech': False,
            'title': '',
            'summary': 'I focus on technology and gadget questions.',
            'steps': [],
            'difficulty': '',
            'safety': '',
        }

        response = self.post_message('What is the weather tomorrow?')

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('TechFix only', html)
        self.assertIn('I focus on technology and gadget questions.', html)
        self.assertNotIn('No exact match', html)

    @patch('apps.core.views.enhance_answer')
    def test_product_answer_renders_catalog_details(self, mocked_enhance):
        self.client.logout()
        from .models import Category, Product

        category = Category.objects.create(name='Phones')
        product = Product.objects.create(
            name='Test Phone',
            category=category,
            brand='TestBrand',
            description='A test phone.',
            specifications='RAM: 8GB, Storage: 128GB',
            price='1499.99',
            stock_quantity=3,
            image='products/test-phone.jpg',
        )
        mocked_enhance.return_value = ai_answer(
            kind='product',
            title=product.name,
            summary='Product summary',
            product=product,
            suggestions=['How do I reset it?'],
        )

        response = self.post_message('Tell me about Test Phone')

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        html = response.json()['html']
        self.assertIn('Product summary', html)
        self.assertIn('TestBrand', html)
        self.assertIn('₱1,499.99', html)
        self.assertNotIn('$1,499.99', html)
        self.assertIn('3 available', html)
        self.assertIn('RAM: 8GB', html)
        self.assertIn('View product', html)
        self.assertIn('/media/products/test-phone.jpg', html)
        self.assertIn('Products mentioned in this answer', html)
        self.assertEqual(
            html.count('class="assistant-result assistant-mentioned-product"'),
            1,
        )
        self.assertIn('data-chat-prompt="How do I reset it?"', html)

    @patch('apps.core.views.enhance_answer', return_value=None)
    def test_product_search_results_show_photos_and_placeholders(
        self, mocked_enhance
    ):
        self.client.logout()
        category = Category.objects.create(name='Smartphones')
        Product.objects.create(
            name='Phone with photo',
            category=category,
            brand='PhotoBrand',
            description='A phone with a catalog photo.',
            price='249.99',
            image='products/phone-with-photo.jpg',
        )
        Product.objects.create(
            name='Phone without photo',
            category=category,
            brand='PlaceholderBrand',
            description='A phone using the catalog placeholder.',
        )

        response = self.post_message('Show me phones')

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('assistant-result-photo', html)
        self.assertIn('/media/products/phone-with-photo.jpg', html)
        self.assertIn('assistant-result-icon', html)
        self.assertIn('assistant-result-price', html)
        self.assertIn('View details', html)
        self.assertIn('Phone without photo', html)


class StrictAssistantResultsTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Smartphones')
        self.iphone_17 = Product.objects.create(
            name='iPhone 17',
            category=self.category,
            brand='Apple',
            description='Compact iPhone 17.',
            price='799.00',
            stock_quantity=4,
        )
        self.iphone_pro_max = Product.objects.create(
            name='iPhone 17 Pro Max',
            category=self.category,
            brand='Apple',
            description='Large iPhone 17 Pro Max.',
            price='1199.00',
            stock_quantity=2,
        )
        self.samsung_ultra = Product.objects.create(
            name='Samsung Galaxy S25 Ultra',
            category=self.category,
            brand='Samsung',
            description='Samsung flagship.',
            price='1299.00',
            stock_quantity=3,
        )
        self.samsung_fe = Product.objects.create(
            name='Samsung Galaxy S25 FE',
            category=self.category,
            brand='Samsung',
            description='Samsung Fan Edition.',
            price='649.00',
            stock_quantity=6,
        )
        self.case = Accessory.objects.create(
            name='iPhone Silicone Case with MagSafe',
            category=Category.objects.create(name='Cases'),
            brand='Apple',
            description='Protective case.',
            compatibility_notes='Designed for iPhone.',
            price='49.00',
            stock_quantity=8,
        )
        self.solution = Solution.objects.create(
            title='iPhone 17 Pro Max battery drains overnight',
            category=Category.objects.create(name='Battery'),
            related_product=self.iphone_pro_max,
            problem_description='Battery drops while idle overnight.',
            steps='1. Check battery usage.\n2. Update iOS.\n3. Contact support.',
            difficulty_level='Easy',
        )
        self.slow_solution = Solution.objects.create(
            title='iPhone 17 running slow after update',
            category=Category.objects.create(name='Performance'),
            related_product=self.iphone_17,
            problem_description='Phone feels laggy after an update.',
            steps='1. Restart.\n2. Free up storage.',
            difficulty_level='Easy',
        )

    def test_brand_only_does_not_list_products_or_accessories(self):
        answer = build_answer('Apple')

        self.assertEqual(answer['kind'], 'answer')
        self.assertEqual(answer['badge'], 'Brand overview')
        self.assertTrue(answer.get('brand_overview'))
        self.assertEqual(answer['matches']['products'], [])
        self.assertEqual(answer['matches']['accessories'], [])
        self.assertEqual(answer['sources'], [])

    def test_brand_with_products_word_lists_products_only(self):
        answer = build_answer('Apple products')

        self.assertEqual(answer['kind'], 'results')
        names = {item.name for item in answer['matches']['products']}
        self.assertEqual(names, {'iPhone 17', 'iPhone 17 Pro Max'})
        self.assertEqual(answer['matches']['accessories'], [])

    def test_brand_with_accessories_word_lists_accessories_only(self):
        answer = build_answer('Apple accessories')

        self.assertEqual(answer['kind'], 'results')
        names = {item.name for item in answer['matches']['accessories']}
        self.assertEqual(names, {'iPhone Silicone Case with MagSafe'})
        self.assertEqual(answer['matches']['products'], [])

    def test_brand_phone_query_lists_products_without_accessories(self):
        answer = build_answer('Samsung phone')

        self.assertEqual(answer['kind'], 'results')
        names = {item.name for item in answer['matches']['products']}
        self.assertEqual(
            names, {'Samsung Galaxy S25 Ultra', 'Samsung Galaxy S25 FE'}
        )
        self.assertEqual(answer['matches']['accessories'], [])

    @patch('apps.core.gemini.ask_gemini')
    def test_chat_brand_only_hides_catalog_product_cards(self, mocked_ask):
        mocked_ask.return_value = {
            'is_tech': True,
            'title': 'About Apple',
            'summary': 'Apple designs the iPhone 17 and other devices.',
            'steps': [],
            'difficulty': '',
            'safety': '',
        }

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'Apple'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('About Apple', html)
        self.assertNotIn('assistant-mentioned-products', html)
        self.assertNotIn('assistant-results', html)
        self.assertNotIn('View product', html)

    def test_iphone_query_returns_only_iphone_products(self):
        answer = build_answer('iphone')

        self.assertEqual(answer['kind'], 'results')
        names = {item.name for item in answer['matches']['products']}
        self.assertEqual(names, {'iPhone 17', 'iPhone 17 Pro Max'})
        self.assertNotIn('Samsung Galaxy S25 Ultra', names)
        self.assertNotIn('Samsung Galaxy S25 FE', names)

    def test_exact_model_query_returns_exact_product(self):
        answer = build_answer('iphone 17 pro max')

        self.assertEqual(answer['kind'], 'product')
        self.assertEqual(answer['title'], 'iPhone 17 Pro Max')

    def test_price_query_does_not_invent_an_unlisted_price(self):
        self.iphone_pro_max.price = None
        self.iphone_pro_max.save(update_fields=['price'])
        answer = build_answer('price iphone 17 pro max')

        self.assertEqual(answer['kind'], 'product')
        self.assertIn('No price is listed in the TechFix catalog.', answer['summary'])
        self.assertNotIn('₱', answer['summary'])

    def test_general_tech_question_is_not_a_catalog_result(self):
        answer = build_answer('What is 5G?')

        self.assertEqual(answer['kind'], 'answer')
        self.assertFalse(answer.get('strict'))
        self.assertEqual(answer['steps'], [])
        self.assertEqual(answer['matches']['products'], [])
        self.assertEqual(answer['matches']['accessories'], [])

    def test_advice_question_is_not_troubleshooting(self):
        answer = build_answer('How do I choose a TV?')

        self.assertEqual(answer['kind'], 'answer')
        self.assertEqual(answer['steps'], [])
        self.assertNotEqual(answer['badge'], 'Troubleshooting guide')

    def test_battery_concept_is_not_troubleshooting(self):
        answer = build_answer('What is battery drain?')

        self.assertEqual(answer['kind'], 'answer')
        self.assertEqual(answer['steps'], [])

    def test_component_concept_is_not_a_missing_catalog_model(self):
        answer = build_answer('What is the RTX 5090?')

        self.assertEqual(answer['kind'], 'answer')
        self.assertNotEqual(answer['badge'], 'No exact match')

    def test_show_me_query_returns_catalog_results(self):
        answer = build_answer('Show me phones')

        self.assertEqual(answer['kind'], 'results')
        names = {item.name for item in answer['matches']['products']}
        self.assertIn('iPhone 17', names)
        self.assertIn('Samsung Galaxy S25 Ultra', names)

    @patch('apps.core.views.enhance_answer', return_value=None)
    def test_phone_recommendation_returns_one_specific_answer(self, mocked_enhance):
        recommended = Product.objects.create(
            name='Spec Leader Phone',
            category=self.category,
            brand='TestBrand',
            description='A well-equipped phone.',
            specifications=(
                'Snapdragon 8 Elite Gen 5, 16GB RAM / 512GB storage, '
                '120Hz OLED, 50MP camera, 6000mAh battery'
            ),
            price='499.00',
        )
        Product.objects.create(
            name='Basic Phone',
            category=self.category,
            brand='TestBrand',
            description='An entry-level phone.',
            specifications='8GB RAM / 128GB storage',
            price='199.00',
        )

        answer = build_answer(
            'Can you recommend a phone that has good specs? '
            'Can you show me those products?'
        )

        self.assertEqual(answer['kind'], 'product')
        self.assertEqual(answer['badge'], 'Recommended phone')
        self.assertEqual(answer['product'], recommended)
        self.assertEqual(answer['title'], 'My recommendation: Spec Leader Phone')
        self.assertIn('I recommend Spec Leader Phone', answer['summary'])
        self.assertIn('Snapdragon 8 Elite Gen 5', answer['summary'])
        self.assertIn('Listed price: ₱499.00', answer['summary'])

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({
                'message': (
                    'Can you recommend a phone that has good specs? '
                    'Can you show me those products?'
                ),
            }),
            content_type='application/json',
        )
        html = response.json()['html']
        self.assertIn('Recommended phone', html)
        self.assertIn('My recommendation: Spec Leader Phone', html)
        self.assertIn('I recommend Spec Leader Phone', html)
        self.assertIn('Snapdragon 8 Elite Gen 5', html)
        self.assertIn('View product', html)
        self.assertIn('Products mentioned in this answer', html)
        self.assertNotIn('Basic Phone', html)
        self.assertNotIn('assistant-results', html)

    def test_non_tech_issue_is_not_given_local_repair_steps(self):
        answer = build_answer('My car will not start')

        self.assertEqual(answer['kind'], 'answer')
        self.assertEqual(answer['steps'], [])

    def test_repair_question_keeps_local_steps(self):
        answer = build_answer('How do I fix my laptop that will not turn on?')

        self.assertEqual(answer['badge'], 'Troubleshooting guide')
        self.assertGreaterEqual(len(answer['steps']), 3)

    @patch('apps.core.views.enhance_answer')
    def test_product_question_uses_ai_and_exact_catalog_match(
        self, mocked_enhance
    ):
        mocked_enhance.return_value = ai_answer(
            kind='product',
            title='iPhone 17 Pro Max overview',
            summary='The iPhone 17 Pro Max is a flagship phone.',
        )
        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'What is iPhone 17 Pro Max?'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        html = response.json()['html']
        self.assertIn('The iPhone 17 Pro Max is a flagship phone.', html)
        self.assertIn('iPhone 17 Pro Max', html)
        self.assertIn('₱1,199.00', html)
        self.assertNotIn('Samsung Galaxy S25 Ultra', html)

    def test_samsung_model_query_does_not_pick_fe_variant(self):
        answer = build_answer('samsung galaxy s25 ultra')

        self.assertEqual(answer['kind'], 'product')
        self.assertEqual(answer['title'], 'Samsung Galaxy S25 Ultra')

    def test_iphone_issue_query_does_not_return_other_devices(self):
        answer = build_answer('iphone battery drains')

        self.assertEqual(answer['kind'], 'solution')
        self.assertEqual(answer['product'].brand, 'Apple')
        self.assertIn('iPhone', answer['title'])
        self.assertEqual(answer['suggestions'], [])

    def test_iphone_accessory_query_returns_only_iphone_cases(self):
        answer = build_answer('iphone case')

        self.assertEqual(answer['kind'], 'results')
        names = [item.name for item in answer['matches']['accessories']]
        self.assertEqual(names, ['iPhone Silicone Case with MagSafe'])
        self.assertEqual(answer['matches']['products'], [])

    def test_missing_model_gets_no_match_instead_of_other_devices(self):
        answer = build_answer('iphone 18')

        self.assertEqual(answer['badge'], 'No exact match')
        self.assertEqual(answer['matches']['products'], [])
        self.assertEqual(answer['steps'], [])

    @patch('apps.core.views.enhance_answer')
    def test_chat_does_not_invent_missing_catalog_product(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer(
            summary='No exact match for iPhone 18 in the TechFix catalog.'
        )
        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'What is iPhone 18?'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        self.assertIn('No exact match', response.json()['html'])
        self.assertNotIn('View product', response.json()['html'])

    @patch('apps.core.views.enhance_answer')
    def test_chat_strict_results_use_ai_and_render_matches(self, mocked_enhance):
        mocked_enhance.return_value = ai_answer(
            kind='results',
            title='iPhone models',
            summary='These are the iPhone models in the TechFix catalog.',
        )
        user = get_user_model().objects.create_user(
            username='strict-chat', password='secret1234'
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'iphone'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        html = response.json()['html']
        self.assertIn(
            'These are the iPhone models in the TechFix catalog.', html
        )
        self.assertIn('iPhone 17', html)
        self.assertIn('iPhone 17 Pro Max', html)
        self.assertNotIn('Samsung Galaxy S25', html)

    @patch('apps.core.views.enhance_answer')
    def test_ai_answer_does_not_link_products_the_user_did_not_name(
        self, mocked_enhance
    ):
        self.client.logout()
        named_phone = Product.objects.create(
            name='Samsung Galaxy S24 Ultra',
            category=self.category,
            brand='Samsung',
            description='Samsung flagship phone.',
        )
        named_iphone = Product.objects.create(
            name='iPhone 15 Pro Max',
            category=self.category,
            brand='Apple',
            description='Apple flagship phone.',
        )
        mocked_enhance.return_value = ai_answer(
            kind='answer',
            title='Top smartphone recommendations',
            summary=(
                'The Samsung Galaxy S24 Ultra and iPhone 15 Pro Max are '
                'both strong choices.'
            ),
        )

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'My phone will not charge'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        mocked_enhance.assert_called_once()
        html = response.json()['html']
        self.assertNotIn(
            'class="assistant-result assistant-mentioned-product"', html
        )
        self.assertNotIn(reverse('product_detail', args=[named_phone.pk]), html)
        self.assertNotIn(reverse('product_detail', args=[named_iphone.pk]), html)

    @patch('apps.core.views.enhance_answer')
    def test_brand_only_message_does_not_show_a_random_product(
        self, mocked_enhance
    ):
        self.client.logout()
        mocked_enhance.return_value = ai_answer(
            kind='answer',
            title='Samsung overview',
            summary='Samsung makes the Galaxy S25 Ultra and many other devices.',
        )

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'Samsung'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('Samsung makes the Galaxy S25 Ultra', html)
        self.assertNotIn(
            'class="assistant-result assistant-mentioned-product"', html
        )

    @patch('apps.core.views.enhance_answer')
    def test_message_mentioning_a_product_shows_that_specific_product(
        self, mocked_enhance
    ):
        self.client.logout()
        mocked_enhance.return_value = ai_answer(
            kind='answer',
            title='Flagship comparison',
            summary='Both devices are strong choices.',
        )

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({
                'message': 'Is the Samsung Galaxy S25 Ultra a good phone?',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertEqual(
            html.count('class="assistant-result assistant-mentioned-product"'),
            1,
        )
        self.assertIn(
            reverse('product_detail', args=[self.samsung_ultra.pk]), html
        )
        self.assertNotIn(
            reverse('product_detail', args=[self.iphone_17.pk]), html
        )

    @patch('apps.core.views.build_answer')
    @patch('apps.core.views.enhance_answer')
    def test_solution_shows_selected_product_once(
        self, mocked_enhance, mocked_build
    ):
        self.client.logout()
        mocked_build.return_value = {
            'kind': 'solution',
            'product': self.iphone_17,
            'strict': False,
            'sources': [],
        }
        mocked_enhance.return_value = ai_answer(
            kind='solution',
            title='iPhone 17 charging help',
            summary='Try restarting the iPhone 17 before testing the charger.',
            steps=['Restart the iPhone 17.'],
        )

        response = self.client.post(
            reverse('assistant_chat'),
            data=json.dumps({'message': 'My iPhone 17 will not charge'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertEqual(
            html.count('class="assistant-result assistant-mentioned-product"'),
            1,
        )
        self.assertNotIn('assistant-related-product', html)
        self.assertNotIn('View device', html)
        self.assertEqual(
            html.count(reverse('product_detail', args=[self.iphone_17.pk])),
            1,
        )


class ContextQueryTests(SimpleTestCase):
    def test_follow_up_how_much_uses_previous_question(self):
        history = [{'role': 'user', 'text': 'Tell me about Test Phone'}]

        self.assertEqual(
            _context_query('How much?', history),
            'Tell me about Test Phone How much?',
        )

    def test_unrelated_question_keeps_its_own_context(self):
        history = [{'role': 'user', 'text': 'My laptop will not turn on'}]

        self.assertEqual(
            _context_query('How do I reset my router?', history),
            'How do I reset my router?',
        )


class GeminiParsingTests(SimpleTestCase):
    def test_follow_up_prompt_answers_only_the_latest_question(self):
        prompt = _build_prompt(
            'How much?',
            [],
            history_included=True,
        )

        self.assertIn('Answer only the user\'s latest question.', prompt)
        self.assertIn(
            'do not repeat or summarize earlier answers unless the user asks.',
            prompt,
        )

    def test_attachment_prompt_mentions_visual_inspection(self):
        prompt = _build_prompt('What is wrong?', [], attachments=True)

        self.assertIn('The user attached file content', prompt)
        self.assertIn('Read visible text', prompt)

    def test_attachment_parts_encode_images_for_gemini(self):
        parts = _attachment_parts([
            {
                'type': 'image',
                'name': 'phone.png',
                'mime_type': 'image/png',
                'data': b'photo-bytes',
            },
            {'type': 'text', 'text': 'hello'},
            {'type': 'note', 'text': 'unsupported file'},
        ])

        self.assertEqual(parts[0], {'text': 'Image attachment: phone.png'})
        self.assertEqual(parts[1]['inlineData']['mimeType'], 'image/png')
        self.assertEqual(
            base64.b64decode(parts[1]['inlineData']['data']),
            b'photo-bytes',
        )
        self.assertEqual(parts[2], {'text': 'hello'})
        self.assertEqual(parts[3], {'text': 'unsupported file'})

    def test_extract_text_ignores_thought_parts(self):
        data = {
            'candidates': [{
                'content': {
                    'parts': [
                        {'text': 'Internal reasoning.', 'thought': True},
                        {'text': '{"summary": "Answer."}'},
                    ],
                },
            }],
        }

        self.assertEqual(_extract_text(data), '{"summary": "Answer."}')

    def test_extract_text_strips_markdown_fences(self):
        data = {
            'candidates': [{
                'content': {
                    'parts': [{'text': '```json\n{"summary": "Answer."}\n```'}],
                },
            }],
        }

        self.assertEqual(_extract_text(data), '{"summary": "Answer."}')

    def test_parse_normalizes_difficulty(self):
        data = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': json.dumps({
                            'is_tech': True,
                            'title': 'Fix',
                            'summary': 'Answer.',
                            'steps': ['One'],
                            'difficulty': 'medium',
                        }),
                    }],
                },
            }],
        }

        parsed = _parse_gemini_data(data, 'test-model')

        self.assertEqual(parsed['difficulty'], 'Medium')


class GeminiEnhanceTests(TestCase):
    @patch('apps.core.gemini.ask_gemini')
    def test_enhance_forwards_attachments(self, mocked_ask):
        attachments = [{
            'type': 'image',
            'name': 'phone.png',
            'mime_type': 'image/png',
            'data': b'photo-bytes',
        }]
        mocked_ask.return_value = {
            'is_tech': True,
            'title': 'Photo analysis',
            'summary': 'The photo shows a damaged cable.',
            'steps': [],
            'difficulty': '',
            'safety': '',
        }

        enhance_answer(
            'What is wrong in this photo?',
            {'kind': 'fallback', 'summary': 'Local answer', 'steps': []},
            attachments=attachments,
        )

        self.assertEqual(mocked_ask.call_args.kwargs['attachments'], attachments)

    @patch('apps.core.gemini.ask_gemini')
    def test_off_topic_questions_are_refused(self, mocked_ask):
        mocked_ask.return_value = {
            'is_tech': False,
            'title': '',
            'summary': 'I can only help with technology questions.',
            'steps': [],
            'difficulty': '',
            'safety': '',
        }

        answer = enhance_answer('What is the weather tomorrow?', {
            'kind': 'fallback',
            'summary': 'Local answer',
            'steps': ['Local step'],
        })

        self.assertEqual(answer['kind'], 'fallback')
        self.assertEqual(answer['badge'], 'TechFix only')
        self.assertEqual(answer['steps'], [])
        self.assertIn('only help with technology', answer['summary'])

    @patch('apps.core.gemini.ask_gemini', return_value=None)
    def test_ai_failure_keeps_local_answer_with_notice(self, mocked_ask):
        answer = enhance_answer('My phone will not charge', {
            'kind': 'fallback',
            'badge': 'General guidance',
            'summary': 'Local answer',
            'steps': ['Local step'],
        })

        self.assertEqual(answer['summary'], 'Local answer')
        self.assertIn('AI is temporarily unavailable', answer['notice'])
        self.assertEqual(answer['badge'], 'General guidance')

    @patch('apps.core.gemini.ask_gemini')
    def test_gemini_answer_replaces_summary_and_steps(self, mocked_ask):
        mocked_ask.return_value = {
            'is_tech': True,
            'title': 'Charging fix',
            'summary': 'Gemini summary.',
            'steps': ['Gemini step one.', 'Gemini step two.'],
            'difficulty': 'Medium',
            'safety': 'Unplug the charger first.',
        }

        answer = enhance_answer('My phone will not charge', {
            'kind': 'solution',
            'title': 'Original title',
            'summary': 'Local summary',
            'steps': ['Local step'],
            'steps_title': 'Local steps',
            'first_step': 'Local step',
            'difficulty': 'Easy',
            'safety': '',
            'badge': 'Repair guide',
            'ai': False,
        })

        self.assertTrue(answer['ai'])
        self.assertEqual(answer['summary'], 'Gemini summary.')
        self.assertEqual(answer['steps'], ['Gemini step one.', 'Gemini step two.'])
        self.assertEqual(answer['first_step'], '')
        self.assertEqual(answer['difficulty'], 'Medium')
        self.assertEqual(answer['safety'], 'Unplug the charger first.')
        self.assertEqual(answer['badge'], 'AI repair answer')

    @patch('apps.core.gemini.ask_gemini')
    def test_gemini_empty_steps_clear_local_repair_steps(self, mocked_ask):
        mocked_ask.return_value = {
            'is_tech': True,
            'title': 'Price check',
            'summary': 'The Test Phone costs 499.99.',
            'steps': [],
            'difficulty': '',
            'safety': '',
        }

        answer = enhance_answer('How much is the Test Phone?', {
            'kind': 'solution',
            'title': 'Original title',
            'summary': 'Local summary',
            'steps': ['Local step'],
            'steps_title': 'Local steps',
            'first_step': 'Local step',
            'badge': 'Repair guide',
            'ai': False,
        })

        self.assertEqual(answer['steps'], [])
        self.assertEqual(answer['steps_title'], '')
        self.assertEqual(answer['badge'], 'AI answer')

class ReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='reviewer',
            password='secret1234',
            first_name='Review',
            last_name='User',
        )
        self.category = Category.objects.create(name='Laptops')
        self.product = Product.objects.create(
            name='Review Laptop',
            category=self.category,
            brand='ReviewBrand',
            description='A laptop for review tests.',
            price='999.00',
            stock_quantity=1,
        )
        self.accessory = Accessory.objects.create(
            name='Review Dock',
            category=self.category,
            brand='ReviewBrand',
            description='A dock for review tests.',
            price='99.00',
            stock_quantity=1,
        )
        self.client.force_login(self.user)

    def test_guests_see_reviews_and_signin_prompt(self):
        self.client.logout()
        response = self.client.get(
            reverse('product_detail', args=[self.product.pk])
        )

        self.assertContains(response, 'Ratings &amp; reviews')
        self.assertContains(response, 'No customer reviews yet')
        self.assertContains(response, 'Sign in to review')
        self.assertNotContains(response, 'Post review')

    def test_user_can_post_and_update_a_product_review(self):
        url = reverse('product_detail', args=[self.product.pk])
        response = self.client.post(
            url,
            {'rating': '5', 'title': 'Excellent', 'comment': 'Works great.'},
        )

        self.assertEqual(response.url, url + '#reviews')
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.title, 'Excellent')

        page = self.client.get(url)
        self.assertContains(page, 'Excellent')
        self.assertContains(page, 'Works great.')
        self.assertContains(page, '5.0')
        self.assertContains(page, '1 review')
        self.assertContains(page, 'Update your review')

        response = self.client.post(
            url,
            {'rating': '3', 'title': 'Changed', 'comment': 'Still good.'},
        )
        self.assertEqual(response.url, url + '#reviews')
        self.assertEqual(
            Review.objects.filter(product=self.product, user=self.user).count(),
            1,
        )
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.title, 'Changed')
        self.assertEqual(review.comment, 'Still good.')

    def test_user_can_post_an_accessory_review(self):
        url = reverse('accessory_detail', args=[self.accessory.pk])
        response = self.client.post(
            url,
            {'rating': '4', 'title': 'Useful', 'comment': 'Does the job.'},
        )

        self.assertEqual(response.url, url + '#reviews')
        review = Review.objects.get(accessory=self.accessory, user=self.user)
        self.assertEqual(review.rating, 4)
        page = self.client.get(url)
        self.assertContains(page, 'Useful')
        self.assertContains(page, 'Does the job.')
        self.assertContains(page, '4.0')

    def test_invalid_review_is_rejected(self):
        url = reverse('product_detail', args=[self.product.pk])
        response = self.client.post(url, {'rating': '9', 'comment': ''})

        self.assertEqual(response.url, url + '#reviews')
        self.assertFalse(Review.objects.exists())

    def test_sample_reviews_are_clearly_labeled(self):
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            title='Sample title',
            comment='Sample comment.',
            is_sample=True,
        )

        response = self.client.get(
            reverse('product_detail', args=[self.product.pk])
        )

        self.assertContains(response, 'Demo content:')
        self.assertContains(response, 'review-sample-badge')
        self.assertContains(response, 'not real customer feedback')

    def test_online_rating_takes_display_priority(self):
        self.product.online_rating = Decimal('4.35')
        self.product.online_rating_count = 123
        self.product.online_rating_source = 'Smartprix'
        self.product.save(update_fields=[
            'online_rating',
            'online_rating_count',
            'online_rating_source',
        ])
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=2,
            title='Local review',
            comment='Local review body.',
        )

        self.assertEqual(self.product.display_rating, Decimal('4.35'))
        self.assertEqual(self.product.display_rating_count, 123)
        self.assertTrue(self.product.rating_is_online)

        response = self.client.get(
            reverse('product_detail', args=[self.product.pk])
        )
        self.assertContains(response, '123 online ratings')
        self.assertContains(response, 'on Smartprix')


class OnlineRatingMatchTests(SimpleTestCase):
    def test_search_variants_remove_year_and_specs(self):
        variants = product_search_variants('Lenovo Tab Plus Gen 2 (2026)')

        self.assertIn('Lenovo Tab Plus Gen 2', variants)

    def test_year_mismatch_is_rejected(self):
        self.assertTrue(_candidate_conflicts(
            'Asus ROG Strix SCAR 18 2026 G835LXG Gaming Laptop',
            'ASUS ROG Strix SCAR 18 (2025)',
        ))

    def test_older_candidate_cpu_year_is_rejected(self):
        self.assertTrue(_candidate_conflicts(
            'Gigabyte Aero 14 OLED BMF Laptop (13th Gen Core i7)',
            'Gigabyte Aero 14 (2017)',
        ))
        self.assertFalse(_candidate_conflicts(
            'Lenovo Legion 5 15IMH6 Gaming Laptop (10th Gen Core i5)',
            'Lenovo Legion 5 15 (2020)',
        ))

    def test_missing_or_different_generation_is_rejected(self):
        self.assertTrue(_candidate_conflicts(
            'Lenovo ThinkBook 14 Gen 9 Laptop',
            'Lenovo ThinkBook 14 G6 (2024)',
        ))
        self.assertTrue(_candidate_conflicts(
            'Lenovo Yoga Pro 7i Aura Edition Gen 11 Laptop',
            'Lenovo Yoga Pro 9i 16 Gen 11 (2026)',
        ))

    def test_reordered_model_tokens_are_matched(self):
        product = Product(name='MSI GF63 Thin 12VE', brand='MSI')
        candidates = [(
            'MSI Thin GF63 12VE-080IN Gaming Laptop '
            '(12th Gen Core i7/ 8GB/ 512GB SSD)',
            '/laptops/msi-thin-gf63-12ve',
            4.35,
        )]

        chosen = pick_candidate(candidates, product, allow_prefix=True)

        self.assertIsNotNone(chosen)
        self.assertIn('Thin GF63 12VE', chosen[0])

    def test_gpu_variant_must_match(self):
        product = Product(name='Acer Swift X 14 RTX 4050')
        candidates = [(
            'Acer Swift X SFX14-41G Laptop (Ryzen 7/ 4GB Graph)',
            '/laptops/acer-swift-x',
            4.7,
        )]

        self.assertIsNone(
            pick_candidate(candidates, product, allow_prefix=True)
        )

    def test_exact_year_candidate_wins(self):
        product = Product(name='ASUS ROG Strix SCAR 18 (2025)')
        candidates = [
            (
                'Asus ROG Strix SCAR 18 2026 Gaming Laptop '
                '(Intel Core Ultra 9/ 32GB)',
                '/laptops/scar-18-2026',
                4.4,
            ),
            (
                'Asus ROG Strix SCAR 18 2025 Gaming Laptop '
                '(Intel Core Ultra 9/ 32GB)',
                '/laptops/scar-18-2025',
                4.3,
            ),
        ]

        chosen = pick_candidate(candidates, product, allow_prefix=True)

        self.assertIn('2025', chosen[0])


class RequestedBrandCatalogCommandTests(TestCase):
    def test_command_imports_requested_brands_and_is_idempotent(self):
        from apps.core.management.commands.seed_requested_brand_catalog import (
            BRAND_KEYS,
            BRAND_NAMES,
        )
        from old_accessories_data import OLD_ACCESSORIES
        from old_products_data import OLD_PRODUCTS

        Product.objects.create(
            name='Unrequested Laptop',
            category=Category.objects.create(name='Laptops'),
            brand='Unrequested',
            description='Should remain untouched.',
        )
        Accessory.objects.create(
            name='Unrequested Charger',
            brand='Unrequested',
            description='Should remain untouched.',
        )

        first_output = StringIO()
        call_command(
            'seed_requested_brand_catalog',
            stdout=first_output,
        )

        expected_products = sum(len(OLD_PRODUCTS[key]) for key in BRAND_KEYS)
        expected_accessories = sum(
            len(OLD_ACCESSORIES[key]) for key in BRAND_KEYS
        )
        self.assertEqual(
            Product.objects.exclude(brand='Unrequested').count(),
            expected_products,
        )
        self.assertEqual(
            Accessory.objects.exclude(brand='Unrequested').count(),
            expected_accessories,
        )
        self.assertEqual(Solution.objects.count(), 0)
        for key in BRAND_KEYS:
            brand = BRAND_NAMES[key]
            self.assertEqual(
                Product.objects.filter(brand=brand).count(),
                len(OLD_PRODUCTS[key]),
            )
            self.assertEqual(
                Accessory.objects.filter(brand=brand).count(),
                len(OLD_ACCESSORIES[key]),
            )
        self.assertEqual(
            Accessory.objects.get(
                brand='Apple',
                name='Apple 5W USB Power Adapter (original)',
            )
            .compatible_products.count(),
            2,
        )
        self.assertEqual(
            Product.objects.filter(brand='Unrequested').count(),
            1,
        )
        self.assertEqual(
            Accessory.objects.filter(brand='Unrequested').count(),
            1,
        )

        second_output = StringIO()
        call_command(
            'seed_requested_brand_catalog',
            stdout=second_output,
        )
        self.assertIn('0 added', second_output.getvalue())
        self.assertEqual(
            Product.objects.exclude(brand='Unrequested').count(),
            expected_products,
        )
        self.assertEqual(
            Accessory.objects.exclude(brand='Unrequested').count(),
            expected_accessories,
        )


class CurrentOfficialCatalogCommandTests(TestCase):
    def test_command_imports_source_linked_items_idempotently(self):
        from apps.core.management.commands.seed_current_official_catalog import (
            ACCESSORIES,
            PRODUCTS,
        )

        existing = Product.objects.create(
            name='Galaxy S26',
            category=Category.objects.create(name='Existing phone category'),
            brand='Samsung',
            description='Existing catalog entry.',
            price='1234.00',
            stock_quantity=5,
        )
        existing_accessory = Accessory.objects.create(
            name='Anker Nano Charger (45W, Smart Display, 180° Foldable)',
            brand='Anker',
            description='Existing accessory entry.',
            price='99.00',
            stock_quantity=2,
        )

        first_output = StringIO()
        call_command('seed_current_official_catalog', stdout=first_output)

        self.assertIn('21 added, 1 refreshed', first_output.getvalue())
        self.assertIn('6 added, 1 refreshed', first_output.getvalue())
        self.assertEqual(Product.objects.count(), len(PRODUCTS))
        self.assertEqual(Accessory.objects.count(), len(ACCESSORIES))

        existing.refresh_from_db()
        self.assertIsNone(existing.price)
        self.assertIsNone(existing.stock_quantity)
        self.assertTrue(existing.source_url.startswith('https://www.samsung.com/'))

        existing_accessory.refresh_from_db()
        self.assertIsNone(existing_accessory.price)
        self.assertIsNone(existing_accessory.stock_quantity)
        self.assertTrue(existing_accessory.source_url.startswith('https://www.anker.com/'))

        new_phone = Product.objects.get(brand='Apple', name='iPhone 18 Pro')
        self.assertTrue(new_phone.source_url.startswith('https://www.apple.com/'))
        self.assertIsNone(new_phone.price)
        self.assertIsNone(new_phone.stock_quantity)

        new_accessory = Accessory.objects.get(
            brand='Anker',
            name='Anker Nano Charger (45W, Smart Display, 180° Foldable)',
        )
        self.assertTrue(new_accessory.source_url.startswith('https://www.anker.com/'))
        self.assertIsNone(new_accessory.price)
        self.assertIsNone(new_accessory.stock_quantity)

        second_output = StringIO()
        call_command('seed_current_official_catalog', stdout=second_output)

        self.assertIn('0 added, 22 refreshed', second_output.getvalue())
        self.assertIn('0 added, 7 refreshed', second_output.getvalue())
        self.assertEqual(Product.objects.count(), len(PRODUCTS))
        self.assertEqual(Accessory.objects.count(), len(ACCESSORIES))


class SampleReviewCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Laptops')
        self.product = Product.objects.create(
            name='Seed Laptop',
            category=self.category,
            brand='SeedBrand',
            description='A laptop for seed tests.',
            price='999.00',
            stock_quantity=1,
        )
        self.accessory = Accessory.objects.create(
            name='Seed Dock',
            category=self.category,
            brand='SeedBrand',
            description='A dock for seed tests.',
            price='99.00',
            stock_quantity=1,
        )

    def test_command_seeds_every_item_with_labeled_reviews(self):
        output = StringIO()
        call_command(
            'seed_sample_reviews',
            min_reviews=2,
            max_reviews=2,
            seed=7,
            stdout=output,
        )

        self.assertEqual(Review.objects.filter(is_sample=True).count(), 4)
        self.assertEqual(Review.objects.filter(product=self.product).count(), 2)
        self.assertEqual(Review.objects.filter(accessory=self.accessory).count(), 2)
        self.assertTrue(
            all(review.is_sample for review in Review.objects.all())
        )
        self.assertTrue(
            all(
                review.user.username.startswith('techfix_sample_')
                for review in Review.objects.select_related('user')
            )
        )
        self.assertIn('Created 4 labeled sample reviews', output.getvalue())

    def test_command_is_idempotent(self):
        call_command(
            'seed_sample_reviews',
            min_reviews=3,
            max_reviews=3,
            seed=7,
            stdout=StringIO(),
        )
        call_command(
            'seed_sample_reviews',
            min_reviews=3,
            max_reviews=3,
            seed=7,
            stdout=StringIO(),
        )

        self.assertEqual(Review.objects.filter(is_sample=True).count(), 6)
        self.assertEqual(Review.objects.filter(is_sample=True).values('user').distinct().count(), 6)
