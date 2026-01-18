import os
import time
from typing import Tuple, Optional

import cloudscraper
import requests

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from leetcodebot.today import get_leetcode_daily_challenge

scraper = cloudscraper.create_scraper()


usernames = [name.strip() for name in os.getenv("USERNAMES", default="").split(",")]


def solved_today(username: str, title_slug: str) -> Tuple[bool, bool, Optional[str], Optional[str], Optional[str]]:
    url = "https://leetcode.com/graphql"
    headers = {
        # LeetCode sometimes cuts "empty" queries (Cloudflare / rate limit).
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
    }
    query = """
    query recentAcSubmissions($username: String!) {
        recentAcSubmissionList(username: $username, limit: 20) {
            id
            titleSlug
            timestamp
            runtime
            memory
        }
    }
    """
    variables = {
        "username": username
    }
    json_data = {
        "query": query,
        "variables": variables
    }

    response = None
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            # timeout: (connect, read). With retries it’s better to fail fast on "hung" requests.
            response = scraper.post(url, json=json_data, headers=headers, timeout=(1, 3))
            # retry on typical transient statuses
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.4 * (2 ** attempt))
                continue
            break
        except (requests.Timeout, requests.RequestException) as e:
            last_exc = e
            time.sleep(0.4 * (2 ** attempt))

    if response is None:
        raise Exception(f"Failed to fetch data from LeetCode (network error: {type(last_exc).__name__})") from last_exc

    if response.status_code != 200:
        raise Exception("Failed to fetch data from LeetCode")

    try:
        data = response.json()
    except ValueError as e:
        raise Exception("Failed to parse LeetCode response") from e

    if "errors" in data:
        raise Exception(f"Error fetching data: {data['errors']}")

    now_utc = datetime.now(timezone.utc)
    start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    timestamp = int(start_of_today_utc.timestamp())

    array = data["data"]["recentAcSubmissionList"]
    last_solved = [x for x in array if int(x.get("timestamp")) > timestamp]

    for d in last_solved:
        if d["titleSlug"] == title_slug:
            return True, True, d["runtime"], d["memory"], d["id"]

    return len(last_solved) > 0, False, None, None, None


async def send_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        daily_challenge = get_leetcode_daily_challenge()
        question = daily_challenge["question"]
        answers = {}

        with ThreadPoolExecutor(max_workers=len(usernames)) as executor:
            future_to_username = {
                executor.submit(solved_today, username, question["titleSlug"]): username
                for username in usernames
            }

            for future in as_completed(future_to_username):
                username = future_to_username[future]
                try:
                    another, solved, runtime, memory, submission_id = future.result()
                    if solved:
                        link = f"https://leetcode.com/problems/{question['titleSlug']}/submissions/{submission_id}/"
                        answers[username] = f"✅\t{username}, [{runtime}, {memory}]({link})\n"
                    else:
                        checkbox = "☑️" if another else "⬜️"
                        answers[username] = f"{checkbox}\t{username}\n"
                except Exception:
                    answers[username] = f"⛔️\t{username}\n"

        sorted_info = sorted(answers.items(), key=lambda item: item[0])
        answer = ""
        for info in sorted_info:
            answer += f"{info[1]}"

        if all(info[1].startswith("✅") for info in sorted_info):
            answer += "\n\n🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉"

        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Error occurred\n{str(e)}", parse_mode=ParseMode.MARKDOWN)
