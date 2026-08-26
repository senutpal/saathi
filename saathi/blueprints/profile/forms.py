"""WTForms for personal data and education/work entries."""

from __future__ import annotations

from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from ...utils import PHONE_CHARS

MIN_BIRTH_YEAR = 1900


def _not_future(_form: FlaskForm, field: object) -> None:
    if field.data and field.data > date.today():
        raise ValidationError("Date cannot be in the future.")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    headline = StringField("Headline", validators=[Length(max=140)])
    sex = SelectField(
        "Sex",
        choices=[
            ("", "—"),
            ("female", "Female"),
            ("male", "Male"),
            ("other", "Other"),
            ("prefer_not_to_say", "Prefer not to say"),
        ],
        validators=[Optional()],
    )
    date_of_birth = DateField(
        "Date of birth",
        format="%Y-%m-%d",
        validators=[Optional(), _not_future],
    )
    phone = StringField("Phone", validators=[Length(max=30)])
    address = TextAreaField("Address", validators=[Length(max=255)])
    skills_csv = TextAreaField("Skills (comma-separated)", validators=[Length(max=500)])
    summary = TextAreaField("Summary", validators=[Length(max=2000)])
    likes = TextAreaField("Likes", validators=[Length(max=1000)])
    dislikes = TextAreaField("Dislikes", validators=[Length(max=1000)])
    submit = SubmitField("Save profile")

    def validate_date_of_birth(self, field: object) -> None:
        if field.data and field.data.year < MIN_BIRTH_YEAR:
            raise ValidationError("Year must be 1900 or later.")

    def validate_phone(self, field: object) -> None:
        # Charset allowlist only (ADR-020): rejects letters, never a valid format.
        if field.data and not all(PHONE_CHARS.fullmatch(ch) for ch in field.data):
            raise ValidationError("Phone may contain digits, spaces and + - ( ) . only.")


class EducationForm(FlaskForm):
    institution = StringField("Institution", validators=[DataRequired(), Length(max=150)])
    qualification = StringField("Qualification", validators=[DataRequired(), Length(max=150)])
    field_of_study = StringField("Field of study", validators=[Length(max=150)])
    start_date = DateField("Start date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End date", format="%Y-%m-%d", validators=[Optional()])
    description = TextAreaField("Description", validators=[Length(max=500)])
    submit = SubmitField("Add")

    def validate_end_date(self, field: object) -> None:
        start = self.start_date.data
        if field.data and start and field.data < start:
            raise ValidationError("End date must be on or after the start date.")


class WorkForm(FlaskForm):
    organization = StringField("Organization", validators=[DataRequired(), Length(max=150)])
    role = StringField("Role", validators=[DataRequired(), Length(max=150)])
    location = StringField("Location", validators=[Length(max=120)])
    start_date = DateField("Start date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End date", format="%Y-%m-%d", validators=[Optional()])
    description = TextAreaField("Description", validators=[Length(max=500)])
    submit = SubmitField("Add")

    def validate_end_date(self, field: object) -> None:
        start = self.start_date.data
        if field.data and start and field.data < start:
            raise ValidationError("End date must be on or after the start date.")
