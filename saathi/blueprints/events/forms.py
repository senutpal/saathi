"""WTForms for reminder create/edit."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from ...models.base import utcnow
from ...utils import ist_to_utc_naive


class EventForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    event_at = DateTimeLocalField("When", validators=[DataRequired()])
    repeat_rule = SelectField(
        "Repeat",
        choices=[
            ("none", "Once"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        default="none",
        validators=[Optional()],
    )
    alert_lead_minutes = IntegerField(
        "Alert lead (minutes)", default=30, validators=[Optional(), NumberRange(min=0, max=10080)]
    )
    submit = SubmitField("Save reminder")

    def __init__(self, now_fn: Callable[[], datetime] = utcnow, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._now_fn = now_fn

    def validate_event_at(self, field: DateTimeLocalField) -> None:
        if field.data is not None and ist_to_utc_naive(field.data) <= self._now_fn():
            raise ValidationError("Time must be in the future.")
