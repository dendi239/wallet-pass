import datetime
import typing as tp

import ics

from lib.ticket import Ticket


def _simplify_station_name(name: str) -> str:
    return name.lower().title()


def build_calendar_event(
    begin_time: datetime.datetime,
    end_time: datetime.datetime,
    in_station: str,
    out_station: str,
) -> ics.Calendar:
    in_station = _simplify_station_name(in_station)
    out_station = _simplify_station_name(out_station)

    event = ics.Event()
    event.name = f"Поезд {in_station} - {out_station}"

    event.begin = begin_time
    event.end = end_time

    calendar = ics.Calendar()
    calendar.events.add(event)

    return calendar


def make_calendar_event(ticket: Ticket) -> str:
    return build_calendar_event(
        ticket["relevant_date"],
        ticket["expiration_date"],
        ticket["from"],
        ticket["to"],
    )
