#! /usr/bin/env python3

import asyncio
import datetime
import logging
import os
import tempfile
import typing as tp
import urllib.parse

import aiohttp
import aiogram.utils.markdown as md
import textract
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


@dp.message_handler(commands=['todo'])
async def show_todo(message: types.Message) -> None:
    todo_message = md.text(
        md.bold('TODO list:'),
        md.text('- support expire date'),
        md.text('- consider using builtin time/date formatting'),
        md.text('- check if everything okay with timezones and winter time'),
        md.text('- clear passes feature'),
        md.text('- consider more convenient interface'),
        md.text('- make group identifier right'),
        sep='\n',
    )
    logging.info(f'sending {todo_message}')
    await bot.send_message(message.chat.id, todo_message, parse_mode=types.ParseMode.MARKDOWN)


async def register_pass(data: tp.Dict[str, str]) -> tp.Dict[str, str]:
    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.passslot.com/v1/templates/5786360806637568/pass',
                                headers={'Authorization': PASSSLOT_API_KEY},
                                json=data) as response:
            assert response.status == 201, response
            return await response.json()


def get_(data: tp.List[str], key: str, shift: int = 1) -> str:
    for k, v in zip(data, data[shift:]):
        if k.strip().lower() == key.strip().lower():
            return v
    raise ValueError(f'{key} not found in {data}')


def parse_time(t: str) -> datetime.datetime:
    # TODO: Check winter time
    time_zone = datetime.timezone(offset=datetime.timedelta(hours=2))

    return datetime.datetime \
        .strptime(t, '%d.%m.%Y %H:%M') \
        .replace(tzinfo=time_zone)


def build_ticket(
        uid: str, name: str, train: str, seat: str, coach: str,
        station_in: str, station_out: str,
        time_in: datetime.datetime, time_out: datetime.datetime,
) -> tp.Dict[str, str]:
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


def parse_ticket(s: str) -> tp.Dict[str, str]:
    tokens = [token for line in s.split('\n') for token in line.split('\t') if token]

    uid = get_(tokens, 'ПОСАДОЧНИЙ ДОКУМЕНТ')
    name, train = get_(tokens, 'Прізвище, Ім’я'), get_(tokens, 'Поїзд')
    train = train.split()[0]

    station_in, coach = get_(tokens, 'Відправлення', shift=2), get_(tokens, 'Вагон')
    coach = coach.split()[0]

    station_out, seat = get_(tokens, 'Призначення', shift=2), get_(tokens, 'Місце')
    seat = seat.split()[0]

    time_in, time_out = get_(tokens, 'Дата/час відпр.'), get_(tokens, 'Дата/час приб.')
    time_in, time_out = map(parse_time, (time_in, time_out))

    return build_ticket(
        uid=uid, name=name, train=train, seat=seat, coach=coach,
        station_in=station_in, station_out=station_out,
        time_in=time_in, time_out=time_out,
    )


def parse_ticket_from_pdf(text: str) -> tp.Dict[str, str]:
    tokens = text.split('\n')

    for i, token in enumerate(tokens):
        logging.info(f'get token #{i:02}: "{token}"')

    station_index = 0
    for i, token in enumerate(tokens):
        if len(token) > 7 and all(d.isdigit() for d in token[:7]) and token[7].isspace():
            station_index = i
            break

    train_index = 0
    for i, token in enumerate(tokens):
        if token.strip().startswith('ФК:'):
            train_index = i + 2
            break

    return build_ticket(
        uid=tokens[7],
        name=tokens[10],
        train=tokens[train_index].split()[0],
        coach=tokens[train_index+1].split()[0],
        seat=tokens[train_index+2].split()[0],
        station_in=''.join(tokens[station_index].split()[1:]),
        station_out=''.join(tokens[station_index+1].split()[1:]),
        time_in=parse_time(tokens[station_index+2]),
        time_out=parse_time(tokens[station_index+3]),
    )


async def process_text(text: str, message: types.Message, pdf=False) -> None:
    logging.info(f'start process text for {message.from_user}: {text}')

    try:
        if pdf:
            ticket = parse_ticket_from_pdf(text)
        else:
            ticket = parse_ticket(text)
    except Exception as e:
        await message.reply(f'parsing failed: {e}')
        return

    logging.info(f'Parsed ticket: {ticket}')

    try:
        registered = await register_pass(ticket)
    except Exception as e:
        await message.reply(f'Registering failed: {e} ({type(e)})')
        return

    if 'url' not in registered:
        await message.reply(f'something went wrong with {registered}')
    else:
        # TODO: Delete tickets after creating
        await message.reply(registered['url'])


@dp.message_handler(content_types=types.ContentTypes.DOCUMENT | types.ContentTypes.TEXT)
async def create_ticket(message: types.Message) -> None:
    logging.info(f'Received message {message.text} from {message.from_user.id}, message: {message}')

    if message.document is not None and message.document.mime_type == 'application/pdf':
        logging.info(f'found attachment: {message.document}')

        with tempfile.NamedTemporaryFile('wb', suffix='.pdf', delete=False) as temp_ticket:
            await message.document.download(temp_ticket.name)
            for page in textract \
                    .process(temp_ticket.name) \
                    .decode('utf-8') \
                    .split('\f'):
                if not page:
                    continue

                try:
                    await process_text(page, message, pdf=True)
                except ValueError:
                    pass
    else:
        await process_text(message.text, message)


def main() -> None:
    if 'WEBHOOK_HOST' in os.environ:
        webhook_host = os.environ['WEBHOOK_HOST']
        webhook_port = int(os.environ['PORT'])

        webhook_url_path = f'/webhook/{TELEGRAM_API_TOKEN}'
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
