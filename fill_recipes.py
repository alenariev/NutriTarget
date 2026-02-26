
import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nutritarget.settings')
django.setup()

from core.models import Recipe

def seed():
    print("Очистка базы данных от старых рецептов...")
    Recipe.objects.all().delete()

    # Расширенный список базовых рецептов с разными тегами для фото
    recipes_pool = [
        # --- ЗАВТРАКИ ---
        ("Овсяная каша с ягодами", "breakfast", "vegan", 250, 8, 5, 45, "Овсянка 60г, Черника 40г, Сироп топинамбура 10г", "oatmeal,berries,healthy,breakfast"),
        ("Скрэмбл с тостами и зеленью", "breakfast", "vege", 320, 18, 22, 12, "Яйца 3шт, Сливочное масло 10г, Цельнозерновой хлеб 40г", "scrambled-eggs,toast,avocado,breakfast"),
        ("Сырники с медом и сметаной", "breakfast", "vege", 350, 25, 10, 40, "Творог 5% 180г, Рисовая мука 30г, Яйцо 1шт, Мед 15г", "cottage-cheese,pancakes,honey,breakfast"),
        ("Авокадо-тост с яйцом пашот", "breakfast", "vege", 380, 14, 25, 25, "Цельнозерновой хлеб 50г, Авокадо 60г, Яйцо 1шт", "avocado-toast,poached-egg,breakfast"),
        ("Блины на кефире с фруктами", "breakfast", "vege", 290, 10, 8, 45, "Кефир 100мл, Мука 60г, Яйцо 0.5шт, Фрукты 50г", "pancakes,kefir,fruits,breakfast"),
        ("Рисовая каша с орехами", "breakfast", "vegan", 280, 7, 10, 40, "Рис 60г, Миндаль 20г, Растительное молоко 100мл", "rice-porridge,nuts,vegan,breakfast"),
        ("Гранола с йогуртом", "breakfast", "vege", 300, 12, 10, 38, "Гранола 50г, Йогурт 150г, Мед 10г", "granola,yogurt,breakfast"),
        ("Яичница с овощами", "breakfast", "vege", 270, 16, 18, 10, "Яйца 2шт, Помидоры 50г, Перец 30г, Сыр 15г", "fried-eggs,vegetables,cheese,breakfast"),

        # --- ПЕРЕКУСЫ ---
        ("Микс орехов и сухофруктов", "snack", "vegan", 180, 4, 14, 12, "Грецкий орех 20г, Курага 30г, Миндаль 10г", "nuts,dried-fruits,snack"),
        ("Греческий йогурт с семенами чиа", "snack", "vege", 130, 12, 4, 10, "Йогурт 2% 150г, Семена чиа 5г, Ягоды 20г", "greek-yogurt,chia-seeds,berries,snack"),
        ("Яблоко с арахисовой пастой", "snack", "vegan", 210, 5, 12, 22, "Яблоко 150г, Арахисовая паста 15г", "apple,peanut-butter,snack"),
        ("Сырники из рикотты", "snack", "vege", 190, 15, 14, 1, "Рикотта 50г, Яйцо 0.5шт, Мука 10г", "ricotta,cheese-fritters,snack"),
        ("Фруктовый салат", "snack", "vegan", 150, 2, 5, 25, "Яблоко 50г, Банан 50г, Апельсин 50г", "fruit-salad,healthy,snack"),

        # --- ОБЕДЫ ---
        ("Куриная грудка с овощами гриль", "lunch", "all", 420, 45, 12, 35, "Куриная грудка 150г, Брокколи 100г, Перец болгарский 50г, Кабачок 50г", "chicken-breast,grilled-vegetables,healthy,lunch"),
        ("Лосось на пару с киноа", "lunch", "pesca", 510, 35, 22, 40, "Лосось 150г, Киноа 60г, Спаржа 100г", "salmon,quinoa,asparagus,lunch"),
        ("Чечевичный суп-пюре", "lunch", "vegan", 320, 18, 4, 55, "Красная чечевица 80г, Морковь 30г, Лук 20г, Корень сельдерея 30г", "lentil-soup,vegan-soup,vegetables,lunch"),
        ("Говядина с тушеными овощами", "lunch", "all", 450, 30, 22, 30, "Говядина 150г, Картофель 100г, Морковь 50г, Горошек 30г", "beef,stew,vegetables,lunch"),
        ("Креветки с рисом и овощами", "lunch", "pesca", 480, 30, 15, 50, "Креветки 120г, Рис басмати 60г, Брокколи 50г, Морковь 50г", "shrimp,rice,asian-food,lunch"),
        ("Борщ украинский", "lunch", "all", 350, 15, 15, 40, "Говядина 80г, Свёкла 100г, Картофель 50г, Капуста 50г", "borscht,soup,traditional-food,lunch"),
        ("Суп Том Ям с курицей", "lunch", "all", 380, 25, 10, 45, "Курица 100г, Грибы 50г, Кокосовое молоко 80мл, Лемонграсс", "tom-yum,chicken-soup,thai-food,lunch"),

        # --- УЖИНЫ ---
        ("Треска запеченная с лимоном", "dinner", "pesca", 280, 32, 6, 15, "Треска 200г, Лимон 10г, Оливковое масло 5мл", "baked-fish,cod,lemon,dinner"),
        ("Салат с тунцом и авокадо", "dinner", "pesca", 240, 28, 10, 8, "Тунец консервированный 120г, Авокадо 60г, Руккола 50г, Огурец 50г", "tuna-salad,avocado,healthy-salad,dinner"),
        ("Куриные котлеты с овощным пюре", "dinner", "all", 310, 35, 8, 20, "Куриный фарш 150г, Цветная капуста 100г, Брокколи 50г", "chicken-cutlets,vegetable-puree,dinner"),
        ("Творожная запеканка с изюмом", "dinner", "vege", 340, 35, 12, 20, "Творог 2% 200г, Яйцо 1шт, Изюм 30г, Сахарозаменитель", "cottage-cheese-casserole,healthy-dessert,dinner"),
        ("Овощное рагу с нутом", "dinner", "vegan", 210, 6, 8, 30, "Кабачок 100г, Баклажан 100г, Перец 50г, Томаты 80г, Нут 40г", "vegetable-stew,ratatouille,vegan-dinner,dinner"),
        ("Рыба на гриле с овощами", "dinner", "pesca", 300, 30, 10, 20, "Филе белой рыбы 180г, Помидоры черри 50г, Цукини 80г", "grilled-fish,vegetables,dinner"),
        ("Гречневая каша с грибами", "dinner", "vegan", 250, 10, 5, 40, "Гречневая крупа 60г, Грибы шампиньоны 100г, Лук 20г", "buckwheat,mushrooms,vegan-dinner,dinner"),
    ]

    print("Начинаю наполнение базы (создаю ~250+ рецептов)...")
    total_recipes_created = 0

    num_recipes_to_create = max(len(recipes_pool) * 3, 250) 

    for i in range(num_recipes_to_create):
        base_title, m_type, diet, cal, p, f, c, desc, img_tags = random.choice(recipes_pool)
        
        variance = random.uniform(0.9, 1.1) # Небольшое отклонение в КБЖУ
        
        # Комбинируем теги
        all_tags = f"{diet},{m_type},{img_tags},food,recipe,meal,healthy-eating"
        img_url = f"https://source.unsplash.com/800x600/?{all_tags},{i}" # Добавляем 'i' для разнообразия

        Recipe.objects.create(
            title=f"{base_title}",
            meal_type=m_type, 
            diet_type=diet,
            calories=int(cal * variance), 
            protein=int(p * variance), 
            fat=int(f * variance), 
            carbs=int(c * variance), 
            description=desc, 
            image_url=img_url
        )
        total_recipes_created += 1

    print(f"Успех! В базе теперь {total_recipes_created} рецептов.")

if __name__ == "__main__":
    seed()
