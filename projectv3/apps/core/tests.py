import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .assistant import build_answer
from .gemini import _extract_text, _parse_gemini_data, enhance_answer
from .models import Accessory, Category, Product, Solution
from .views import CHAT_SESSION_KEY, _context_query


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

    def test_product_detail_back_button_returns_to_products(self):
        response = self.client.get(
            reverse('product_detail', args=[Product.objects.first().pk])
        )

        self.assertContains(
            response,
            '<a href="%s" class="btn btn-outline-primary btn-sm">'
            '<i class="fas fa-arrow-left me-1"></i>Back</a>'
            % (reverse('dashboard') + '#techfix'),
            html=True,
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

    def test_brand_detail_back_button_returns_to_brands(self):
        response = self.client.get(reverse('brand_detail', args=['TestBrand']))

        self.assertContains(
            response,
            '<a href="%s" class="btn btn-outline-primary btn-sm">'
            '<i class="fas fa-arrow-left me-1"></i>Back</a>' % reverse('brand_list'),
            html=True,
        )
        self.assertNotContains(response, 'All brands')
        self.assertNotContains(response, '>Dashboard</a>')

    def test_library_page_renders_new_layout(self):
        response = self.client.get(reverse('brand_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'catalog/brands.html')
        self.assertContains(response, 'Search library')
        for tab in ('suggested', 'favorites', 'folders', 'images', 'all'):
            self.assertContains(response, 'data-library-tab="%s"' % tab)
        self.assertContains(response, 'TestBrand')
        self.assertContains(response, 'data-library-favorite="TestBrand"')

    def test_recent_page_activity_is_shown_to_signed_in_user(self):
        self.client.get(reverse('product_detail', args=[Product.objects.first().pk]))
        self.client.get(reverse('brand_detail', args=['TestBrand']))

        response = self.client.get(reverse('dashboard'))
        sidebar = response.content.decode().split(
            '<div class="sidebar-nav" id="recentActivities"', 1
        )[1].split('</div>', 1)[0]

        self.assertIn('Brand: TestBrand', sidebar)
        self.assertIn('Product: Test Laptop', sidebar)
        self.assertLess(sidebar.index('Brand: TestBrand'), sidebar.index('Product: Test Laptop'))

    def test_library_search_filters_folders(self):
        response = self.client.get(reverse('brand_list'), {'q': 'TestBrand'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TestBrand')
        self.assertNotContains(response, 'OtherBrand')
        self.assertContains(response, 'data-initial-tab="all"')

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
    def test_product_answer_renders_catalog_details(self, mocked_enhance):
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
        html = response.json()['html']
        self.assertIn('TestBrand', html)
        self.assertIn('₱1,499.99', html)
        self.assertNotIn('$1,499.99', html)
        self.assertIn('RAM: 8GB', html)
        self.assertIn('View product', html)
        self.assertIn('data-chat-prompt="How do I reset it?"', html)


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
    def test_chat_strict_results_skip_ai_and_render_matches(self, mocked_enhance):
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
        mocked_enhance.assert_not_called()
        html = response.json()['html']
        self.assertIn('iPhone 17', html)
        self.assertIn('iPhone 17 Pro Max', html)
        self.assertNotIn('Samsung Galaxy S25', html)


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
