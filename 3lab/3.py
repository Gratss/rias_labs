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
import random

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


def add_to_history(user_id: int, data_type: str, value: str):
    """Добавляет запись в историю пользователя"""
    try:
        user_id_str = str(user_id)
        
        # Создаем структуру, если её нет
        if user_id_str not in history:
            history[user_id_str] = {}
        
        if data_type not in history[user_id_str]:
            history[user_id_str][data_type] = []
        
        # Добавляем значение, если его еще нет
        if value not in history[user_id_str][data_type]:
            history[user_id_str][data_type].append(value)
            save_history()
    except Exception as e:
        logging.error(f"Ошибка при добавлении в историю: {e}")


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
        self.neighbors = []  # Список соседних узлов
        self.visited = False  # Флаг для волнового алгоритма
        self.distance = float('inf')  # Расстояние до центрального узла

    def update_load(self, increment=1):
        self.load = min(self.max_load, self.load + increment)
        self.last_update = datetime.now()
        save_node_loads()

    def decrease_load(self, decrement=1):
        self.load = max(0, self.load - decrement)
        self.last_update = datetime.now()
        save_node_loads()

    def get_status(self):
        return {
            'node_id': self.node_id,
            'load': self.load,
            'max_load': self.max_load,
            'last_update': self.last_update.strftime("%Y-%m-%d %H:%M:%S")
        }

# Создаем список узлов
NODES = [Node(i) for i in range(3)]

# Функция для инициализации сети
async def initialize_network():
    NODES[0].neighbors = [NODES[1], NODES[2]]
    NODES[1].neighbors = [NODES[0], NODES[2]]
    NODES[2].neighbors = [NODES[0], NODES[1]]

# Волновой алгоритм Финна для сбора данных о загрузке
async def finn_wave_algorithm(source_node):
    logging.info(f"Запуск волнового алгоритма от узла {source_node.node_id}")
    # Сбрасываем флаги посещения
    for node in NODES:
        node.visited = False
        node.distance = float('inf')
    
    source_node.visited = True
    source_node.distance = 0
    
    # Очередь для обработки узлов
    queue = [source_node]
    
    while queue:
        current_node = queue.pop(0)
        logging.info(f"Обработка узла {current_node.node_id} с нагрузкой {current_node.load}")
        
        # Обновляем данные о загрузке
        current_node.update_load()
        
        # Передаем информацию соседям
        for neighbor in current_node.neighbors:
            if not neighbor.visited:
                neighbor.visited = True
                neighbor.distance = current_node.distance + 1
                queue.append(neighbor)
                logging.info(f"Передача данных от узла {current_node.node_id} к узлу {neighbor.node_id}")
                
                # Обновляем данные о загрузке у соседа
                neighbor.update_load()
                
    # Логируем итоговое состояние узлов
    for node in NODES:
        logging.info(f"Итоговое состояние узла {node.node_id}: нагрузка {node.load}")
    
    # Возвращаем собранную информацию
    return [node.get_status() for node in NODES]

# Централизованное принятие решения о балансировке
async def make_balancing_decision(node_loads):
    logging.info("Начало процесса принятия решения о балансировке")
    
    # Находим узел с максимальной нагрузкой
    max_load_node = max(node_loads, key=lambda x: x['load'])
    logging.info(f"Узел с максимальной нагрузкой: {max_load_node['node_id']} ({max_load_node['load']}%)")
    
    # Находим узел с минимальной нагрузкой
    min_load_node = min(node_loads, key=lambda x: x['load'])
    logging.info(f"Узел с минимальной нагрузкой: {min_load_node['node_id']} ({min_load_node['load']}%)")
    
    # Проверяем, нужно ли переносить задачу
    if max_load_node['load'] > 70 and min_load_node['load'] < 30:
        logging.info("Превышены пороги нагрузки - требуется перенос задачи")
        
        # Имитация переноса задачи
        max_load_node = [node for node in NODES if node.node_id == max_load_node['node_id']][0]
        min_load_node = [node for node in NODES if node.node_id == min_load_node['node_id']][0]
        
        # Переносим задачу
        max_load_node.decrease_load(10)
        min_load_node.update_load(10)
        
        logging.info(f"Перенос 10% нагрузки с узла {max_load_node.node_id} на узел {min_load_node.node_id}")
        
        return {
            'action': 'transfer',
            'from_node': max_load_node.node_id,
            'to_node': min_load_node.node_id,
            'load_transferred': 10
        }
    else:
        logging.info("Пороги нагрузки не превышены - нет необходимости в переносе")
    
    return {'action': 'no_action'}

# Периодическая проверка балансировки
async def periodic_balancing():
    while True:
        try:
            # Выбираем случайный узел как источник волны
            source_node = random.choice(NODES)
            
            # Запускаем волновой алгоритм
            node_loads = await finn_wave_algorithm(source_node)
            
            # Принимаем решение о балансировке
            decision = await make_balancing_decision(node_loads)
            
            if decision['action'] == 'transfer':
                logging.info(f"Перенос задачи с узла {decision['from_node']} на узел {decision['to_node']}")
            
        except Exception as e:
            logging.error(f"Ошибка при балансировке: {e}")
            
        # Ждем перед следующей проверкой
        await asyncio.sleep(60)  # Проверяем каждую минуту

@dp.message(Command("node_status"))
async def node_status(message: types.Message):
    """Обработчик команды /node_status"""
    try:
        status_text = "📊 Статус узлов:\n\n"
        for node in NODES:
            status = node.get_status()
            status_text += (
                f"Узел {status['node_id']}:\n"
                f"Загрузка: {status['load']}%\n"
                f"Последнее обновление: {status['last_update']}\n\n"
            )
        
        await message.answer(status_text)
    except Exception as e:
        logging.error(f"Ошибка при получении статуса узлов: {e}")
        await message.answer("❌ Произошла ошибка при получении статуса узлов")

async def check_data_breach(email):
    """Проверяет email на наличие в утечках через LeakCheck API"""
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = min(NODES, key=lambda node: node.load)
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        # Проверка через LeakCheck API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://leakcheck.io/api/v2/search",
                params={"key": LEAKCHECK_API_KEY, "query": email}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success", False):
                        return {
                            'found': data.get("found", False),
                            'sources': data.get("sources", [])
                        }
                    else:
                        return {'error': "Ошибка при проверке через LeakCheck API"}
                else:
                    return {'error': "Ошибка при проверке через LeakCheck API"}
    except Exception as e:
        logging.error(f"Ошибка при проверке утечек: {e}")
        return {'error': str(e)}

@dp.message()
async def handle_data_input(message: Message):
    """Обработчик введенных данных"""
    text = message.text.strip()
    
    # Проверка email
    if "@" in text:
        await message.answer("📧 Проверяется email...")
        result = await check_data_breach(text)
        if 'error' in result:
            await message.answer(f"❌ Ошибка при проверке: {result['error']}")
        else:
            if result['found']:
                sources = ", ".join(result['sources'])
                await message.answer(
                    f"⚠️ Этот email найден в утечках!\n"
                    f"Источники: {sources}\n"
                    f"Рекомендуем сменить пароль!"
                )
            else:
                await message.answer("✅ Этот email не найден в утечках")
        
        # Сохраняем историю
        add_to_history(message.from_user.id, "email", text)
    
    # Проверка телефона
    elif text.isdigit() and len(text) >= 10:
        await message.answer("📞 Телефон проверяется...")
        # Здесь должна быть реализация проверки телефона
        await message.answer("⚠️ Проверка телефона временно недоступна")
    
    # Проверка URL
    elif text.startswith("http"):
        await message.answer("🌐 URL проверяется...")
        result = await check_url_virustotal(text)
        
        if isinstance(result, dict):
            if result['malicious']:
                await message.answer(
                    f"⚠️ URL может быть вредоносным!\n"
                    f"Репутация: {result['reputation']}%\n"
                    f"Проверок: {result['total_checks']}\n"
                    f"Положительных: {result['positive_checks']}"
                )
            else:
                await message.answer(
                    f"✅ URL безопасен\n"
                    f"Репутация: {result['reputation']}%\n"
                    f"Проверок: {result['total_checks']}\n"
                    f"Положительных: {result['positive_checks']}"
                )
        else:
            await message.answer("❌ Ошибка при проверке URL")
        
        # Сохраняем историю
        add_to_history(message.from_user.id, "url", text)
    
    # Проверка IP
    elif text.count(".") == 3 and all(part.isdigit() for part in text.split(".")):               
        await message.answer("📍 IP проверяется...")
        result = await check_ip_reputation(text)
        
        if isinstance(result, dict):
            if result['fraud_score'] > 50:
                await message.answer(
                    f"⚠️ IP-адрес может быть подозрительным!\n"
                    f"Оценка мошенничества: {result['fraud_score']}%\n"
                    f"Прокси: {'Да' if result['is_proxy'] else 'Нет'}\n"
                    f"TOR: {'Да' if result['is_tor'] else 'Нет'}\n"
                    f"Бот: {'Да' if result['is_bot'] else 'Нет'}"
                )
            else:
                await message.answer(
                    f"✅ IP-адрес безопасен\n"
                    f"Оценка мошенничества: {result['fraud_score']}%\n"
                    f"Прокси: {'Да' if result['is_proxy'] else 'Нет'}\n"
                    f"TOR: {'Да' if result['is_tor'] else 'Нет'}\n"
                    f"Бот: {'Да' if result['is_bot'] else 'Нет'}"
                )
        else:
            await message.answer("❌ Ошибка при проверке IP-адреса")
        
        # Сохраняем историю
        add_to_history(message.from_user.id, "ip", text)
    
    else:
        await message.answer("❌ Пожалуйста, введите корректные данные для проверки.")

async def check_url_virustotal(url):
    """Проверка URL через VirusTotal API"""
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = min(NODES, key=lambda node: node.load)
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        # Проверка через VirusTotal API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.virustotal.com/api/v3/urls/{url}",
                headers={"x-apikey": VIRUSTOTAL_API_KEY}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    total = sum(stats.values())
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    
                    return {
                        'malicious': malicious > 0,
                        'reputation': int((1 - (malicious + suspicious) / total) * 100) if total > 0 else 100,
                        'total_checks': total,
                        'positive_checks': malicious + suspicious
                    }
                else:
                    return {
                        'malicious': False,
                        'reputation': 0,
                        'total_checks': 0,
                        'positive_checks': 0
                    }
    except Exception as e:
        logging.error(f"Ошибка при проверке URL: {e}")
        return {
            'malicious': False,
            'reputation': 0,
            'total_checks': 0,
            'positive_checks': 0
        }

async def check_ip_reputation(ip_address):
    """Проверка репутации IP-адреса через IPQS API"""
    try:
        # Выбираем узел с наименьшей нагрузкой
        node = min(NODES, key=lambda node: node.load)
        
        # Обновляем нагрузку на узле
        node.update_load()
        
        # Проверка через IPQS API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://ipqs.io/ip-api/json/{ip_address}",
                params={"key": IPQS_API_KEY}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success", False):
                        return {
                            'fraud_score': data.get("fraud_score", 0),
                            'is_proxy': data.get("proxy", False),
                            'is_tor': data.get("tor", False),
                            'is_bot': data.get("bot", False)
                        }
                    else:
                        return {
                            'fraud_score': 100,
                            'is_proxy': True,
                            'is_tor': True,
                            'is_bot': True
                        }
                else:
                    return {
                        'fraud_score': 100,
                        'is_proxy': True,
                        'is_tor': True,
                        'is_bot': True
                    }
    except Exception as e:
        logging.error(f"Ошибка при проверке IP: {e}")
        return {
            'fraud_score': 100,
            'is_proxy': True,
            'is_tor': True,
            'is_bot': True
        }

        # Уменьшаем нагрузку после выполнения запроса
        node.decrease_load()
        save_node_loads()
        
        return result_text
    except Exception as e:
        logging.error(f"Ошибка при проверке IP-адреса: {e}")
        return "❌ Ошибка при проверке IP-адреса"

async def main():
    # Инициализируем сеть
    await initialize_network()
    
    # Запускаем периодическую балансировку в отдельном таске
    asyncio.create_task(periodic_balancing())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
