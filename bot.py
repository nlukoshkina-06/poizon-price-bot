# bot.py
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import asyncio
import requests

# загружаем токен
load_dotenv("config.env")
TOKEN = os.getenv("BOT_TOKEN")

# Создаём объекты бота и диспетчера
bot = Bot(token=TOKEN) # Bot — основной объект для работы с Telegram
dp = Dispatcher() # Dispatcher — управляет обработчиками сообщений

# Словарь для хранения данных пользователя
user_data = {}

# Кэш для курса валюты
exchange_rate_cache = None

# Функция для получения актуального курса CNY → RUB
def get_exchange_rate():
    """
    Получаем актуальный курс CNY → RUB с сайта open.er-api.com
    (не требует ключей)
    Если запрос не удаётся, возвращаем запасной курс 12.9
    """
    try:
        response = requests.get("https://open.er-api.com/v6/latest/CNY")
        data = response.json()
        rate = data["rates"]["RUB"]
        return rate
    except Exception as e:
        print("Ошибка при получении курса:", e)
        return 12.9  # запасной курс

# Клавиатура для основных команд
def main_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Новый товар")],
            [KeyboardButton(text="Пересчитать наценку")],
            [KeyboardButton(text="/rate")]
        ],
        resize_keyboard=True
    )
    return kb

# Обработчик команды /start
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {}  # сброс данных при новом старте
    await send_greeting(user_id)

# Функция для приветствия
async def send_greeting(user_id):
    await bot.send_message(
        chat_id=user_id,
        text=(
            "Привет! Я Poizon Price Bot 👋\n\n"
            "Я могу:\n"
            "• Перевести цену товара с Poizon в рубли по актуальному курсу\n"
            "• Рассчитать стоимость доставки\n"
            "• Рассчитать итоговую цену с наценкой и вашу прибыль\n"
            "• Позволить пересчитать цену с другим процентом наценки\n\n"
            "Нажмите 'Новый товар', чтобы начать!"
        ),
        reply_markup=main_keyboard()
    )

# Основной обработчик сообщений
@dp.message()
async def main_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # Если новый пользователь — отправляем приветствие
    if user_id not in user_data:
        user_data[user_id] = {}
        await send_greeting(user_id)
        return

    data = user_data[user_id]

    # Команды
    if text == "Новый товар":
        user_data[user_id] = {}  # сброс всех данных для нового товара
        await message.answer("Введите цену товара в юанях (например: 550):", reply_markup=main_keyboard())
        return

    if text == "Пересчитать наценку":
        if "price" not in data or "weight" not in data or "delivery_per_kg" not in data:
            await message.answer("Сначала введите данные товара через 'Новый товар'.", reply_markup=main_keyboard())
            return
        data["awaiting_margin"] = True
        await message.answer("Введите новый процент наценки (например: 25):", reply_markup=main_keyboard())
        return

    if text.startswith("/rate"):
        rate = get_exchange_rate()
        await message.answer(f"Актуальный курс CNY → RUB: {rate:.2f}", reply_markup=main_keyboard())
        return


    # Если ждём процент для пересчёта
    if data.get("awaiting_margin"):
        try:
            margin = float(text)
            if margin < 0:
                await message.answer("Процент наценки должен быть >= 0. Попробуй ещё раз.", reply_markup=main_keyboard())
                return
            data["awaiting_margin"] = False
        except ValueError:
            await message.answer("Пожалуйста, введи число для процента наценки.", reply_markup=main_keyboard())
            return
    else:
        # Шаг 1: ввод цены
        if "price" not in data:
            if not text.isdigit():
                await message.answer("Пожалуйста, введи только число, цену в юанях.", reply_markup=main_keyboard())
                return
            data["price"] = float(text)
            await message.answer("Укажите вес товара в кг (например: 0.8):", reply_markup=main_keyboard())
            return

        # Шаг 2: ввод веса
        if "weight" not in data:
            try:
                weight = float(text)
                if weight <= 0:
                    await message.answer("Вес должен быть больше 0. Попробуй ещё раз.", reply_markup=main_keyboard())
                    return
                data["weight"] = weight
                await message.answer("Укажите стоимость доставки за 1 кг (например: 1000):", reply_markup=main_keyboard())
            except ValueError:
                await message.answer("Пожалуйста, введи число для веса.", reply_markup=main_keyboard())
            return

        # Шаг 3: ввод стоимости доставки
        if "delivery_per_kg" not in data:
            try:
                delivery_per_kg = float(text)
                if delivery_per_kg < 0:
                    await message.answer("Стоимость доставки должна быть >= 0. Попробуй ещё раз.", reply_markup=main_keyboard())
                    return
                data["delivery_per_kg"] = delivery_per_kg
                await message.answer("Укажите процент наценки, если хотите (например: 25):", reply_markup=main_keyboard())
            except ValueError:
                await message.answer("Пожалуйста, введи число для стоимости доставки.", reply_markup=main_keyboard())
            return

        # Шаг 4: ввод процента наценки
        try:
            margin = float(text)
            if margin < 0:
                await message.answer("Процент наценки должен быть >= 0. Попробуй ещё раз.", reply_markup=main_keyboard())
                return
        except ValueError:
            await message.answer("Пожалуйста, введи число для процента наценки.", reply_markup=main_keyboard())
            return

    # Расчёты
    price_cny = data["price"]
    weight = data["weight"]
    delivery_per_kg = data["delivery_per_kg"]
    exchange_rate = get_exchange_rate()

    price_rub = price_cny * exchange_rate
    delivery_cost = weight * delivery_per_kg
    total_without_margin = price_rub + delivery_cost
    total_with_margin = total_without_margin * (1 + margin / 100)
    profit = total_with_margin - total_without_margin

    await message.answer(
        f"💰 Цена товара: {price_cny} ¥ × {exchange_rate:.2f} ₽ = {price_rub:.0f} ₽\n"
        f"🚚 Доставка: {weight} кг × {delivery_per_kg:.0f} ₽ = {delivery_cost:.0f} ₽\n"
        f"💵 Итого без наценки: {total_without_margin:.0f} ₽\n"
        f"💸 С наценкой {margin:.0f}%: {total_with_margin:.0f} ₽\n"
        f"📈 Ваша прибыль: {profit:.0f} ₽\n\n"
        "Если хотите пересчитать с другим процентом наценки, используйте кнопку 'Пересчитать наценку'.",
        reply_markup=main_keyboard()
    )

# Основной запуск бота
async def main():
    print("Poizon Price Bot запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
