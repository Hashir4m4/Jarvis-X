from backend.browser.manager import BrowserManager
import logging

logging.basicConfig(level=logging.INFO)
manager = BrowserManager()

print("1. Launch browser.")
session_id = manager.create_session()
print(f"Session created: {session_id}")

print("2. Navigate to a safe website (example.com).")
result = manager.read_page(session_id, "https://example.com")
if not result["success"]:
    print("FAILED TO READ PAGE")
    exit(1)

print("3. Read title.")
print(f"Title: {result.get('title')}")

print("4. Extract visible text (first 100 chars).")
print(f"Text: {result.get('content', '')[:100]}...")

print("5. Extract links.")
print(f"Links count: {len(result.get('links', []))}")

print("6. Perform a safe search.")
search_result = manager.search_web(session_id, "quantum computing")
if not search_result["success"]:
    print("FAILED SEARCH")
    exit(1)

print("7. Open a result.")
first_result_url = search_result["results"][0]["url"]
print(f"Opening: {first_result_url}")
result2 = manager.read_page(session_id, first_result_url)

print("8. Return to previous page.")
session = manager.get_session(session_id)
prev_url = session.go_back()
print(f"Returned to: {prev_url}")

print("9. Close browser.")
manager.close_session(session_id)
print("LIVE TEST PASSED")
