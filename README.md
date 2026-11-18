# Red String - Blood Registry

A community-driven blood donor networking platform (Flask + MySQL) for connecting donors,
tracking donations, and building communities that save lives.

## User stories
1. As a visitor I can read blood-donation facts on the Home and Learn pages.
2. As a visitor I can register and log in (passwords are hashed).
3. As a donor I can edit my profile (name, blood type, bio, picture) and choose public or private.
4. As a donor I can record my weight, height and health check-ups; my BMI is calculated.
5. As a donor I can log donations and see my points, badge, and next eligible date.
6. As a donor I can create, join and leave communities and tag donations with one.
7. Anyone can view a public profile; private profiles are hidden from other people.

## Setup (Windows + XAMPP)
1. Start **MySQL** in the XAMPP control panel.
2. Create a virtual environment and install the requirements:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and edit it (XAMPP default: user `root`, empty password).
4. Create the database and tables (safe to run again):
   ```
   python setup_db.py
   ```
5. Run the app: `python app.py` then open http://127.0.0.1:5000

## Run the tests
```
python -m pytest
```
The tests use a **fake database connection** (`tests/fakes.py`), so MySQL does not need to be running.

## Folder structure
```
app.py            Flask routes (front end): read the form -> call a service -> render
templates/        HTML pages (Jinja + Bootstrap)         static/   CSS and images
registry/
  exceptions.py   custom exception hierarchy (RegistryError and children)
  models.py       OOP domain classes (abstract Measurement, BadgeTier strategies, validation)
  repositories.py ALL SQL, only %s parameters
  services.py     business rules and transactions
  db.py           connection, schema runner, Transaction (commit/rollback)
  storage.py      profile picture files
sql/              01_schema.sql, 02_seed.sql (run by setup_db.py)
tests/            pytest suite with a fake database
```

## Design notes
- **OOP:** abstract `Measurement` -> `Weight` / `Height` (polymorphic `describe()`); `User` has a
  `Profile` and `DonationHistory` has `Donation`s (composition); setters and `BoundedText`
  validate every value (encapsulation). **Design pattern:** Strategy (`BadgePolicy` + `BadgeTier`).
- **Errors:** every failure is a `RegistryError` shown as a friendly message; database errors never
  leak SQL to the user.
- **Transactions:** registering (user + profile) and creating a community (community + creator
  membership) each commit together or roll back together.
- **Secrets:** `.env` is git-ignored; only `.env.example` is committed.

## Team contributions
| Member | What they built | Commits |
|--------|-----------------|---------|
| (name) | (parts)         | (run `git shortlog -sn`) |
| (name) | (parts)         |         |
