# init_db.py
"""
Скрипт полной инициализации проекта "Домашняя Бухгалтерия"
✅ Создаёт базу данных (если нет)
✅ Создаёт таблицы
✅ Заполняет тестовыми данными

Использование:
    python init_db.py
"""

import sys
import os
import psycopg
from dotenv import load_dotenv

# 🔧 Добавляем текущую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(line_buffering=True)

print("🏁 Запуск полной инициализации проекта")
print("=" * 50)

# Загружаем переменные окружения
load_dotenv()

DB_NAME = os.getenv('DB_NAME', 'budget_db')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

print(f"📊 База данных: {DB_NAME}")
print(f"👤 Пользователь: {DB_USER}")
print(f"🌍 Хост: {DB_HOST}:{DB_PORT}")
print("=" * 50)

# === ШАГ 1: Создаём базу данных (если не существует) ===
print("\n📁 ШАГ 1: Проверка/создание базы данных...")

try:
    # Подключаемся к системной БД 'postgres' для создания новой
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname='postgres'  # ← Подключаемся к системной БД
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Проверяем, существует ли база
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    exists = cur.fetchone()
    
    if exists:
        print(f"   ⏭️  База '{DB_NAME}' уже существует")
    else:
        print(f"   🔄 Создание базы '{DB_NAME}'...")
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"   ✅ База '{DB_NAME}' создана!")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ ОШИБКА при создании базы: {e}")
    print("💡 Убедитесь, что PostgreSQL запущен и пароль верный")
    sys.exit(1)

# === ШАГ 2: Создаём таблицы и заполняем данными ===
print("\n📊 ШАГ 2: Создание таблиц и заполнение данными...")

from datetime import date, timedelta
from app import app, db, Category, Transaction, Budget

with app.app_context():
    try:
        # Создаём таблицы
        print("   🔄 Создание таблиц...")
        db.create_all()
        print("   ✅ Таблицы созданы")
        
        # Категории
        print("   🔄 Добавление категорий...")
        default_categories = [
            {'name': 'Зарплата', 'type': 'income', 'icon': 'bi-cash-coin'},
            {'name': 'Еда', 'type': 'expense', 'icon': 'bi-cart'},
            {'name': 'Транспорт', 'type': 'expense', 'icon': 'bi-bus-front'},
            {'name': 'Развлечения', 'type': 'expense', 'icon': 'bi-film'},
            {'name': 'Жильё', 'type': 'expense', 'icon': 'bi-house'},
            {'name': 'Здоровье', 'type': 'expense', 'icon': 'bi-heart-pulse'},
            {'name': 'Подарки', 'type': 'expense', 'icon': 'bi-gift'},
            {'name': 'Другое', 'type': 'expense', 'icon': 'bi-three-dots'},
        ]
        
        categories = {}
        for cat_data in default_categories:
            cat = Category.query.filter_by(name=cat_data['name']).first()
            if not cat:
                cat = Category(**cat_data)
                db.session.add(cat)
                print(f"      ➕ {cat_data['name']}")
            db.session.flush()
            categories[cat_data['name']] = cat
        
        # Транзакции
        print("   🔄 Добавление транзакций...")
        sample_transactions = [
            {'amount': 50000, 'category': 'Зарплата', 'type': 'income', 'date': date.today().replace(day=1), 'comment': 'Аванс'},
            {'amount': 30000, 'category': 'Зарплата', 'type': 'income', 'date': date.today().replace(day=15), 'comment': 'Зарплата'},
            {'amount': 1500, 'category': 'Еда', 'type': 'expense', 'date': date.today() - timedelta(days=1), 'comment': 'Продукты'},
            {'amount': 800, 'category': 'Еда', 'type': 'expense', 'date': date.today() - timedelta(days=3), 'comment': 'Обед'},
            {'amount': 500, 'category': 'Транспорт', 'type': 'expense', 'date': date.today() - timedelta(days=2), 'comment': 'Такси'},
            {'amount': 1200, 'category': 'Транспорт', 'type': 'expense', 'date': date.today().replace(day=1), 'comment': 'Проездной'},
            {'amount': 1000, 'category': 'Развлечения', 'type': 'expense', 'date': date.today() - timedelta(days=4), 'comment': 'Кино'},
            {'amount': 25000, 'category': 'Жильё', 'type': 'expense', 'date': date.today().replace(day=5), 'comment': 'Аренда'},
            {'amount': 2000, 'category': 'Здоровье', 'type': 'expense', 'date': date.today() - timedelta(days=7), 'comment': 'Витамины'},
            {'amount': 3000, 'category': 'Подарки', 'type': 'expense', 'date': date.today() - timedelta(days=8), 'comment': 'На ДР'},
        ]
        
        for t_data in sample_transactions:
            exists = Transaction.query.filter_by(
                amount=t_data['amount'],
                category_id=categories[t_data['category']].id,
                transaction_date=t_data['date']
            ).first()
            if not exists:
                t = Transaction(
                    amount=t_data['amount'],
                    category_id=categories[t_data['category']].id,
                    type=t_data['type'],
                    comment=t_data.get('comment'),
                    transaction_date=t_data['date']
                )
                db.session.add(t)
        
        # Бюджеты
        print("   🔄 Установка бюджетов...")
        now = date.today()
        sample_budgets = [
            {'category': 'Еда', 'limit': 10000},
            {'category': 'Транспорт', 'limit': 3000},
            {'category': 'Развлечения', 'limit': 5000},
            {'category': 'Жильё', 'limit': 30000},
        ]
        
        for b_data in sample_budgets:
            cat = categories[b_data['category']]
            budget = Budget.query.filter_by(
                category_id=cat.id,
                month=now.month,
                year=now.year
            ).first()
            if not budget:
                budget = Budget(
                    category_id=cat.id,
                    limit_amount=b_data['limit'],
                    month=now.month,
                    year=now.year
                )
                db.session.add(budget)
                print(f"      ➕ {b_data['category']}: {b_data['limit']} ₽")
        
        db.session.commit()
        
        print("\n" + "=" * 50)
        print("🎉 ГОТОВО! Проект полностью инициализирован")
        print("=" * 50)
        print(f"📊 Статистика:")
        print(f"   • Категорий: {Category.query.count()}")
        print(f"   • Транзакций: {Transaction.query.count()}")
        print(f"   • Бюджетов: {Budget.query.count()}")
        print(f"\n🚀 Запуск приложения:")
        print(f"   python app.py")
        print(f"\n🌐 Открой в браузере:")
        print(f"   http://127.0.0.1:5000")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        db.session.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)