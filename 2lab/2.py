import asyncio
import os
import json
import logging
import aiohttp
import base64
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, BotCommand, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LEAKCHECK_API_KEY = os.getenv("LEAKCHECK_API_KEY")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")
IPQS_API_KEY = os.getenv("IPQS_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SUBSCRIBERS_FILE = "subscribers.json"
HISTORY_FILE = "history.json"
NODE_LOADS_FILE = "node_loads.json"

def load_node_loads():
    """Загружает состояние узлов из файла"""
    try:
        if os.path.exists(NODE_LOADS_FILE):
            with open(NODE_LOADS_FILE, "r") as file:
                node_data = json.load(file)
                for node in NODES:
                    node_info = node_data.get(str(node.node_id))
                    if node_info:
                        node.load = node_info["load"]
                        node.last_update = datetime.strptime(
                            node_info["last_update"], "%Y-%m-%d %H:%M:%S"
                        )
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных о загрузке узлов: {e}")

def save_node_loads():
    """Сохраняет текущее состояние узлов в файл"""
    try:
        node_data = {
            str(node.node_id): {
                "load": node.load,
                "last_update": node.last_update.strftime("%Y-%m-%d %H:%M:%S")
            }
            for node in NODES
        }
        with open(NODE_LOADS_FILE, "w") as file:
            json.dump(node_data, file, indent=4)
    except Exception as e:
        logging.error(f"Ошибка при сохранении данных о загрузке узлов: {e}")


def load_subscribers():
    try:
        if os.path.exists(SUBSCRIBERS_FILE):
            with open(SUBSCRIBERS_FILE, "r") as file:
                return json.load(file)
        return []
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Ошибка загрузки подписчиков: {e}")
        return []


def save_subscribers(subscribers):
    try:
        with open(SUBSCRIBERS_FILE, "w") as file:
            json.dump(subscribers, file, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения подписчиков: {e}")


def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as file:
                return json.load(file)
        return {}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Ошибка загрузки истории: {e}")
        return {}


def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as file:
            json.dump(history, file, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения истории: {e}")


def add_to_history(user_id, data_type, value):
    history = load_history()
    user_id_str = str(user_id)

    if user_id_str not in history:
        history[user_id_str] = {"email": [], "ip": [], "phone": []}

    if value not in history[user_id_str][data_type]:
        history[user_id_str][data_type].append(value)

    save_history(history)


# Устанавливаем команды, доступные в боте
async def set_bot_commands():
    """Устанавливаем команды, доступные в боте"""
    commands = [
        BotCommand(command="/start", description="Начать работу с ботом"),
        BotCommand(command="/status", description="Показать статус подписки и историю"),
        BotCommand(command="/node_status", description="Статус загрузки узлов"),
        BotCommand(command="/check", description="Проверить данные на утечку")
    ]
    await bot.set_my_commands(commands)
    logging.info("Установлены команды /start, /status, /node_status и /check")


start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔔 Подписаться на уведомления"), KeyboardButton(text="🚫 Отписаться от уведомлений")],
        [KeyboardButton(text="💡 Советы по безопасности")],
        [KeyboardButton(text="🔍 Проверка URL")],
        [KeyboardButton(text="📧 Проверка Email")],
        [KeyboardButton(text="📱 Проверка телефона")],
        [KeyboardButton(text="🌐 Проверка IP")],
        [KeyboardButton(text="🔐 2FA Info")]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: Message):
    try:
        await message.answer(
            "🔐 Привет! Я бот для защиты персональных данных.\n"
            "Выберите одну из опций для проверки:\n",
            reply_markup=start_keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка в обработчике /start: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")


@dp.message(lambda message: message.text == "🔔 Подписаться на уведомления")
async def subscribe(message: Message):
    try:
        subscribers = load_subscribers()
        if message.from_user.id not in subscribers:
            subscribers.append(message.from_user.id)
            save_subscribers(subscribers)
            await message.answer("✅ Вы подписались на уведомления о новых утечках!")
        else:
            await message.answer("⚠️ Вы уже подписаны на уведомления.")
    except Exception as e:
        logging.error(f"Ошибка при подписке: {e}")
        await message.answer("❌ Произошла ошибка при подписке. Попробуйте позже.")


@dp.message(lambda message: message.text == "🚫 Отписаться от уведомлений")
async def unsubscribe(message: Message):
    try:
        subscribers = load_subscribers()
        if message.from_user.id in subscribers:
            subscribers.remove(message.from_user.id)
            save_subscribers(subscribers)
            await message.answer("✅ Вы отписались от уведомлений.")
        else:
            await message.answer("⚠️ Вы не были подписаны.")
    except Exception as e:
        logging.error(f"Ошибка при отписке: {e}")
        await message.answer("❌ Произошла ошибка при отписке. Попробуйте позже.")


@dp.message(Command("status"))
async def status(message: Message):
    logging.info("Команда /status получена")
    subscribers = load_subscribers()
    history = load_history()
    user_id_str = str(message.from_user.id)

    is_subscribed = "✅ Подписаны" if message.from_user.id in subscribers else "❌ Не подписаны"

    user_history = history.get(user_id_str, {"email": [], "ip": [], "phone": []})

    email_list = "\n".join(user_history["email"]) if user_history["email"] else "Нет данных"
    ip_list = "\n".join(user_history["ip"]) if user_history["ip"] else "Нет данных"
    phone_list = "\n".join(user_history["phone"]) if user_history["phone"] else "Нет данных"

    response = f"📊 Ваш статус:\n🔔 Подписка: {is_subscribed}\n\n📧 История email:\n{email_list}\n\n🌐 История IP:\n{ip_list}\n\n📱 История телефонов:\n{phone_list}"

    await message.answer(response)


@dp.message(lambda message: message.text == "💡 Советы по безопасности")
async def send_tips(message: Message):
    tips = [
        "✅ Используй сложные пароли и менеджеры паролей.",
        "✅ Включи двухфакторную аутентификацию (2FA).",
        "✅ Никогда не переходи по подозрительным ссылкам.",
        "✅ Регулярно проверяй свои данные на утечки.",
        "✅ Не устанавливай сомнительные приложения."
    ]
    await message.answer("\n".join(tips))


# Обработчики для проверки данных (URL, email, телефон, IP)
@dp.message(lambda message: message.text == "🔍 Проверка URL")
async def check_url(message: Message):
    await message.answer("Введите URL для проверки:")


@dp.message(lambda message: message.text == "📧 Проверка Email")
async def check_email(message: Message):
    await message.answer("Введите email для проверки:")


@dp.message(lambda message: message.text == "📱 Проверка телефона")
async def check_phone(message: Message):
    await message.answer("Введите номер телефона для проверки:")


@dp.message(lambda message: message.text == "🌐 Проверка IP")
async def check_ip(message: Message):
    await message.answer("Введите IP-адрес для проверки:")

class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.load = 0  # Текущая нагрузка
        self.max_load = 100  # Максимальная нагрузка
        self.last_update = datetime.now()

    def update_load(self, increment=1):
        """Обновляет нагрузку на узле"""
        self.load += increment
        if self.load > self.max_load:
            self.load = self.max_load
        self.last_update = datetime.now()

    def decrease_load(self, decrement=1):
        """Уменьшает нагрузку на узле"""
        self.load -= decrement
        if self.load < 0:
            self.load = 0
        self.last_update = datetime.now()

    def get_status(self):
        """Возвращает статус узла в виде словаря"""
        return {
            "node_id": self.node_id,
            "current_load": self.load,
            "max_load": self.max_load,
            "last_update": self.last_update.strftime("%Y-%m-%d %H:%M:%S")
        }

# Создаем список узлов
NODES = [Node(i) for i in range(3)]

def select_node():
    """Выбирает узел с наименьшей нагрузкой"""
    return min(NODES, key=lambda node: node.load)

@dp.message(Command("node_status"))
async def node_status(message: types.Message):
    """Обработчик команды /node_status"""
    try:
        status_text = "📊 Статус узлов:\n\n"
        for node in NODES:
            status = node.get_status()
            status_text += (
                f"Узел {status['node_id']}:\n"
                f"Загрузка: {status['current_load']}%\n"
                f"Последнее обновление: {status['last_update']}\n\n"
            )
        
        await message.answer(status_text)
    except Exception as e:
        logging.error(f"Ошибка при получении статуса узлов: {e}")
        await message.answer("❌ Произошла ошибка при получении статуса узлов")

async def check_data_breach(email):
    """Проверяет email на наличие в утечках"""
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        # Проверяем данные через LeakCheck API
        url = f"https://leakcheck.io/api?key={LEAKCHECK_API_KEY}&check={email}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("found"):
                        return True
                    return False
                else:
                    logging.error("Ошибка при проверке email")
                    return False
    except Exception as e:
        logging.error(f"Ошибка при проверке email: {e}")
        return False

@dp.message(lambda message: message.text)
async def handle_data_input(message: Message):
    text = message.text.strip()
    
    # Проверка email
    if "@" in text:
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        is_breached = await check_data_breach(text)
        
        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        if is_breached:
            await message.answer(f"⚠️ Этот email найден в базе утечек!")
        else:
            await message.answer(f"✅ Email {text} не найден в утечках.")
    
    # Проверка телефона
    elif text.isdigit() and len(text) >= 10:
        await message.answer("� Телефон проверяется...")
    
    # Проверка URL
    elif text.startswith("http"):
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        safety_message = await check_url_virustotal(text)
        
        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        await message.answer(safety_message)
    
    # Проверка IP
    elif text.count(".") == 3 and all(part.isdigit() for part in text.split(".")):
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        result = await check_ip_reputation(text)
        
        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        await message.answer(result)
    else:
        await message.answer("❌ Пожалуйста, введите корректные данные для проверки.")

# Проверка URL через VirusTotal API
async def check_url_virustotal(url):
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        async with aiohttp.ClientSession() as session:
            url = f"https://www.virustotal.com/api/v3/urls"
            headers = {"x-apikey": VIRUSTOTAL_API_KEY}
            data = {"url": url}
            
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("data", {}).get("attributes", {}).get("last_analysis_stats", {}).get("malicious") > 0:
                        result_text = "⚠️ URL может быть вредоносным!"
                    else:
                        result_text = "✅ URL безопасен"
                else:
                    result_text = "❌ Ошибка при проверке URL"

        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        return result_text
    except Exception as e:
        logging.error(f"Ошибка при проверке URL: {e}")
        return "❌ Ошибка при проверке URL"

# Проверка IP через IPQS API
async def check_ip_reputation(ip_address):
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = select_node()
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        async with aiohttp.ClientSession() as session:
            url = f"https://ipqualityscore.com/api/json/ip/{IPQS_API_KEY}/{ip_address}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success", False):
                        risk = data.get("fraud_score", 0)
                        if risk > 80:
                            result_text = f"❌ IP-адрес {ip_address} имеет высокий риск: {risk}/100."
                        elif risk > 50:
                            result_text = f"⚠️ IP-адрес {ip_address} имеет средний риск: {risk}/100."
                        else:
                            result_text = f"✅ IP-адрес {ip_address} безопасен: {risk}/100."
                    else:
                        result_text = "❌ Ошибка при проверке IP-адреса"
                else:
                    result_text = "❌ Ошибка при проверке IP-адреса"

        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        return result_text
    except Exception as e:
        logging.error(f"Ошибка при проверке IP-адреса: {e}")
        return "❌ Ошибка при проверке IP-адреса"

async def main():
    logging.info("Запуск бота...")
    await set_bot_commands()
    logging.info("Бот зарегистрировал команды.")
    await dp.start_polling(bot)


# Алгоритм "Эхо"
async def echo_algorithm(node_id, load_data):
    """Имитация волнового алгоритма 'Эхо' для сбора данных о загрузке узлов"""
    node_loads = load_node_loads()
    node_loads[node_id] = load_data
    save_node_loads(node_loads)
    logging.info(f"Собрана информация о загрузке узла {node_id}: {load_data}")

    # После сбора данных алгоритм принимает решение о балансировке
    await make_balancing_decision(node_loads)

    # Функция для принятия решения о балансировке
async def make_balancing_decision(node_loads):
    """Принятие решения о переносе объекта на основе текущих данных о загрузке"""
    # Пример логики балансировки: переносим объект с самого загруженного узла на менее загруженный
    sorted_nodes = sorted(node_loads.items(), key=lambda x: x[1], reverse=True)
    most_loaded_node = sorted_nodes[0]
    least_loaded_node = sorted_nodes[-1]

    # Принятие решения о переносе
    logging.info(f"Балансировка: перенос объекта с узла {most_loaded_node[0]} на узел {least_loaded_node[0]}")
    
    # Логика переноса объекта (например, отправка сообщения)
    await bot.send_message(most_loaded_node[0], f"🔄 Ваш узел перегружен, объект будет перемещен.")
    await bot.send_message(least_loaded_node[0], f"💻 Вы получили новый объект для обработки.")

if __name__ == "__main__":
    asyncio.run(main())
