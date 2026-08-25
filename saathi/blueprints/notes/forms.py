"""WTForms for note create/edit."""

from __future__ import annotations

from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from ...extensions import db
from ...models import Event


class NoteForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)])
    body = TextAreaField("Body (markdown)", validators=[Optional(), Length(max=50_000)])
    tags = StringField("Tags (comma separated)", validators=[Optional(), Length(max=400)])
    event_id = SelectField("Linked event", coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField("Save note")
    preview = SubmitField("Preview")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        events = db.session.scalars(
            select(Event).where(Event.user_id == current_user.id).order_by(Event.event_at.desc())
        ).all()
        self.event_id.choices = [(0, "— none —")] + [(e.id, e.title) for e in events]

    def validate_event_id(self, field: SelectField) -> None:
        if field.data == 0:
            field.data = None
