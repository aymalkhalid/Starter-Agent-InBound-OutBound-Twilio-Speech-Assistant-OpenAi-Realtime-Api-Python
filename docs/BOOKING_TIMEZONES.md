# Booking Timezones

This guide describes how appointment timezone, caller timezone, Google Calendar,
and dashboard call-record booking fields work together.

## Core Rules

1. `TIMEZONE` is the appointment/business timezone and booking authority.
2. Google Calendar events are written with explicit `start.timeZone` and
   `end.timeZone` equal to the appointment timezone.
3. Caller timezone is display context only. It never changes the ISO slot that
   gets booked.
4. Outbound `contact_timezone` is the trusted caller timezone source.
5. Explicit caller-provided timezone can be used when the caller states it.
6. Caller-ID phone timezone inference is only a weak hint and should not decide
   booking authority.

## Runtime Flow

1. Outbound intake accepts `contact_timezone`, for example
   `America/New_York` or `America/Phoenix`.
2. The outbound call context passes that timezone into the Realtime session.
3. `get_availability` receives caller timezone context and returns:
   - UTC `start` / `end`
   - appointment display in clinic time
   - caller-local display when different
   - `appointment_timezone`
   - `caller_timezone`
4. The AI offers caller-local time first when it differs:
   `For you, Tuesday at 9 AM Mountain, which is 8 AM Pacific at the clinic.`
5. `book_appointment` books the exact returned `slot_start_iso`.
6. Google Calendar stores the event in appointment timezone and includes caller
   timezone context in the event details.
7. Call records store structured booking fields:
   - `confirmed_slot`
   - `calendar_event_link`
   - `metadata.appointments[]`
   - `metadata.booking_event_id`
   - `metadata.booking_state`
8. The dashboard Booking field renders from those structured fields and shows
   the Calendar link when `calendar_event_link` is present.

## Spoken Wording

When caller and clinic time differ, speak caller-local time first and clinic
time second:

```text
For you, Monday at 12 PM Eastern, which is 9 AM Pacific at the clinic.
```

Use `clinic time`, `business time`, or `[timezone] at the clinic`. Do not say
`my time`.

When caller and clinic time are the same, avoid over-explaining:

```text
I have Monday at 1 PM Pacific Time.
```

## Manual Test Matrix

Use `TIMEZONE=America/Los_Angeles` for the clinic calendar unless testing
another business timezone.

| Caller timezone | Test date | Expected behavior |
| --- | --- | --- |
| `America/Los_Angeles` | Any bookable date | Same timezone; speak only Pacific time. |
| `America/New_York` | Any bookable date | Caller is 3 hours ahead of LA in normal US DST alignment; speak Eastern first, Pacific second. |
| `America/Phoenix` | July date | Phoenix and LA are usually same offset; avoid duplicate same-time explanation. |
| `America/Phoenix` | Winter date, e.g. `2026-12-01` | Phoenix is 1 hour ahead of LA; speak Mountain/Phoenix first, Pacific second. |

Example Phoenix winter conversion:

```text
2026-12-01 08:00 America/Los_Angeles
= 2026-12-01 09:00 America/Phoenix
```

Expected spoken offer:

```text
For you, Tuesday, December 1 at 9 AM Mountain, which is 8 AM Pacific at the clinic.
```

## Dashboard Verification

After a successful booking, verify:

1. Google Calendar event exists at the clinic time.
2. Event details include appointment time zone, caller local time, caller
   timezone, and caller timezone source.
3. Dashboard call-record details show a Booking row.
4. The Booking row includes appointment time first for staff, caller-local time
   second when different, and a `Calendar` link.

If Google Calendar has the event but the dashboard Booking field is blank,
check the logs for:

- `Syncing call record after booking`
- `has_confirmed_slot: true`
- `has_calendar_event_link: true`
- `Lead updated by call_sid` or `Lead inserted into Supabase table`

Older rows created before structured booking sync may need a one-time backfill.
New rows should carry booking fields from the booking result into
`save_call_record` even if the call-record row did not exist at booking time.
