#! /usr/bin/env python3

import asyncio
import logging
import os
import tempfile
import urllib.parse

import aiogram.types.message
import aiogram.utils.markdown as md
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.utils.executor import start_webhook

from lib.passslot import create_pass
from uz.parse import parse_pdf, parse_ticket, parse_ticket_from_pdf

TELEGRAM_API_TOKEN = os.environ["TELEGRAM_API_TOKEN"]

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


@dp.message_handler(commands=["start", "help"])
async def show_help(message: types.Message) -> None:
    help_message = (
        "Это бот который по билету укрзализныци генерирует pkpass. "
        "Просто отправьте мне pdf с билетом и я всё сделаю."
    )
    await bot.send_message(message.chat.id, help_message, parse_mode=types.ParseMode.MARKDOWN)


@dp.message_handler(commands=["todo"])
async def show_todo(message: types.Message) -> None:
    todo_message = md.text(
        md.bold("TODO list:"),
        md.text("- support expire date"),
        md.text("- consider using builtin time/date formatting"),
        md.text("- check if everything okay with timezones and winter time"),
        md.text("- clear passes feature"),
        md.text("- consider more convenient interface"),
        md.text("- make group identifier right"),
        sep="\n",
    )
    logging.info(f"sending {todo_message}")
    await bot.send_message(message.chat.id, todo_message, parse_mode=types.ParseMode.MARKDOWN)


@dp.message_handler(content_types=types.ContentTypes.DOCUMENT | types.ContentTypes.TEXT)
async def create_ticket(message: types.Message) -> None:
    logging.info(f"Received message {message.text} from {message.from_user.id}, message: {message}")

    if message.document is not None and message.document.mime_type == "application/pdf":
        logging.info(f"found attachment: {message.document}")

        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as temp_ticket:
            await message.document.download(temp_ticket.name)
            for ticket in parse_pdf(temp_ticket.name):
                logging.info(f"Parsed ticket: {ticket}")
                try:
                    pkpass = await create_pass(ticket)
                    await bot.send_document(
                        message.chat.id, aiogram.types.InputFile(pkpass.pkpass, filename=f"{pkpass.name}.pkpass")
                    )

                except Exception as e:
                    await message.reply(f"Registering failed: {e} ({type(e)})")


def main() -> None:
    if "WEBHOOK_HOST" in os.environ:
        webhook_host = os.environ["WEBHOOK_HOST"]
        webhook_port = int(os.environ["PORT"])

        webhook_url_path = f"/webhook/{TELEGRAM_API_TOKEN}"
        webhook_url = urllib.parse.urljoin(webhook_host, webhook_url_path)

        async def on_startup(dp: Dispatcher) -> None:
            if (await bot.get_webhook_info()).url != webhook_url:
                await bot.delete_webhook()
                await bot.set_webhook(webhook_url)

        start_webhook(
            dispatcher=dp,
            webhook_path=webhook_url_path,
            skip_updates=False,
            on_startup=on_startup,
            host="0.0.0.0",
            port=webhook_port,
        )

    else:

        async def run() -> None:
            await dp.start_polling()

        asyncio.get_event_loop().run_until_complete(run())


if __name__ == "__main__":
    main()
