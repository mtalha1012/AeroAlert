from playwright.sync_api import sync_playwright, Playwright
import os
import shutil
import subprocess
import time

page = None
playwright = None
context = None

subprocess.run("taskkill /f /im chrome.exe /t", shell=True, capture_output=True)
subprocess.run("taskkill /f /im chromium.exe /t", shell=True, capture_output=True)

def cache_cleanup():
    while True:
        time.sleep(3600)
        USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "WhatsApp_profile")
        for cache in ["Cache", "Code Cache", "GPUCache", "DawnCache", "Service Worker/ScriptCache", "GrShaderCache"]:
            cache_path = os.path.join(USER_DATA_DIR, "Default", cache)
            if os.path.exists(cache_path):
                try:
                    shutil.rmtree(cache_path)
                except PermissionError:
                    print(f"Skipped: {cache_path}")

def start_whatsApp():
    global page, playwright, context
    USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "WhatsApp_profile")

    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        args=[
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disk-cache-size=0",
            "--media-cache-size=0",
            "--js-flags=--no-compilation-cache"
        ]
    )
    page = context.pages[0] if context.pages else context.new_page()

def open_whatsApp():
    global page
    page.goto("https://web.whatsapp.com")

def send_msg(contact_name, message):
    global page
    page.wait_for_timeout(5000)

    searchbox = page.get_by_role("textbox", name="Search or start a new chat")
    searchbox.wait_for(timeout=60000)
    searchbox.fill(contact_name)
    page.wait_for_timeout(2000)

    page.get_by_title(contact_name).first.click()

    textbox = page.get_by_role("textbox", name="Type a message")
    textbox.wait_for(timeout=10000)
    textbox.fill(message)
    page.wait_for_timeout(500)

    page.keyboard.press("Enter")

    page.wait_for_timeout(7000)

def close_whatsApp():
    global page, context, playwright
    if context:
        context.close()
    if playwright:
        playwright.close()