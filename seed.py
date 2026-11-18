"""One-time script: fills the TriviaFact table. Run with:  python seed.py
Safe to re-run: it rebuilds ONLY the trivia_fact table, so users, donations
and communities are left untouched."""
from app import app
from models import db, TriviaFact

RC = "American Red Cross"
WHO = "World Health Organization (WHO)"

FACTS = [
    # category, title, body, source
    ("Blood types", "O negative is the universal red cell type",
     "Red cells from O negative donors can be given to patients of any blood type, which is why O negative blood is so often used in emergencies.", RC),
    ("Blood types", "AB positive is the universal plasma type",
     "Plasma from AB donors can be given to patients of any blood type.", RC),
    ("Blood types", "O positive is the most common blood type",
     "More people have O positive blood than any other type, so hospitals need a steady supply of it.", RC),
    ("Blood types", "AB negative is one of the rarest types",
     "Only about 1% of people in the U.S. have AB negative blood.", RC),
    ("Blood types", "You inherit your blood type",
     "Your ABO type and your Rh factor (positive or negative) are passed down from your biological parents.", RC),
    ("Blood types", "Blood is more than one thing",
     "A donation can be separated into red cells, plasma and platelets, and each part can help a different patient.", WHO),

    ("Donation tips", "Wait 8 weeks between whole blood donations",
     "Donors need to wait at least 56 days (8 weeks) between whole blood donations so the body can recover. This is the same gap used for the 'next eligible' date in this app.", RC),
    ("Donation tips", "Drink water and eat well beforehand",
     "Have a healthy meal and drink plenty of fluids before you donate, and keep drinking afterwards.", RC),
    ("Donation tips", "Eat iron-rich foods",
     "Foods like red meat, fish, poultry, beans, spinach and iron-fortified cereals help keep your iron levels up.", RC),
    ("Donation tips", "The donation itself is quick",
     "Giving whole blood usually takes about 8 to 10 minutes. The whole visit, including the health check and snack, takes around an hour.", RC),
    ("Donation tips", "One donation can help up to three people",
     "Because blood is separated into parts, a single donation can help several patients.", RC),
    ("Donation tips", "Bring ID and get some rest",
     "Bring a form of identification and try to get a good night's sleep before your appointment.", RC),

    ("Myths", "Myth: donating blood is very painful",
     "Most donors only feel a quick pinch when the needle goes in.", RC),
    ("Myths", "Myth: you can catch a disease by donating",
     "A new, sterile needle is used for every donor and thrown away afterwards, so you cannot get an infection from donating.", RC),
    ("Myths", "Myth: donating leaves you weak for days",
     "Your body replaces the fluid you gave within about 24 hours and the red cells within a few weeks. Most people feel fine after resting and drinking fluids.", RC),
    ("Myths", "Myth: I'm too old to donate",
     "In many places there is no fixed upper age limit as long as you are healthy and meet the requirements. Rules vary, so check with your local blood service.", RC),
    ("Myths", "Myth: a tattoo means I can never donate",
     "Usually it only means a waiting period, and the rules differ between countries and blood services. Ask your local blood service before you assume.", RC),
    ("Myths", "Myth: blood is only needed after disasters",
     "Blood is needed every day, for surgery, childbirth complications, cancer treatment and accidents.", WHO),
]

with app.app_context():
    TriviaFact.__table__.drop(db.engine, checkfirst=True)   # rebuilds the table with the new columns
    TriviaFact.__table__.create(db.engine)
    for category, title, body, source in FACTS:
        db.session.add(TriviaFact(category=category, title=title, body=body, source=source))
    db.session.commit()
    print(f"Added {len(FACTS)} trivia facts.")
