import os
from typing import Tuple, Optional

import requests

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from leetcodebot.today import get_leetcode_daily_challenge


usernames = [name.strip() for name in os.getenv("USERNAMES", default="").split(",")]


def solved_today(username: str, title_slug: str) -> Tuple[bool, bool, Optional[str], Optional[str], Optional[str]]:
    url = "https://leetcode.com/graphql"
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

    response = requests.post(url, json=json_data, timeout=20)

    if response.status_code != 200:
        raise Exception("Failed to fetch data from LeetCode")

    data = response.json()

    if "errors" in data:
        raise Exception(f"Error fetching data: {data["errors"]}")

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
                        link = f"https://leetcode.com/problems/{question["titleSlug"]}/submissions/{submission_id}/"
                        answers[username] = f"✅\t{username}, [{runtime}, {memory}]({link})\n"
                    else:
                        answers[username] = f"{"☑️" if another else "⬜️"}\t{username}\n"
                except Exception:
                    answers[username] = f"⛔️\t{username}\n"

        sorted_info = sorted(answers.items(), key=lambda item: item[0])
        answer = ""
        for info in sorted_info:
            answer += f"{info[1]}"

        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Error occurred\n{str(e)}", parse_mode=ParseMode.MARKDOWN)
