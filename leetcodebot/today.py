from typing import Dict, Any

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import requests


def get_leetcode_daily_challenge() -> Dict[str, Any]:
    url = "https://leetcode.com/graphql"
    query = """
    query questionOfToday {
        activeDailyCodingChallengeQuestion {
            date
            userStatus
            link
            question {
                acRate
                difficulty
                freqBar
                frontendQuestionId: questionFrontendId
                isFavor
                paidOnly: isPaidOnly
                status
                title
                titleSlug
                hasVideoSolution
                hasSolution
                topicTags {
                    name
                    id
                    slug
                }
            }
        }
    }
    """
    json_data = {
        "query": query,
        "operationName": "questionOfToday"
    }

    response = requests.post(url, json=json_data, timeout=20)

    if response.status_code != 200:
        raise Exception("Failed to fetch data from LeetCode")

    data = response.json()

    if "errors" in data:
        raise Exception(f"Error fetching data: {data["errors"]}")

    daily_challenge = data["data"]["activeDailyCodingChallengeQuestion"]

    return daily_challenge


async def send_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        daily_challenge = get_leetcode_daily_challenge()
        question = daily_challenge["question"]
        answer = ""
        answer += f"*Title*: {question["frontendQuestionId"]}. {question["title"]}\n"
        answer += f"*Difficulty*: `{question["difficulty"]}`\n"
        answer += f"*Link*: https://leetcode.com{daily_challenge["link"]}\n"
        answer += f"*Acceptance Rate*: {question["acRate"]:.2f}%\n"
        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"Error occurred\n{str(e)}", parse_mode=ParseMode.MARKDOWN)
