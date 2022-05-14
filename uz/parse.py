import datetime
import logging
import os
import tempfile
import typing as tp

import dateutil.tz
import textract

from lib.ticket import Ticket


def get_(data: tp.List[str], key: str, shift: int = 1) -> str:
    for k, v in zip(data, data[shift:]):
        if k.strip().lower() == key.strip().lower():
            return v
    raise ValueError(f"{key} not found in {data}")


def parse_time(t: str) -> datetime.datetime:
    time_zone = dateutil.tz.gettz("EET")

    return (
        datetime.datetime.strptime(t.strip(), "%d.%m.%Y %H:%M")
        .replace(tzinfo=time_zone)
        .astimezone(datetime.timezone.utc)
    )


def rebuild_uid(uid: str) -> str:
    parts = uid.split("-")
    return f'{parts[0]}-{"".join(parts[1:-1])}-{parts[-1]}'


def build_ticket(
    uid: str,
    name: str,
    train: str,
    seat: str,
    coach: str,
    station_in: str,
    station_out: str,
    time_in: datetime.datetime,
    time_out: datetime.datetime,
) -> tp.Dict[str, str]:
    return {
        "uid": rebuild_uid(uid),
        "name": name,
        "train": train,
        "relevant_date": time_in.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "expiration_date": time_out.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "from": station_in,
        "to": station_out,
        "seat": seat,
        "coach": coach,
    }


def parse_ticket(s: str) -> tp.Dict[str, str]:
    tokens = [token for line in s.split("\n") for token in line.split("\t") if token]

    uid = get_(tokens, "ПОСАДОЧНИЙ ДОКУМЕНТ")
    name, train = get_(tokens, "Прізвище, Ім’я"), get_(tokens, "Поїзд")
    train = train.split()[0]

    station_in, coach = get_(tokens, "Відправлення", shift=2), get_(tokens, "Вагон")
    coach = coach.split()[0]

    station_out, seat = get_(tokens, "Призначення", shift=2), get_(tokens, "Місце")
    seat = seat.split()[0]

    time_in, time_out = get_(tokens, "Дата/час відпр."), get_(tokens, "Дата/час приб.")
    time_in, time_out = map(parse_time, (time_in, time_out))

    return build_ticket(
        uid=uid,
        name=name,
        train=train,
        seat=seat,
        coach=coach,
        station_in=station_in,
        station_out=station_out,
        time_in=time_in,
        time_out=time_out,
    )


def parse_ticket_from_pdf(text: str) -> Ticket:
    tokens = text.split("\n")

    for i, token in enumerate(tokens):
        logging.info(f'get token #{i:02}: "{token}"')

    station_index = 0
    for i, token in enumerate(tokens):
        if len(token) > 7 and all(d.isdigit() for d in token[:7]) and token[7].isspace():
            station_index = i
            break

    train_index = 0
    for i, token in enumerate(tokens):
        if token.strip().startswith("ФК:"):
            train_index = i + 2
            break

    time_index, out_time_index = -1, -1
    for diff in range(1, 5):
        for i, (token, next_token) in enumerate(zip(tokens, tokens[diff:])):
            try:
                _, _ = parse_time(token), parse_time(next_token)
                time_index = i
                out_time_index = i + diff
                break
            except ValueError:
                pass

        if time_index != -1:
            break

    if time_index == -1:
        raise ValueError("no time has been found")

    name_index = 10
    if tokens[name_index] == "ЦЕЙ ПОСАДОЧНИЙ ДОКУМЕНТ Є ПІДСТАВОЮ ДЛЯ ПРОЇЗДУ":
        for i, token in enumerate(tokens):
            if token == "Прізвище, Ім’я":
                name_index = i + 1

    if tokens[name_index] in {"", "Відправлення"}:
        name_index = 12

    return build_ticket(
        uid=tokens[7],
        name=tokens[name_index],
        train=tokens[train_index].split()[0],
        coach=tokens[train_index + 1].split()[0],
        seat=tokens[train_index + 2].split()[0],
        station_in="".join(tokens[station_index].split()[1:]),
        station_out="".join(tokens[station_index + 1].split()[1:]),
        time_in=parse_time(tokens[time_index]),
        time_out=parse_time(tokens[out_time_index]),
    )


def parse_pdf(filename: os.PathLike) -> tp.Iterable[Ticket]:
    for page in textract.process(filename).decode("utf-8").split("\f"):
        if not page:
            continue

        try:
            ticket = parse_ticket_from_pdf(page)
            yield ticket
        except ValueError:
            pass
