from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
import datetime
import json
from .models import Recipe

class TestAPIs(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.profile = self.user.profile
        self.profile.target_kcal = 2000
        self.profile.diet_pref = 'all'
        self.profile.weight = 70
        self.profile.height = 175
        self.profile.age = 25
        self.profile.gender = 'male'
        self.profile.activity = 1.2
        self.profile.save()
        
        self.recipe = Recipe.objects.create(
            title="Тест", meal_type="lunch", diet_type="all", 
            calories=100, protein=10, fat=10, carbs=10, description="Тест"
        )
        self.recipe2 = Recipe.objects.create(
            title="Замена", meal_type="lunch", diet_type="all", 
            calories=200, protein=20, fat=20, carbs=20, description="Тест"
        )
        
    def test_toggle_favorite(self):
        """Проверяет логику добавления и удаления из избранного через API."""
        self.client.login(username="testuser", password="password")
        
        # Добавляем в избранное
        response = self.client.post(reverse('toggle_favorite'), json.dumps({'recipe_id': self.recipe.id}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['action'], 'added')
        self.assertIn(self.recipe, self.profile.favorite_recipes.all())
        
        # Удаляем из избранного (тот же запрос)
        response2 = self.client.post(reverse('toggle_favorite'), json.dumps({'recipe_id': self.recipe.id}), content_type='application/json')
        data2 = json.loads(response2.content)
        self.assertEqual(data2['action'], 'removed')
        self.assertNotIn(self.recipe, self.profile.favorite_recipes.all())

    def test_replace_meal_ajax_premium(self):
        """Проверяет эндпоинт замены блюда, требующий подписки Premium."""
        self.client.login(username="testuser", password="password")
        
        # Запрос без Premium должен вернуть 403
        response = self.client.post(reverse('replace_meal'), json.dumps({
            'recipe_id': self.recipe.id,
            'meal_type': 'lunch'
        }), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        
        # Выдаем Premium подписку на 30 дней
        self.profile.is_subscribed = True
        self.profile.subscription_end = timezone.now().date() + datetime.timedelta(days=30)
        self.profile.save()
        
        # Теперь замена должна пройти успешно (заменяет `recipe` на `recipe2`)
        response_success = self.client.post(reverse('replace_meal'), json.dumps({
            'recipe_id': self.recipe.id,
            'meal_type': 'lunch'
        }), content_type='application/json')
        
        self.assertEqual(response_success.status_code, 200)
        data = json.loads(response_success.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['new_meal']['id'], self.recipe2.id)
