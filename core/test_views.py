from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class TestViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.profile = self.user.profile
        self.profile.target_kcal = 2000
        self.profile.save()
        
    def test_index_page(self):
        """Проверка доступности главной страницы."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

    def test_menu_types_page(self):
        """Проверка доступности страницы Типы Меню."""
        response = self.client.get(reverse('menu_types'))
        self.assertEqual(response.status_code, 200)

    def test_profile_page_unauthenticated(self):
        """При попытке зайти в профиль без логина должно быть перенаправление."""
        response = self.client.get(reverse('profile'))
        self.assertNotEqual(response.status_code, 200)
        self.assertTrue(response.status_code in [302, 403])
        
    def test_profile_page_authenticated(self):
        """Залогиненный пользователь должен иметь доступ к профилю."""
        self.client.login(username="testuser", password="password")
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
