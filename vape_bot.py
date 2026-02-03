
import sqlite3
import logging
from datetime import datetime

import telebot
from telebot import types

# ==================== НАСТРОЙКИ ====================
ADMIN_IDS = [2001042541, 6219861415, 7301378079]
TOKEN = "8543678011:AAHRBzthpkn6Ihd2xZdwIiSk7HfFltJmWRY"
DATABASE_NAME = "vape_shop.db"

# Инициализация бота
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище для данных при добавлении товара
adding_products = {}

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
        self.create_tables()
        print("✅ База данных подключена")
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Товары
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                name TEXT,
                description TEXT,
                price REAL,
                photo_id TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Заказы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                total_price REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Оплата
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def add_product(self, category, name, description, price, photo_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO products (category, name, description, price, photo_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (category, name, description, price, photo_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_products(self, category):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM products WHERE category = ? AND is_active = 1', (category,))
        return cursor.fetchall()
    
    def get_product(self, product_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        return cursor.fetchone()
    
    def create_order(self, user_id, product_id):
        product = self.get_product(product_id)
        if product:
            total_price = product[4]  # price
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO orders (user_id, product_id, total_price)
                VALUES (?, ?, ?)
            ''', (user_id, product_id, total_price))
            self.conn.commit()
            return cursor.lastrowid, total_price
        return None, 0
    
    def add_payment_link(self, link):
        cursor = self.conn.cursor()
        # Деактивируем старые ссылки
        cursor.execute('UPDATE payment_links SET is_active = 0')
        # Добавляем новую
        cursor.execute('INSERT INTO payment_links (link) VALUES (?)', (link,))
        self.conn.commit()
    
    def get_payment_link(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT link FROM payment_links WHERE is_active = 1 LIMIT 1')
        row = cursor.fetchone()
        return row[0] if row else None

# Инициализация базы данных
db = Database()

# ==================== КЛАВИАТУРЫ ====================
def main_menu(user_id):
    """Главное меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📂 Каталог", "ℹ️ Инструкция")
    
    if user_id in ADMIN_IDS:
        markup.row("⚙️ Админ-панель")
    
    return markup

def admin_menu():
    """Меню админа"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить товар", "💰 Оплата")
    markup.row("📦 Заказы", "🔙 В меню")
    return markup

def categories_keyboard():
    """Кнопки категорий"""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💧 Жидкости", callback_data="cat_liquids"),
        types.InlineKeyboardButton("💨 Устройства", callback_data="cat_devices")
    )
    markup.row(
        types.InlineKeyboardButton("🔋 Картриджи", callback_data="cat_cartridges")
    )
    markup.row(types.InlineKeyboardButton("🔙 В меню", callback_data="back_main"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == 'add_devices')
def handle_add_devices(call):
    """Обработка выбора устройств для добавления товара"""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔄 Многоразовые", callback_data="add_reusable"),
        types.InlineKeyboardButton("⚡ Одноразовые", callback_data="add_disposable")
    )
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_add"))
    
    bot.edit_message_text(
        "📱 <b>Выберите тип устройств:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

def devices_keyboard():
    """Кнопки выбора типа устройств"""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🔄 Многоразовые устройства", callback_data="cat_reusable"),
        types.InlineKeyboardButton("⚡ Одноразовые устройства", callback_data="cat_disposable")
    )
    markup.row(types.InlineKeyboardButton("🔙 В каталог", callback_data="back_catalog"))
    return markup

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда /start"""
    user = message.from_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    text = (
        "👋 <b>Добро пожаловать в магазин 'Ингаляторов'!</b>\n\n"
        "🔞 <i>Внимание: только для лиц 18+</i>\n"
        "🤫 <i>Важно: маме не рассказывать!</i>\n\n"
        "Используйте кнопки меню:"
    )
    
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu(user.id)
    )

@bot.message_handler(func=lambda m: m.text == "📂 Каталог")
def show_catalog(message):
    """Показать каталог"""
    bot.send_message(
        message.chat.id,
        "📂 <b>Выберите категорию:</b>",
        reply_markup=categories_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ Инструкция")
def show_instructions(message):
    """Показать инструкцию"""
    text = (
        "📋 <b>ИНСТРУКЦИЯ ПО ПОКУПКЕ</b>\n\n"
        "1️⃣ <b>Выберите товар</b> в каталоге\n"
        "2️⃣ <b>Нажмите 'Купить'</b>\n"
        "3️⃣ <b>Оплатите</b> по ссылке\n"
        "4️⃣ <b>Ждите проверки</b> (15 мин)\n"
        "5️⃣ <b>Менеджер свяжется</b> с вами\n"
        "6️⃣ <b>Назначьте встречу</b>\n"
        "7️⃣ <b>Получите товар!</b>\n\n"
        "⚠️ <b>ВАЖНО:</b>\n"
        "• Только для совершеннолетних\n"
        "• Сохраняйте анонимность\n"
        "• Не сообщайте о покупках"
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
def admin_panel(message):
    """Показать админ-панель"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен.")
        return
    
    bot.send_message(
        message.chat.id,
        "⚙️ <b>Админ-панель</b>\nВыберите действие:",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == "➕ Добавить товар")
def add_product_start(message):
    """Начать добавление товара"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("💧 Жидкости", callback_data="add_liquids"),
        types.InlineKeyboardButton("💨 Устройства", callback_data="add_devices")
    )
    markup.row(
        types.InlineKeyboardButton("🔋 Картриджи", callback_data="add_cartridges")
    )
    markup.row(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_add"))
    
    bot.send_message(
        message.chat.id,
        "➕ <b>Добавление товара</b>\nВыберите категорию:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_'))
def handle_add_category(call):
    """Обработка выбора категории"""
    if call.data == "cancel_add":
        bot.edit_message_text(
            "❌ Добавление отменено.",
            call.message.chat.id,
            call.message.message_id
        )
        return
    
    category = call.data.replace("add_", "")
    
    # Сохраняем данные в глобальном словаре
    adding_products[call.from_user.id] = {
        'step': 'name',
        'category': category
    }
    
    bot.edit_message_text(
        f"✅ Категория выбрана\n\n📝 Введите <b>название товара</b>:",
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(func=lambda m: m.from_user.id in adding_products)
def handle_product_data(message):
    """Обработка данных товара"""
    user_id = message.from_user.id
    data = adding_products.get(user_id)
    
    if not data:
        return
    
    if data['step'] == 'name':
        # Сохраняем название
        data['name'] = message.text
        data['step'] = 'description'
        
        bot.send_message(
            message.chat.id,
            "✅ Название сохранено!\n\n📝 Введите <b>описание товара</b>:"
        )
    
    elif data['step'] == 'description':
        # Сохраняем описание
        data['description'] = message.text
        data['step'] = 'price'
        
        bot.send_message(
            message.chat.id,
            "✅ Описание сохранено!\n\n💰 Введите <b>цену</b> (только число):"
        )
    
    elif data['step'] == 'price':
        try:
            price = float(message.text)
            
            # Сохраняем товар в базу
            product_id = db.add_product(
                data['category'],
                data['name'],
                data['description'],
                price
            )
            
            # Удаляем данные пользователя
            del adding_products[user_id]
            
            # Сообщаем об успехе
            category_names = {
                'liquids': '💧 Жидкости',
                'reusable': '🔄 Многоразовые',
                'disposable': '⚡ Одноразовые',
                'cartridges': '🔋 Картриджи'
            }
            
            category_display = category_names.get(data['category'], data['category'])
            
            bot.send_message(
                message.chat.id,
                f"✅ <b>Товар успешно добавлен!</b>\n\n"
                f"🆔 ID: {product_id}\n"
                f"🏷️ Название: {data['name']}\n"
                f"📝 Описание: {data['description']}\n"
                f"💰 Цена: {price} руб.\n"
                f"📂 Категория: {category_display}",
                reply_markup=admin_menu()
            )
            
        except ValueError:
            bot.send_message(message.chat.id, "❌ Неверная цена! Введите число:")
    else:
        # Неизвестный шаг
        del adding_products[user_id]
        bot.send_message(
            message.chat.id,
            "❌ Ошибка процесса. Начните заново.",
            reply_markup=admin_menu()
        )

@bot.message_handler(func=lambda m: m.text == "💰 Оплата")
def add_payment(message):
    """Добавить ссылку оплаты"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    bot.send_message(
        message.chat.id,
        "💰 <b>Добавление ссылки оплаты</b>\n\n"
        "Отправьте ссылку (начинается с https://):\n\n"
        "Пример:\n"
        "<code>https://qiwi.com/n/номер</code>\n"
        "или\n"
        "<code>https://t.me/аккаунт</code>"
    )

@bot.message_handler(func=lambda m: m.text and m.text.startswith("https://"))
def handle_payment_link(message):
    """Обработка ссылки оплаты"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    db.add_payment_link(message.text)
    bot.send_message(
        message.chat.id,
        f"✅ Ссылка оплаты добавлена!\n{message.text[:50]}...",
        reply_markup=admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📦 Заказы")
def show_orders(message):
    """Показать заказы"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT o.id, u.first_name, p.name, o.total_price, o.created_at
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        JOIN products p ON o.product_id = p.id
        ORDER BY o.created_at DESC
        LIMIT 10
    ''')
    
    orders = cursor.fetchall()
    
    if not orders:
        bot.send_message(message.chat.id, "📭 Заказов пока нет.")
        return
    
    text = "📦 <b>Последние заказы:</b>\n\n"
    total = 0
    
    for order in orders:
        text += (
            f"🆔 #{order[0]}\n"
            f"👤 {order[1]}\n"
            f"📦 {order[2]}\n"
            f"💰 {order[3]} руб.\n"
            f"📅 {order[4][:10]}\n"
            f"{'―'*20}\n"
        )
        total += order[3]
    
    text += f"\n💰 <b>Общая сумма: {total} руб.</b>"
    
    bot.send_message(message.chat.id, text)

# ==================== КАТАЛОГ И ПОКУПКА ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category(call):
    """Обработка выбора категории"""
    category = call.data.replace("cat_", "")
    
    # Если выбрали "Устройства" - показываем подкатегории
    if category == "devices":
        bot.edit_message_text(
            "📱 <b>Выберите тип устройств:</b>",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=devices_keyboard()
        )
        return
    
    # Для остальных категорий - показываем товары
    products = db.get_products(category)
    
    if not products:
        bot.answer_callback_query(call.id, "Товаров пока нет")
        return
    
    # Красивые названия категорий для отображения
    category_names = {
        'liquids': '💧 Жидкости',
        'reusable': '🔄 Многоразовые устройства',
        'disposable': '⚡ Одноразовые устройства',
        'cartridges': '🔋 Картриджи'
    }
    
    category_display = category_names.get(category, category)
    
    markup = types.InlineKeyboardMarkup()
    for product in products:
        btn_text = f"{product[2]} - {product[4]} руб."
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"view_{product[0]}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_catalog"))
    
    bot.edit_message_text(
        f"📦 <b>Товары ({category_display}):</b>\n\nВыберите товар:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def show_product(call):
    """Показать товар"""
    product_id = int(call.data.replace("view_", ""))
    product = db.get_product(product_id)
    
    if not product:
        bot.answer_callback_query(call.id, "Товар не найден")
        return
    
    text = (
        f"🛒 <b>{product[2]}</b>\n\n"
        f"📝 {product[3]}\n\n"
        f"💰 <b>Цена: {product[4]} руб.</b>\n\n"
        "Хотите купить этот товар?"
    )
    
    markup = types.InlineKeyboardMarkup()
    # Определяем, куда ведет кнопка "Назад"
    back_target = f"cat_{product[1]}"
    if product[1] in ['reusable', 'disposable']:
        back_target = "cat_devices"

    markup.row(
        types.InlineKeyboardButton("✅ Купить", callback_data=f"buy_{product_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data=back_target)
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def process_buy(call):
    """Обработка покупки"""
    product_id = int(call.data.replace("buy_", ""))
    user_id = call.from_user.id
    
    # Создаем заказ
    order_id, total_price = db.create_order(user_id, product_id)
    
    if not order_id:
        bot.answer_callback_query(call.id, "Ошибка при создании заказа")
        return
    
    # Получаем ссылку оплаты
    payment_link = db.get_payment_link()
    
    text = (
        "📋 <b>ИНСТРУКЦИЯ ПО ОПЛАТЕ</b>\n\n"
        "1️⃣ Нажмите на кнопку 'Оплатить'\n"
        "2️⃣ Переведите сумму заказа\n"
        "3️⃣ Ждите проверки оплаты\n"
        "4️⃣ Ждите сообщения от менеджера (там вы назначите время и день встречи)\n"
        "5️⃣ Радоваться покупке и маме не рассказывать!\n\n"
        f"💰 <b>Сумма: {total_price} руб.</b>\n"
        f"📦 <b>Заказ: #{order_id}</b>"
    )
    
    markup = types.InlineKeyboardMarkup()
    
    if payment_link:
        link = payment_link.replace("{amount}", str(total_price))
        markup.add(types.InlineKeyboardButton("💰 Оплатить", url=link))
    
    markup.add(types.InlineKeyboardButton("🔙 В каталог", callback_data="back_catalog"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ==================== НАВИГАЦИЯ ====================
@bot.callback_query_handler(func=lambda call: call.data == 'back_main')
def back_to_main(call):
    """Назад в главное меню"""
    bot.answer_callback_query(call.id)
    start_command(call.message)

@bot.callback_query_handler(func=lambda call: call.data == 'back_catalog')
def back_to_catalog(call):
    """Назад в каталог"""
    bot.answer_callback_query(call.id)
    show_catalog(call.message)

@bot.message_handler(func=lambda m: m.text == "🔙 В меню")
def back_to_main_menu(message):
    """Назад в главное меню"""
    start_command(message)

@bot.message_handler(func=lambda m: True)
def handle_other_messages(message):
    """Обработка других сообщений"""
    bot.send_message(
        message.chat.id,
        "Используйте кнопки меню для навигации.",
        reply_markup=main_menu(message.from_user.id)
    )

# ==================== ЗАПУСК БОТА ====================
def main():
    """Запуск бота"""
    print("=" * 60)
    print("🚀 ТЕЛЕГРАМ БОТ ДЛЯ ПРОДАЖИ 'ИНГАЛЯТОРОВ'")
    print("=" * 60)
    print(f"👑 Админы: {ADMIN_IDS}")
    print("💻 Windows | Python 3.14")
    print("✅ Бот запущен!")
    print("📩 Ожидание сообщений...")
    print("=" * 60)
    
    bot.infinity_polling()

if __name__ == "__main__":
    main()
