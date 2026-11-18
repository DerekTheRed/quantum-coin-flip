import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from coin import QuantumCoin
from config import IG_USERNAME, IG_PASSWORD

BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "session.json"

POLL_SECONDS = 10        # how often to check for new DMs
USER_COOLDOWN = 30       # seconds a user must wait between flips
COMMAND = "!flip"


def login() -> Client:
    """Log in, reusing a saved session so we don't re-auth (and get flagged) every run."""
    cl = Client()
    cl.delay_range = [1, 3]  # small random delay between API calls

    if SESSION_FILE.exists():
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.get_timeline_feed()  # cheap call to confirm the session is valid
            return cl
        except LoginRequired:
            print("Saved session expired, logging in fresh.")
            cl = Client()
            cl.delay_range = [1, 3]

    cl.login(IG_USERNAME, IG_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    return cl


def fetch_threads(cl: Client):
    """Inbox plus message requests (people who don't follow you land in pending)."""
    threads = list(cl.direct_threads(amount=20))
    try:
        threads += cl.direct_pending_inbox(amount=20)
    except Exception as e:
        print(f"Couldn't read pending inbox: {e}")
    return threads


def handle_flip(cl: Client, coin: QuantumCoin, thread_id: str) -> None:
    """Runs in a worker thread: the quantum job can take a while in the queue."""
    try:
        cl.direct_answer(thread_id, "Connecting to IBM's quantum computer...")
        flip = coin.flip()
        reply = (
            f"{flip['result']}!\n"
            f"Qubit string: {flip['bitstring']}"
        )
    except Exception as e:
        traceback.print_exc()
        reply = f"Error: {e}"

    try:
        cl.direct_answer(thread_id, reply)
    except Exception as e:
        print(f"Failed to send reply: {e}")


def run() -> None:
    cl = login()
    my_id = str(cl.user_id)
    coin = QuantumCoin()
    pool = ThreadPoolExecutor(max_workers=2)

    # Mark everything already in the inbox as seen so we only react to NEW messages.
    seen: set[str] = set()
    for thread in fetch_threads(cl):
        for msg in thread.messages:
            seen.add(str(msg.id))

    last_flip: dict[str, float] = {}  # user_id -> timestamp of last flip
    print(f"Logged in as {IG_USERNAME}. Listening for {COMMAND!r}...")

    while True:
        try:
            for thread in fetch_threads(cl):
                for msg in reversed(thread.messages):  # oldest first
                    msg_id = str(msg.id)
                    if msg_id in seen:
                        continue
                    seen.add(msg_id)

                    if str(msg.user_id) == my_id:
                        continue  # ignore our own messages
                    if (msg.text or "").strip().lower() != COMMAND:
                        continue

                    sender = str(msg.user_id)
                    now = time.time()
                    if now - last_flip.get(sender, 0) < USER_COOLDOWN:
                        continue
                    last_flip[sender] = now

                    print(f"{COMMAND} from {sender} in thread {thread.id}")
                    pool.submit(handle_flip, cl, coin, thread.id)

        except LoginRequired:
            print("Session expired, logging back in.")
            cl = login()
            my_id = str(cl.user_id)
        except Exception as e:
            print(f"Poll failed: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()