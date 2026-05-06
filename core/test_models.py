from django.test import TestCase
from django.utils import timezone
import datetime
from django.contrib.auth.models import User

class TestModels(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testmodeluser")
        self.profile = self.user.profile

    def test_can_refresh_menu(self):
        """Проверяет, когда профиль имеет право на обновление меню."""
        # По умолчанию пользователь ни разу не обновлял меню, значит можно
        self.assertIsNone(self.profile.last_weekly_refresh)
        self.assertTrue(self.profile.can_refresh_menu())
        
        # Только что обновил меню, бесплатно обновить больше нельзя
        self.profile.last_weekly_refresh = timezone.now()
        self.profile.save()
        self.assertFalse(self.profile.can_refresh_menu())
        
        # Добавляем Premium. С подпиской обновлять можно всегда.
        self.profile.is_subscribed = True
        self.profile.subscription_end = timezone.now().date() + datetime.timedelta(days=30)
        self.profile.save()
        self.assertTrue(self.profile.can_refresh_menu())

    def test_days_until_next_refresh(self):
        """Проверяет корректность расчета оставшихся дней до бесплатного обновления меню."""
        # Устанавливаем дату обновления на 2 дня назад
        self.profile.last_weekly_refresh = timezone.now() - datetime.timedelta(days=2)
        self.profile.save()
        # 7 - 2 = 5 дней осталось
        self.assertEqual(self.profile.days_until_next_refresh(), 5)
        
        # Если прошло больше 7 дней
        self.profile.last_weekly_refresh = timezone.now() - datetime.timedelta(days=10)
        self.profile.save()
        self.assertEqual(self.profile.days_until_next_refresh(), 0)
