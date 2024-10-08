import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import requests
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

usernames = [name.strip() for name in os.getenv("USERNAMES", default="").split(",")]


def get_leetcode_contest_rank(username: str) -> int:
    url = "https://leetcode.com/graphql"
    query = """
    query getContestInfo($username: String!) {
        userContestRanking(username: $username) {
            globalRanking
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
    response = requests.post(url, json=json_data)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch data for user {username}")

    data = response.json()
    if "errors" in data:
        raise Exception(f"Error fetching data for user {username}: {data["errors"]}")

    try:
        ranking = data["data"]["userContestRanking"]["globalRanking"]
    except TypeError:
        ranking = 1_000_000_000

    return ranking


async def get_contest_for_users(usernames: List[str]) -> Dict[str, str]:
    user_ranks = {}
    with ThreadPoolExecutor(max_workers=len(usernames)) as executor:
        future_to_username = {executor.submit(get_leetcode_contest_rank, username): username for username in usernames}

        for future in as_completed(future_to_username):
            username = future_to_username[future]
            try:
                result = future.result()
                user_ranks[username] = result
            except Exception as exc:
                user_ranks[username] = str(exc)

    return user_ranks


async def send_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ranks = await get_contest_for_users(usernames)
    sorted_users = sorted(user_ranks.items(), key=lambda item: item[1])
    answer = "```Standings\n"
    for user in sorted_users:
        answer += f"{user[0]}\t{user[1]}\n"
    answer += "```"
    await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)
