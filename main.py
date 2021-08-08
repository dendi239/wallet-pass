#! /usr/bin/env python3

import asyncio
import datetime
import logging
import os
import typing as tp
import urllib.parse

import aiohttp
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.utils.executor import start_webhook

PASSSLOT_API_KEY = os.environ['PASSSLOT_API_KEY']
TELEGRAM_API_TOKEN = os.environ['TELEGRAM_API_TOKEN']

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


@dp.message_handler(commands=['start', 'help'])
async def show_help(message: types.Message) -> None:
    help_message = \
        "Это бот который по билету укрзализныци генерирует pkpass. " \
        "Просто скопируйте текст билета и пришлите мне его в сообщении."
    await bot.send_message(message.chat.id, help_message, parse_mode=types.ParseMode.MARKDOWN)


async def register_pass(data: tp.Dict[str, str]) -> tp.Dict[str, str]:
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.passslot.com/v1/templates/5786360806637568/pass',
                                headers={'Authorization': PASSSLOT_API_KEY},
                                json=data) as response:
            assert response.status == 201, response
            return await response.json()


def parse_ticket(s: str) -> tp.Dict[str, str]:
    tokens = sum([line.split('\t') for line in s.split('\n')], [])
    for i, line in enumerate(tokens):
        print(i, line)

    uid = tokens[2]
    name, train = tokens[14], tokens[16]
    train = train.split()[0]

    station_in, coach = tokens[19], tokens[21]
    coach = coach.split()[0]

    station_out, seat = tokens[24], tokens[26]
    seat = seat.split()[0]

    # TODO: Check winter time
    time_zone = datetime.timezone(offset=datetime.timedelta(hours=2))
    time_in, time_out = map(lambda t: datetime.datetime
                            .strptime(t, '%d.%m.%Y %H:%M')
                            .replace(tzinfo=time_zone),
                            (tokens[28], tokens[33]))

    return {
        'uid': uid,
        'name': name,
        'train': train,
        'relevant_date': time_in.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%m+00:00'),
        'from': station_in,
        'from_time': time_in.strftime('%H:%M'),
        'to_time': time_out.strftime('%H:%M'),
        'from_day': time_in.strftime('%d %b %Y'),
        'to_day': time_out.strftime('%d %b %Y'),
        'to': station_out,
        'seat': seat,
        'coach': coach,
    }


@dp.message_handler()
async def create_ticket(message: types.Message) -> None:
    logging.info(f'Received message {message.text} from {message.from_user.id}, message: {message}')
    try:
        ticket = parse_ticket(message.text)
    except Exception as e:
        await message.reply(f'parsing failed: {e}')
        raise

    logging.info(f'Parsed ticket: {ticket}')

    try:
        registered = await register_pass(ticket)
    except Exception as e:
        await message.reply(f'Registering failed: {e} ({type(e)})')
        raise

    if 'url' not in registered:
        await message.reply(f'something went wrong with {registered}')
    else:
        # TODO: Delete tickets after creating
        await message.reply(registered['url'])


def main() -> None:
    if 'WEBHOOK_HOST' in os.environ:
        webhook_host = os.environ['WEBHOOK_HOST']
        webhook_port = int(os.environ['PORT'])

        webhook_url_path = f'/webhook/{API_TOKEN}'
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
            host='0.0.0.0',
            port=webhook_port,
        )

    else:
        async def run() -> None:
            await dp.start_polling()

        asyncio.get_event_loop().run_until_complete(run())


if __name__ == '__main__':
    main()
