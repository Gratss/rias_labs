import asyncio
import random
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Загружаем переменные окружения
load_dotenv()

# Телеграм токен бота
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Определение класса узла (сервер обработки)
class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.load = 0  # Текущая нагрузка
        self.lock = asyncio.Lock()  # Блокировка для корректного обновления load

    async def process_request(self, request_data):
        """Обрабатывает запрос и уменьшает нагрузку после выполнения."""
        async with self.lock:  # Блокируем изменение load, чтобы избежать ошибок
            self.load += 1

        await asyncio.sleep(random.uniform(1, 3))  # Имитация обработки

        async with self.lock:
            self.load -= 1  # Уменьшаем нагрузку после выполнения

        return f"✅ Node {self.node_id} обработал запрос: {request_data} (Load: {self.load})"

    def get_load(self):
        """Возвращает текущую нагрузку узла."""
        return self.load

# Класс балансировщика нагрузки
class LoadBalancer:
    def __init__(self, nodes):
        self.nodes = nodes  # Список узлов

    def select_node(self):
        """Выбирает узел с наименьшей загрузкой. Если несколько, выбирает случайный."""
        min_load = min(node.get_load() for node in self.nodes)  # Ищем минимальную загрузку
        available_nodes = [node for node in self.nodes if node.get_load() == min_load]  # Узлы с минимальной загрузкой
        selected_node = random.choice(available_nodes)  # Выбираем случайный из свободных узлов
        
        print(f"🔀 Выбран узел: Node {selected_node.node_id} (Load: {selected_node.get_load()})")  
        return selected_node

    async def handle_request(self, request_data):
        """Выбирает узел и отправляет ему запрос."""
        node = self.select_node()
        return await node.process_request(request_data)

# Создаём 3 узла для обработки
nodes = [Node(i) for i in range(3)]
balancer = LoadBalancer(nodes)

# Обработчик команды /check
@dp.message(Command("check"))
async def check_request(message: types.Message):
    """Команда /check - проверяет данные с балансировкой нагрузки."""
    await message.answer("🔄 Запрос отправлен на обработку...")
    response = await balancer.handle_request("Запрос от пользователя")
    await message.answer(response)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
