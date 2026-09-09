-- Saathi SQLite Database Schema

CREATE TABLE search_cache (
	query_hash VARCHAR(64) NOT NULL, 
	query_text VARCHAR(200) NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	payload_json TEXT NOT NULL, 
	fetched_at DATETIME NOT NULL, 
	PRIMARY KEY (query_hash)
);

CREATE TABLE weather_cache (
	city_key VARCHAR(120) NOT NULL, 
	payload_json TEXT NOT NULL, 
	fetched_at DATETIME NOT NULL, 
	PRIMARY KEY (city_key)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	deleted_at DATETIME, 
	ics_token VARCHAR(64), 
	totp_secret VARCHAR(64), 
	twofa_enabled BOOLEAN NOT NULL, 
	session_invalid_before DATETIME, 
	digest_enabled BOOLEAN NOT NULL, 
	digest_last_sent_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_users_password_hash CHECK (length(password_hash) > 0), 
	UNIQUE (username), 
	UNIQUE (email), 
	UNIQUE (ics_token)
);

CREATE TABLE login_attempts (
	id INTEGER NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	attempted_at DATETIME NOT NULL, 
	success BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE tags (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(40) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_tags_user_name UNIQUE (user_id, name), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE uploads (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	original_filename VARCHAR(255) NOT NULL, 
	stored_filename VARCHAR(64) NOT NULL, 
	mime_type VARCHAR(120), 
	size_bytes INTEGER NOT NULL, 
	is_image BOOLEAN NOT NULL, 
	uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_uploads_size CHECK (size_bytes >= 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (stored_filename)
);

CREATE TABLE profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	sex VARCHAR(20), 
	date_of_birth DATE, 
	phone VARCHAR(30), 
	address VARCHAR(255), 
	headline VARCHAR(140), 
	skills_csv TEXT, 
	summary TEXT, 
	likes TEXT, 
	dislikes TEXT, 
	public_token VARCHAR(43), 
	share_enabled BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (public_token)
);

CREATE TABLE education_entries (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	institution VARCHAR(150) NOT NULL, 
	qualification VARCHAR(150) NOT NULL, 
	field_of_study VARCHAR(150), 
	start_date DATE, 
	end_date DATE, 
	description TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE work_entries (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	organization VARCHAR(150) NOT NULL, 
	role VARCHAR(150) NOT NULL, 
	location VARCHAR(120), 
	start_date DATE, 
	end_date DATE, 
	description TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE contacts (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	dob DATE, 
	notes TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE habits (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	color VARCHAR(10), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE moods (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	mood_date DATE NOT NULL, 
	score INTEGER NOT NULL, 
	note TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_moods_user_date UNIQUE (user_id, mood_date), 
	CONSTRAINT ck_moods_score CHECK (score BETWEEN 1 AND 5), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE expenses (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	amount_cents INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	category VARCHAR(40) NOT NULL, 
	spent_on DATE NOT NULL, 
	note TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_expenses_nonneg CHECK (amount_cents >= 0), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE events (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	event_at DATETIME NOT NULL, 
	repeat_rule VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	fired_at DATETIME, 
	alert_lead_minutes INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_events_alert_lead CHECK (alert_lead_minutes >= 0 AND alert_lead_minutes <= 10080), 
	CONSTRAINT ck_events_repeat_rule CHECK (repeat_rule IN ('none','daily','weekly','monthly','yearly')), 
	CONSTRAINT ck_events_status CHECK (status IN ('scheduled','fired','fired_late','missed','cancelled')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE capsule_messages (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	body TEXT NOT NULL, 
	open_at DATETIME NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_capsules_status CHECK (status IN ('sealed','opened')), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE backup_codes (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	code_hash VARCHAR(64) NOT NULL, 
	used_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (code_hash)
);

CREATE TABLE logins (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	at DATETIME NOT NULL, 
	ip VARCHAR(45), 
	user_agent VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE notes (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	event_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	pinned BOOLEAN NOT NULL, 
	archived BOOLEAN NOT NULL, 
	deleted_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE SET NULL
);

CREATE TABLE activity_log (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	event_id INTEGER, 
	activity_type VARCHAR(30) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	details VARCHAR(255), 
	occurred_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE SET NULL
);

CREATE TABLE habit_logs (
	id INTEGER NOT NULL, 
	habit_id INTEGER NOT NULL, 
	log_date DATE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_habit_logs_habit_date UNIQUE (habit_id, log_date), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE
);

CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	event_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	read_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE SET NULL
);

CREATE TABLE note_tags (
	note_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	PRIMARY KEY (note_id, tag_id), 
	FOREIGN KEY(note_id) REFERENCES notes (id) ON DELETE CASCADE, 
	FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

