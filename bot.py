import asyncio
import logging
import os
from pathlib import Path

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted

# ─── Загрузка окружения ───────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY")
SHOP_FILE    = os.getenv("SHOP_FILE", "shop_info.txt")   # можно переопределить в Railway

# ─── Настройка логов ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)

# ─── Читаем базу знаний при старте ───────────────────────────────────────────
def load_knowledge_base() -> str:
    path = Path(SHOP_FILE)
    if not path.exists():
        log.warning(f"Файл '{SHOP_FILE}' не найден — бот будет отвечать без базы знаний.")
        return "Информация о компании временно недоступна."
    text = path.read_text(encoding="utf-8").strip()
    log.info(f"База знаний загружена: {len(text)} символов из '{SHOP_FILE}'")
    return text

SHOP_INFO = load_knowledge_base()

# ─── Системный промпт ────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Ты — вежливый ИИ-администратор компании. "
    "Вот актуальная информация о нас:\n\n"
    f"{SHOP_INFO}\n\n"
    "Твоя задача — отвечать клиентам исключительно на основе этих данных. "
    "Отвечай кратко, по делу, дружелюбно. "
    "Если вопрос клиента выходит за рамки предоставленной информации — "
    "вежливо сообщи, что перенаправляешь запрос менеджеру, "
    "и попроси оставить номер телефона для обратной связи. "
    "Не придумывай информацию, которой нет в тексте. "
    "Если клиент просто здоровается (например: 'привет', 'здравствуйте'), "
    "вежливо поздоровайся в ответ и спроси, какой у него вопрос, не используя базу знаний."
)

# ─── Настройка Gemini ─────────────────────────────────────────────────────────
genai.configure(api_key=GEMINI_KEY)

gemini_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    system_instruction=SYSTEM_PROMPT,
)

# ─── Запрос к Gemini ─────────────────────────────────────────────────────────
async def ask_gemini(user_text: str) -> str:
    try:
        response = await gemini_model.generate_content_async(user_text)
        return response.text

    except ResourceExhausted:
        log.warning("Gemini: лимит запросов (ResourceExhausted)")
        return (
            "Извините, я взял небольшую паузу. "
            "Пожалуйста, повторите вопрос через 10 секунд. 🙏"
        )

    except Exception as e:
        log.error(f"Gemini error: {type(e).__name__}: {e}")
        return (
            "Что-то пошло не так с моей стороны. "
            "Попробуйте повторить вопрос чуть позже."
        )

# ─── Aiogram ─────────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Здравствуйте!\n\n"
        "Я ИИ-администратор нашей компании.\n"
        "Задайте любой вопрос — о ценах, времени работы, доставке или бронировании.\n\n"
        "Чем могу помочь? 😊"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    # Индикатор набора — бот «печатает»
    await bot.send_chat_action(message.chat.id, "typing")

    reply = await ask_gemini(message.text)
    await message.answer(reply)

# ─── Запуск ───────────────────────────────────────────────────────────────────
async def main():
    log.info("Бот запущен — polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
