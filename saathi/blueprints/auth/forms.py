"""WTForms for register and login."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import Field, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from ...extensions import db
from ...models import User


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")

    def validate_username(self, field: Field) -> None:
        taken = User.query.filter(
            db.func.lower(User.username) == field.data.strip().lower()
        ).first()
        if taken:
            raise ValidationError("This username is already taken.")

    def validate_email(self, field: Field) -> None:
        taken = User.query.filter(db.func.lower(User.email) == field.data.lower()).first()
        if taken:
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    # No remember-me field by decision (B03 §1): a persistent token widens exposure for no gain.
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class TwoFaConfirmForm(FlaskForm):
    """Second step of setup: first code from the freshly scanned secret."""

    code = StringField("6-digit code", validators=[DataRequired(), Length(min=6, max=8)])
    submit = SubmitField("Verify and turn on 2FA")


class TwoFaLoginForm(FlaskForm):
    """At /login/two-fa: accepts a TOTP or a backup code in one box."""

    code = StringField(
        "Authenticator code or backup code",
        validators=[DataRequired(), Length(min=6, max=16)],
    )
    submit = SubmitField("Verify")


class TwoFaDisableForm(FlaskForm):
    """Turning 2FA off needs both factors — a hijacked session alone can't."""

    password = PasswordField("Current password", validators=[DataRequired()])
    code = StringField("Current authenticator or backup code", validators=[DataRequired()])
    submit = SubmitField("Turn off 2FA")
