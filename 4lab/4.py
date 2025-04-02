import asyncio
import os
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, BotCommand
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

NODE_LOADS_FILE = "node_loads.json"

class Node:
    def __init__(self, id, max_load):
        self.id = id
        self.max_load = max_load
        self.load = 0
        self.neighbors = []  # Соседние узлы
        self.visited = False
        self.message_queue = []

    def update_load(self, amount=1):
        """Увеличивает нагрузку"""
        self.load = min(self.load + amount, self.max_load)

    def decrease_load(self, amount=1):
        """Уменьшает нагрузку"""
        self.load = max(self.load - amount, 0)

    def get_status(self):
        """Получает текущее состояние узла"""
        return {
            'id': self.id,
            'load': self.load,
            'max_load': self.max_load,
            'neighbors': [n.id for n in self.neighbors]
        }

    def process_message(self, message):
        """Обрабатывает входящее сообщение"""
        if message['type'] == 'wave':
            self.handle_wave(message)
        elif message['type'] == 'transfer':
            self.handle_transfer(message)

    def handle_wave(self, message):
        """Обрабатывает волновое сообщение"""
        if not self.visited:
            self.visited = True
            self.message_queue.extend(self.create_wave_messages())
            self.message_queue.extend(self.create_transfer_messages())

    def handle_transfer(self, message):
        """Обрабатывает сообщение о переносе нагрузки"""
        if message['source'] != self.id:
            transfer_amount = message['amount']
            self.decrease_load(transfer_amount)
            self.message_queue.extend(self.create_transfer_messages())

    def create_wave_messages(self):
        """Создает волновые сообщения для соседей"""
        return [{
            'type': 'wave',
            'source': self.id,
            'status': self.get_status()
        } for neighbor in self.neighbors]

    def create_transfer_messages(self):
        """Создает сообщения о переносе нагрузки"""
        messages = []
        for neighbor in self.neighbors:
            transfer_amount = self.calculate_transfer_amount(neighbor)
            if transfer_amount > 0:
                messages.append({
                    'type': 'transfer',
                    'source': self.id,
                    'target': neighbor.id,
                    'amount': transfer_amount
                })
        return messages

    def calculate_transfer_amount(self, neighbor):
        """Вычисляет количество нагрузки для переноса"""
        max_transfer = (self.load - neighbor.load) // 2
        return min(max_transfer, self.max_load // 4)

async def propagate_wave(node):
    """Распространяет волну по сети"""
    try:
        logging.info(f"Начало волны от узла {node.id}")
        node.visited = True
        messages = node.create_wave_messages()
        
        for message in messages:
            await process_message(node, message)
            
        while any(node.message_queue for node in NODES):
            for node in NODES:
                while node.message_queue:
                    message = node.message_queue.pop(0)
                    await process_message(node, message)
    except Exception as e:
        logging.error(f"Ошибка при распространении волны: {e}")

async def process_message(node, message):
    """Обрабатывает сообщение в асинхронном режиме"""
    try:
        target_node = next(n for n in NODES if n.id == message['target'])
        target_node.process_message(message)
    except Exception as e:
        logging.error(f"Ошибка при обработке сообщения: {e}")

async def balance_load():
    """Запускает фазовый волновой алгоритм балансировки"""
    try:
        # Выбираем узел с максимальной нагрузкой как источник волны
        source_node = max(NODES, key=lambda node: node.load)
        logging.info(f"Запуск волнового алгоритма от узла {source_node.id}")
        
        # Сбрасываем флаги посещения
        for node in NODES:
            node.visited = False
        
        # Запускаем волну
        await propagate_wave(source_node)
        
        # Сохраняем состояние нагрузки
        save_node_loads()
    except Exception as e:
        logging.error(f"Ошибка при балансировке нагрузки: {e}")

async def periodic_balancing():
    """Периодическая балансировка нагрузки"""
    while True:
        try:
            await balance_load()
            await asyncio.sleep(60)  # Проверяем каждую минуту
        except Exception as e:
            logging.error(f"Ошибка при периодической балансировке: {e}")

@dp.message(Command("node_status"))
async def node_status(message: types.Message):
    """Обработчик команды /node_status"""
    try:
        status_text = "📊 Статус узлов:\n\n"
        for node in NODES:
            status = node.get_status()
            status_text += (
                f"Узел {status['id']}:\n"
                f"Загрузка: {status['load']}%\n"
                f"Максимальная загрузка: {status['max_load']}%\n"
                f"Соседи: {', '.join(map(str, status['neighbors']))}\n\n"
            )
        
        await message.answer(status_text)
    except Exception as e:
        logging.error(f"Ошибка при получении статуса узлов: {e}")
        await message.answer("❌ Произошла ошибка при получении статуса узлов")

def save_node_loads():
    """Сохраняет текущее состояние нагрузки узлов"""
    try:
        with open(NODE_LOADS_FILE, 'w') as f:
            json.dump({node.id: node.load for node in NODES}, f)
    except Exception as e:
        logging.error(f"Ошибка при сохранении нагрузки: {e}")

def load_node_loads():
    """Загружает состояние узлов из файла"""
    try:
        with open(NODE_LOADS_FILE, 'r') as f:
            loads = json.load(f)
            for node in NODES:
                node.load = loads.get(str(node.id), 0)
    except Exception as e:
        logging.error(f"Ошибка при загрузке нагрузки: {e}")

# Инициализация сети
NODES = [
    Node(0, 100),  # Узел 0 с максимальной нагрузкой 100%
    Node(1, 100),  # Узел 1 с максимальной нагрузкой 100%
    Node(2, 100)   # Узел 2 с максимальной нагрузкой 100%
]

# Устанавливаем топологию сети
NODES[0].neighbors = [NODES[1], NODES[2]]
NODES[1].neighbors = [NODES[0], NODES[2]]
NODES[2].neighbors = [NODES[0], NODES[1]]

async def main():
    # Загружаем состояние узлов
    load_node_loads()
    
    # Запускаем периодическую балансировку в отдельном таске
    asyncio.create_task(periodic_balancing())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())