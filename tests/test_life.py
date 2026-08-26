"""Pack-A life features: contacts, birthday engine, habits/streaks, mood, expenses."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from saathi.extensions import db
from saathi.models import Contact, Expense, Habit, HabitLog, Mood, User
from saathi.services.daily import habit_streaks, upcoming_birthdays


def _contact(user_id: int, *, name: str = "Ada", dob: date | None = None) -> Contact:
    row = Contact(user_id=user_id, name=name, dob=dob)
    db.session.add(row)
    db.session.commit()
    return row


def _habit(user_id: int, *, name: str = "Read") -> Habit:
    row = Habit(user_id=user_id, name=name, color="sky")
    db.session.add(row)
    db.session.commit()
    return row


def _login_as(client, login, email: str) -> None:
    client.post("/auth/logout")
    login(email, "correct horse")


# --- contacts CRUD -----------------------------------------------------------


def test_contact_create_renders_on_index(logged_in_client):
    page = logged_in_client.post(
        "/contacts/add",
        data={"name": "Ada Lovelace", "phone": "+91 98765 43210", "dob": "2000-02-29"},
        follow_redirects=True,
    ).get_data(as_text=True)

    assert "Ada Lovelace" in page and "29 Feb" in page


def test_contact_form_rejects_letters_in_phone(logged_in_client):
    logged_in_client.post("/contacts/add", data={"name": "Bad Phone", "phone": "call-me"})
    assert db.session.query(Contact).filter_by(name="Bad Phone").count() == 0


def test_contact_edit_updates_name(session, logged_in_client):
    user = db.session.query(User).first()
    row_id = _contact(user.id, name="Before").id

    logged_in_client.post(
        f"/contacts/{row_id}/edit",
        data={"name": "After", "phone": "", "email": "", "notes": ""},
        follow_redirects=True,
    )

    assert db.session.get(Contact, row_id).name == "After"


def test_contact_delete_removes_row(session, logged_in_client):
    user = db.session.query(User).first()
    row = _contact(user.id)

    logged_in_client.post(f"/contacts/{row.id}/delete", follow_redirects=True)

    assert db.session.get(Contact, row.id) is None


def test_foreign_contact_is_invisible_not_forbidden(client, make_user, login, session):
    alice = make_user(username="alice", email="alice@example.com")
    make_user(username="bob", email="bob@example.com")
    row = _contact(alice.id, name="Alices friend")

    _login_as(client, login, "bob@example.com")

    edit = client.get(f"/contacts/{row.id}/edit")
    delete = client.post(f"/contacts/{row.id}/delete")

    assert edit.status_code == 404
    assert delete.status_code == 404
    assert db.session.get(Contact, row.id) is not None


# --- birthday engine ---------------------------------------------------------


def test_feb29_falls_back_to_feb28_in_common_year(session, make_user):
    user = make_user()
    _contact(user.id, name="Leap Lucy", dob=date(2000, 2, 29))

    hits = upcoming_birthdays(user.id, date(2027, 2, 25))

    assert [(c.name, anniv, age) for c, anniv, age in hits] == [
        ("Leap Lucy", date(2027, 2, 28), 27)
    ]


def test_december_window_wraps_into_january(session, make_user):
    user = make_user()
    _contact(user.id, name="Jan Kim", dob=date(1995, 1, 2))

    hits = upcoming_birthdays(user.id, date(2026, 12, 28))

    assert [(c.name, anniv, age) for c, anniv, age in hits] == [("Jan Kim", date(2027, 1, 2), 32)]


def test_contact_outside_window_is_not_listed(session, make_user):
    user = make_user()
    _contact(user.id, name="Late Larry", dob=date(2000, 2, 10))

    assert upcoming_birthdays(user.id, date(2027, 3, 1)) == []


def test_contacts_without_dob_are_ignored(session, make_user):
    user = make_user()
    _contact(user.id, name="No Date Dan", dob=None)

    assert upcoming_birthdays(user.id, date(2027, 3, 1)) == []


# --- habits + streaks --------------------------------------------------------


def test_streak_counts_across_month_boundary():
    logged = {date(2026, 7, 29) + timedelta(days=i) for i in range(6)}

    current, longest = habit_streaks(logged, date(2026, 8, 3))

    assert (current, longest) == (6, 6)


def test_gap_splits_current_from_longest():
    logged = {
        date(2026, 7, 29),
        date(2026, 7, 30),
        date(2026, 7, 31),
        date(2026, 8, 2),
        date(2026, 8, 3),
    }

    current, longest = habit_streaks(logged, date(2026, 8, 3))

    assert (current, longest) == (2, 3)


def test_today_grace_does_not_break_yesterday_chain():
    logged = {date(2026, 8, 1), date(2026, 8, 2)}

    current, _ = habit_streaks(logged, date(2026, 8, 3))

    assert current == 2


def test_toggle_double_post_nets_zero_logs(session, logged_in_client):
    user = db.session.query(User).first()
    row = _habit(user.id)

    logged_in_client.post(f"/habits/{row.id}/toggle")
    logged_in_client.post(f"/habits/{row.id}/toggle")

    assert db.session.query(HabitLog).count() == 0


def test_unique_pair_survives_direct_duplicate_insert(app, session, make_user):
    user = make_user()
    row = _habit(user.id)
    day = date.today()

    with app.app_context():
        db.session.add(HabitLog(habit_id=row.id, log_date=day))
        db.session.add(HabitLog(habit_id=row.id, log_date=day))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_habit_grid_renders_sixty_literal_cells(session, logged_in_client):
    user = db.session.query(User).first()
    row = _habit(user.id)
    today = date.today()
    for offset in range(8):
        db.session.add(HabitLog(habit_id=row.id, log_date=today - timedelta(days=offset)))
    db.session.commit()

    page = logged_in_client.get("/habits").get_data(as_text=True)

    assert page.count("aspect-square") == 60
    assert "bg-sky-500" in page
    assert 'aria-label="8-day streak"' in page


def test_foreign_habit_toggle_returns_404_and_changes_nothing(client, make_user, login, session):
    alice = make_user(username="alice", email="alice@example.com")
    make_user(username="bob", email="bob@example.com")
    row = _habit(alice.id)

    _login_as(client, login, "bob@example.com")

    response = client.post(f"/habits/{row.id}/toggle")

    assert response.status_code == 404
    assert db.session.query(HabitLog).count() == 0


# --- mood --------------------------------------------------------------------


def test_same_day_mood_upsert_replaces_score(session, logged_in_client):
    for score in ("4", "2"):
        logged_in_client.post(
            "/mood/set",
            data={"mood_date": "2026-08-26", "score": score, "note": "day"},
        )

    rows = db.session.query(Mood).all()

    assert len(rows) == 1
    assert rows[0].score == 2


def test_mood_score_check_rejects_out_of_range(app, session, make_user):
    user = make_user()

    with app.app_context():
        db.session.add(Mood(user_id=user.id, mood_date=date(2026, 8, 26), score=9))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_month_view_scopes_to_requested_month(logged_in_client):
    logged_in_client.post("/mood/set", data={"mood_date": "2026-07-15", "score": "3"})
    logged_in_client.post("/mood/set", data={"mood_date": "2026-08-01", "score": "5"})

    july = logged_in_client.get("/mood?month=2026-07").get_data(as_text=True)

    assert "Average 3.0" in july and "5/5" not in july


def test_bad_month_parameter_is_a_404(logged_in_client):

    assert logged_in_client.get("/mood?month=nonsense").status_code == 404


# --- expenses ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "cents"),
    [("9.99", 999), ("1234.56", 123456), ("0.1", 10), ("1,250", 125000)],
)
def test_money_strings_parse_to_exact_cents(raw, cents):
    from saathi.services.money import parse_to_cents

    assert parse_to_cents(raw) == cents


def test_three_decimal_amount_is_rejected_by_form(logged_in_client):
    logged_in_client.post(
        "/expenses/add",
        data={"amount": "19.999", "category": "food", "spent_on": "2026-08-26"},
    )

    assert db.session.query(Expense).count() == 0


def test_month_totals_group_by_category_with_bar_widths(logged_in_client):
    for amount, category in (("750", "food"), ("249.50", "books")):
        logged_in_client.post(
            "/expenses/add",
            data={
                "amount": amount,
                "category": category,
                "spent_on": "2026-08-26",
                "note": "",
            },
        )

    page = logged_in_client.get("/expenses").get_data(as_text=True)

    assert 'style="width: 75%"' in page
    assert 'style="width: 25%"' in page


def test_expense_row_never_round_trips_through_float(session, make_user):
    user = make_user()
    row = Expense(
        user_id=user.id,
        amount_cents=999,
        spent_on=date(2026, 8, 26),
        category="books",
    )
    db.session.add(row)
    db.session.commit()

    assert db.session.get(Expense, row.id).amount_cents == 999


def test_foreign_expense_delete_returns_404(client, make_user, login, session):
    from datetime import date as d

    alice = make_user(username="alice", email="alice@example.com")
    make_user(username="bob", email="bob@example.com")
    row = Expense(user_id=alice.id, amount_cents=100, spent_on=d(2026, 8, 1), category="fun")
    db.session.add(row)
    db.session.commit()

    _login_as(client, login, "bob@example.com")

    assert client.post(f"/expenses/{row.id}/delete").status_code == 404


# --- optional birthday->event sync -------------------------------------------


def test_birthday_events_off_by_default(session, make_user):
    from saathi.models import Event
    from saathi.services import daily

    user = make_user()
    _contact(user.id, name="Quiet Quinn", dob=date(1990, 6, 15))
    daily._last_sync_day = None

    with __import__("flask").current_app.app_context():
        assert daily.maybe_sync_birthday_events(today=date(2026, 8, 26)) == 0

    assert db.session.query(Event).count() == 0


def test_birthday_events_created_once_then_deduped(app, session, make_user):
    from saathi.models import Event
    from saathi.services import daily

    user = make_user()
    _contact(user.id, name="Eventful Eve", dob=date(1990, 9, 30))
    app.config["BIRTHDAYS_AS_EVENTS"] = True

    daily._last_sync_day = None
    assert daily.maybe_sync_birthday_events(today=date(2026, 8, 26)) == 1

    daily._last_sync_day = None
    assert daily.maybe_sync_birthday_events(today=date(2026, 8, 27)) == 0

    events = db.session.query(Event).all()
    assert len(events) == 1
    assert events[0].title == "Birthday: Eventful Eve"
    assert events[0].repeat_rule == "yearly"


@pytest.mark.parametrize("raw", ["19.999", "abc", "-5"])
def test_money_garbage_raises_value_error(raw):
    from saathi.services.money import parse_to_cents

    with pytest.raises(ValueError):
        parse_to_cents(raw)
