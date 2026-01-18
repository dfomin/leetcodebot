import asyncio
import json
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler

from leetcodebot.aoc import send_aoc
from leetcodebot.contest import send_contest
from leetcodebot.rank import send_rank
from leetcodebot.today import send_today
from leetcodebot.status import send_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def create_application() -> Application:
    """Create an Application for handling updates."""
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("rank", send_rank))
    app.add_handler(CommandHandler("today", send_today))
    app.add_handler(CommandHandler("status", send_status))
    app.add_handler(CommandHandler("contest", send_contest))
    app.add_handler(CommandHandler("aoc", send_aoc))

    return app


application = create_application()


HANDLER_TIMEOUT = 20  # seconds - leave buffer before Lambda's 30s timeout


async def process_update(event_body):
    """Process a single update."""
    async with application:
        update = Update.de_json(json.loads(event_body), application.bot)
        await application.process_update(update)


async def process_update_with_timeout(event_body):
    """Process update with hard timeout, send error to Telegram if timeout."""
    data = json.loads(event_body)
    chat_id = data.get("message", {}).get("chat", {}).get("id")

    try:
        await asyncio.wait_for(process_update(event_body), timeout=HANDLER_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error("Handler timed out")
        if chat_id:
            async with application:
                await application.bot.send_message(chat_id, "Request timed out. Please try again.")


def lambda_handler(event, context):
    """Lambda function handler for processing Telegram updates."""
    try:
        event_body = event.get("body")
        asyncio.run(process_update_with_timeout(event_body))
    except Exception as e:
        logger.error(f"Error processing update: {e}")
    return {"statusCode": 200}


if __name__ == '__main__':
    application.run_polling()
