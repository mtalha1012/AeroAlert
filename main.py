import threading
import time

from google.genai.errors import ServerError, ClientError
from imap_tools import MailBox
import traceback
import re
from email.utils import parseaddr
from WhatsApp_tester import send_msg, start_whatsApp, open_whatsApp, cache_cleanup
from config import GEMINI_API_KEY, EMAIL, APP_PASSWORD, ALLOWED_SENDERS, DECISION_PROMPT, TEACHERS, CAPTION_PROMPT, \
    GEMINI_MODEL, CONTACT_NAME
from google import genai
import json
import unicodedata
from difflib import SequenceMatcher
import datetime

client = genai.Client(api_key=GEMINI_API_KEY)

def normalize_name(name):
    name = name.lower()
    name = ' '.join(name.split())
    name = unicodedata.normalize("NFKD", name)
    return name

def similarity(a: str, b: str):
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()

NORMALIZED_SENDERS = {normalize_name(n): v for n, v in ALLOWED_SENDERS.items()}
NORMALIZED_TEACHERS = {normalize_name(n): [t, c] for n,(t,c) in TEACHERS.items()}

def get_priority(email, name):
    if re.search(r"\.(bs|ms)[a-z]+\d+", email):
        return {"priority": 0, "course": None, "type": None}
    elif email in ALLOWED_SENDERS.values():
        for n in NORMALIZED_SENDERS.keys():
            if similarity(name, n) > 0.8:
                return {"priority": 3, "course": NORMALIZED_TEACHERS[n][1], "type": NORMALIZED_TEACHERS[n][0]}
        return {"priority": 3, "course": None, "type": None}
    elif re.match(r".*@seecs.edu.pk", email):
        return {"priority": 2, "course": None, "type": None}
    else:
        return {"priority": 1, "course": None, "type": None}

known_uids = set()

def process_email(msg):
    try:
        name, email = parseaddr(msg.from_)
        priority = get_priority(email, name)
        decision = {"share": False, "caption": ""}
        if 'mtalha.bscs25seecs@seecs.edu.pk' in msg.to:
            decision["share"] = False
            print("personal")
        elif 'bscs15a@seecs.edu.pk' in msg.to:
            for sender in NORMALIZED_SENDERS.keys():
                if similarity(sender, name) > 0.8:
                    decision["share"] = True
                    decision["caption"] = gemini_call(msg.subject, msg.text)["caption"]
                    print("auto else")
            decision = gemini_call(msg.subject, msg.text, msg.from_,priority)
        else:
            print(datetime.datetime.now().strftime('%H:%M:%S.%f') + ": gemini_decide called")
            decision = gemini_call(msg.subject, msg.text, msg.from_,priority)
            print(datetime.datetime.now().strftime('%H:%M:%S.%f') + "gemini response received")
        if decision['share']:
            send_msg(CONTACT_NAME,decision['caption'])
            print(f"🆕 New Email!")
            print(f"Subject : {msg.subject}")
            print(f"From    : {msg.from_}")
            print(f"Body    : {msg.text[:200]}")
            print("-" * 40)
        else:
            print("Not passed")
    except Exception as e:
        traceback.print_exc()


def start_alert():
    while True:
        try:
            print("Connecting...")
            with MailBox("imap.gmail.com").login(EMAIL, APP_PASSWORD, initial_folder="inbox") as mailbox:
                print("login successful")
                if not known_uids:
                    count = 0
                    for msg in mailbox.fetch(mark_seen=False, reverse = True, limit = 5):
                        print(msg.to, end='\n')
                        known_uids.add(msg.uid)
                        count += 1
                        print(f"Loaded {count} older emails...")

                    print(f"Watching for new emails. ({len(known_uids)} existing emails ignored)")

                while True:
                    responses = mailbox.idle.wait(timeout=3)
                    for msg in mailbox.fetch(mark_seen=False, reverse = True, limit = 5):
                        if msg.uid not in known_uids:
                            print(datetime.datetime.now().strftime('%H:%M:%S.%f') + "Email detected")
                            print("new email")
                            known_uids.add(msg.uid)
                            process_email(msg)
                    if not responses:
                        print("Still watching...")

        except KeyboardInterrupt:
            print("Stopping bot.")
            break

        except Exception as e:
            traceback.print_exc()
            print(f"Connection lost ({e.__class__.__name__}). Reconnecting in 5 seconds...")

def strip_json(response):
    raw = response.text.strip()
    if not raw:
        print("Gemini returned empty response")
        return {"share": False, "caption": ""}
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)

def gemini_call(subject, text, sender=None, priority=None):
    response = None
    try:
        if sender and priority:
            response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=(f"{DECISION_PROMPT}teachers: {TEACHERS} priority: {priority} "
                      f"subject: {subject} text: {text} sender: {sender}"))
        else:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=(f"{CAPTION_PROMPT} subject: {subject} text: {text}")
            )
        return strip_json(response)
    except (ServerError, ClientError) as e:
        print("Gemini busy. Retrying in 10s")
        print(e)
        time.sleep(10)
        return gemini_call(subject, text, sender, priority)


if __name__ == "__main__":
    threading.Thread(target=cache_cleanup, daemon=True).start()
    start_whatsApp()
    open_whatsApp()
    start_alert()


