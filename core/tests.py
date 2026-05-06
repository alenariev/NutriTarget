from django.test import TestCase
from django.utils import timezone
from .models import Profile, Recipe
from .logic import scale_ingredients, calculate_macros, generate_weekly_plan
from django.contrib.auth.models import User
import datetime

class LogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        # Профиль создается автоматически через сигнал post_save в models.py
        self.profile = self.user.profile
        self.profile.weight = 80
        self.profile.height = 180
        self.profile.age = 30
        self.profile.gender = 'male'
        self.profile.activity = 1.2
        self.profile.goal = 'maintain'
        self.profile.save()

        # Создаем минимальный набор рецептов для тестирования
        Recipe.objects.create(title="Блинчики", meal_type="breakfast", diet_type="all", calories=250, protein=10, fat=10, carbs=30, description="Мука 100г, Яйцо 1шт")
        Recipe.objects.create(title="Салат", meal_type="lunch", diet_type="vegan", calories=150, protein=5, fat=5, carbs=20, description="Огурец 100г, Помидор 100г")
        Recipe.objects.create(title="Перекус", meal_type="snack", diet_type="all", calories=100, protein=2, fat=2, carbs=15, description="Яблоко 150г")
        Recipe.objects.create(title="Ужин", meal_type="dinner", diet_type="pesca", calories=300, protein=20, fat=10, carbs=10, description="Рыба 150г")

    def test_calculate_macros(self):
        """Проверяет правильность расчета КБЖУ"""
        # BMR male: 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
        # TDEE = 1780 * 1.2 = 2136
        macros = calculate_macros(self.profile)
        self.assertEqual(macros['kcal'], 2136)
        # Белки = 2136 * 0.3 / 4 = 160.2 -> 160
        self.assertEqual(macros['p'], 160)
        
    def test_scale_ingredients_weight(self):
        """Проверяет корректность умножения граммовок (с указанием единиц измерения)"""
        desc = "Курица 100г, Вода 200мл"
        scaled = scale_ingredients(desc, 1.5)
        self.assertEqual(scaled, "Курица 150г, Вода 300мл")
        
    def test_scale_ingredients_pieces(self):
        """Проверяет корректность умножения штук"""
        desc = "Яблоко 1шт"
        scaled = scale_ingredients(desc, 2.0)
        self.assertEqual(scaled, "Яблоко 2шт")

    def test_generate_weekly_plan_length(self):
        """Проверяет, что план для зарегистрированного юзера генерируется корректно на 7 дней"""
        all_recipes = list(Recipe.objects.all())
        plan = generate_weekly_plan(self.profile, all_recipes, target_kcal=2000, is_guest=False)
        self.assertEqual(len(plan), 7) # 7 дней
        self.assertEqual(len(plan[0]['meals']), 4) # 4 приема пищи
        
    def test_generate_weekly_plan_guest(self):
        """Проверяет, что план для гостя генерируется и не падает из-за отсутствия базы"""
        all_recipes = list(Recipe.objects.all())
        session_data = {'weight': 60, 'height': 165, 'age': 25, 'gender': 'female'}
        plan = generate_weekly_plan(session_data, all_recipes, target_kcal=1500, is_guest=True)
        self.assertEqual(len(plan), 7)

    def test_generate_weekly_plan_timestamp_update(self):
        """Проверяет автообновление таймстемпа раз в 7 дней (стабильность меню)"""
        self.assertIsNone(self.profile.last_weekly_refresh)
        all_recipes = list(Recipe.objects.all())
        
        # 1. Первая генерация - должно установить таймстемп
        generate_weekly_plan(self.profile, all_recipes, 2000)
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.last_weekly_refresh)
        
        old_time = self.profile.last_weekly_refresh
        
        # 2. Вторая генерация в тот же день
        generate_weekly_plan(self.profile, all_recipes, 2000)
        self.profile.refresh_from_db()
        # Дата обновления НЕ должна измениться, так как не прошло 7 дней
        self.assertEqual(self.profile.last_weekly_refresh, old_time)

        # 3. Симулируем отмотку времени на 8 дней назад
        self.profile.last_weekly_refresh = timezone.now() - datetime.timedelta(days=8)
        self.profile.save()
        
        # 4. Третья генерация (спустя неделю)
        generate_weekly_plan(self.profile, all_recipes, 2000)
        self.profile.refresh_from_db()
        # Дата обновления ДОЛЖНА измениться, так как прошло больше недели
        self.assertNotEqual(self.profile.last_weekly_refresh, old_time)
