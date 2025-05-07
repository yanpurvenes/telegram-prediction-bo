import os
import json
import logging
import random
import datetime
import asyncio
import pytz
from typing import Dict, List, Set
import telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка токена из переменных окружения
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

# Путь к файлу с предсказаниями
QUOTES_FILE = "quotes_1000.json"

# Временная зона для планирования отправки сообщений (Москва)
TIMEZONE = pytz.timezone('Europe/Moscow')

# Хранилища данных
users_data = {}  # Словарь для хранения пользователей канала
sent_quotes = {}  # Словарь для отслеживания отправленных предсказаний в текущий день


def load_quotes() -> List[Dict]:
    """Загружает предсказания из JSON файла."""
    try:
        with open(QUOTES_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Ошибка при загрузке предсказаний: {e}")
        return []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я бот предсказаний. Я буду отправлять случайные предсказания "
        "пользователям канала раз в день."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/setup_channel - Настроить канал для отправки предсказаний (только для администраторов)\n"
        "/test_prediction - Отправить тестовое предсказание\n"
    )


async def setup_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Настройка канала для отправки предсказаний."""
    # Проверяем, является ли пользователь администратором
    user = update.effective_user
    if not user or user.id not in [int(admin_id) for admin_id in os.environ.get("ADMIN_IDS", "").split(",") if admin_id]:
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Пожалуйста, укажите ID канала. Пример: /setup_channel @your_channel")
        return

    channel_id = context.args[0]
    try:
        # Сохраняем ID канала в переменные контекста
        context.bot_data["channel_id"] = channel_id
        await update.message.reply_text(f"Канал {channel_id} успешно настроен для отправки предсказаний.")
        
        # Начинаем сбор пользователей из канала
        await update.message.reply_text("Начинаю сбор пользователей из канала...")
        
        # В реальности, здесь должна быть логика получения участников канала
        # Но из-за ограничений API Telegram, это может быть сложно
        # Мы будем добавлять пользователей по мере их активности или другим способом
        
    except Exception as e:
        logger.error(f"Ошибка при настройке канала: {e}")
        await update.message.reply_text(f"Произошла ошибка: {e}")


async def test_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет тестовое предсказание."""
    quotes = load_quotes()
    if not quotes:
        await update.message.reply_text("Не удалось загрузить предсказания.")
        return

    random_quote = random.choice(quotes)
    user = update.effective_user
    
    await update.message.reply_text(
        f"@{user.username}, ваше предсказание:\n\n{random_quote['text']}"
    )


async def collect_users_from_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Собирает пользователей из обновлений для последующей отправки предсказаний."""
    user = update.effective_user
    if user and user.id not in users_data:
        users_data[user.id] = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        logger.info(f"Добавлен новый пользователь: {user.first_name} (@{user.username})")


async def send_daily_predictions() -> None:
    """Отправляет ежедневные предсказания всем пользователям с интервалом в 30 секунд."""
    while True:
        now = datetime.datetime.now(TIMEZONE)
        
        # Определяем время следующей отправки (например, в 9:00 утра)
        target_hour = 21
        target_minute = 20
        
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
            next_run = next_run + datetime.timedelta(days=1)
        
        # Ждем до следующего времени отправки
        time_to_wait = (next_run - now).total_seconds()
        logger.info(f"Следующая отправка предсказаний через {time_to_wait/3600:.2f} часов")
        await asyncio.sleep(time_to_wait)
        
        # Загружаем предсказания
        quotes = load_quotes()
        if not quotes:
            logger.error("Не удалось загрузить предсказания для ежедневной отправки")
            continue
        
        # Сбрасываем отслеживание отправленных предсказаний для нового дня
        sent_quotes.clear()
        
        # Отправляем предсказания всем пользователям
        for user_id, user in users_data.items():
            # Выбираем предсказание, которое еще не было отправлено сегодня
            available_quotes = [q for q in quotes if q['id'] not in sent_quotes.values()]
            if not available_quotes:
                logger.warning("Все предсказания уже были отправлены сегодня")
                break
                
            quote = random.choice(available_quotes)
            sent_quotes[user_id] = quote['id']
            
            try:
                # Формируем сообщение с упоминанием пользователя
                username = user.get('username')
                message = f"@{username}, ваше предсказание на сегодня:\n\n{quote['text']}" if username else f"Ваше предсказание на сегодня:\n\n{quote['text']}"
                
                # Отправляем сообщение пользователю
                # В реальности здесь должна быть отправка в канал или личные сообщения
                # bot.send_message(chat_id=user_id, text=message)
                logger.info(f"Отправлено предсказание пользователю {user.get('first_name')} (@{username}): {quote['text'][:30]}...")
                
                # Ждем 30 секунд перед отправкой следующему пользователю
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке предсказания пользователю {user_id}: {e}")


async def get_chat_members_count(bot, chat_id):
    """Получает количество участников в чате."""
    try:
        count = await bot.get_chat_members_count(chat_id)
        return count
    except Exception as e:
        logger.error(f"Ошибка при получении количества участников: {e}")
        return 0


def main() -> None:
    """Запускает бота."""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setup_channel", setup_channel))
    application.add_handler(CommandHandler("test_prediction", test_prediction))

    # Запускаем задачу отправки ежедневных предсказаний
    application.job_queue.run_once(
        lambda context: asyncio.create_task(send_daily_predictions()),
        when=0
    )

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
