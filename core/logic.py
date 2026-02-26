import re

def scale_ingredients(description, multiplier):
    """
    Функция ищет числа в строке состава и умножает их на коэффициент.
    Пример: "Курица 100г" при multiplier=1.5 станет "Курица 150г"
    """
    if not description:
        return ""

    def multiply(match):
        # Находим число в строке
        number = float(match.group(0))
        # Умножаем на множитель и округляем
        new_number = round(number * multiplier)
        # Возвращаем как целое число (строкой)
        return str(int(new_number))

    # Регулярное выражение ищет любые числа в тексте
    scaled_text = re.sub(r"\d+", multiply, description)
    return scaled_text

def calculate_macros(data):
    """
    Универсальный расчет КБЖУ. 
    Принимает либо объект Profile, либо словарь сессии (для гостей).
    """
    
    # 1. Извлекаем данные в зависимости от типа входных данных
    if hasattr(data, 'weight'):
        # Если это объект Profile (доступ через точку)
        w = float(data.weight)
        h = float(data.height)
        a = int(data.age)
        g = data.gender
        activity = float(data.activity)
        goal = data.goal
    else:
        # Если это словарь сессии (доступ через .get())
        w = float(data.get('weight', 0))
        h = float(data.get('height', 0))
        a = int(data.get('age', 0))
        g = data.get('gender', 'male')
        activity = float(data.get('activity', 1.2))
        goal = data.get('goal', 'maintain')

    # 2. Расчет BMR по формуле Миффлина-Сан Жеора
    if g == 'male':
        bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    else:
        bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
    
    # 3. Учет активности (TDEE)
    tdee = bmr * activity
    
    # 4. Учет цели 
    if goal == 'lose':
        tdee *= 0.85 # Дефицит 15%
    elif goal == 'gain':
        tdee *= 1.15 # Профицит 15%
        
    # 5. Расчет БЖУ 
    protein = (tdee * 0.30) / 4
    fat = (tdee * 0.30) / 9
    carbs = (tdee * 0.40) / 4
    
    return {
        'kcal': round(tdee),
        'p': round(protein),
        'f': round(fat),
        'c': round(carbs)
    }