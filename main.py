import json
import logging
import os

import boto3
import telebot

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_LOGS_FILENAME = os.environ["BOT_LOGS_FILENAME"]
LAMBDA_NAME = os.environ["LAMBDA_NAME"]
MASTER_CHAT_ID = json.loads(os.environ["MASTER_CHAT_ID"])

SUBSCRIBE_ACTION = "subscribe"
UNSUBSCRIBE_ACTION = "unsubscribe"
FORMATTER = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

bot = telebot.TeleBot(BOT_TOKEN)

logger = logging.getLogger(__name__)


def _setup_logger(logger):
    logger.setLevel(logging.DEBUG)
    log_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), BOT_LOGS_FILENAME
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FORMATTER)

    logger.addHandler(file_handler)


_setup_logger(logger)


def _get_lambda_env_vars(lambda_client) -> str:
    return lambda_client.get_function_configuration(FunctionName=LAMBDA_NAME)[
        "Environment"
    ]["Variables"]


def _is_action_required(chat_id, chat_id_list, action) -> bool:
    """
    Check if the chat ID is already present in the environment variables.
    """
    if action == SUBSCRIBE_ACTION:
        if chat_id in chat_id_list:
            logger.debug(
                "Action: %s is not required. Chat ID already subscribed to the bot.",
                action,
            )
            return False
    elif action == UNSUBSCRIBE_ACTION:
        if chat_id not in chat_id_list:
            logger.debug(
                f"Action: %s  is not required. Chat ID not unsubscribed to the bot.",
                action,
            )
            return False
    return True


def _handle_action(chat_id, chat_id_list: list, action: str):
    """
    Handle the user's action for subscription.
    """
    if _is_action_required(chat_id, chat_id_list, action):
        if action == SUBSCRIBE_ACTION:
            chat_id_list.append(chat_id)
            logger.debug("Successfully added chat ID to the subscribers.")
        elif action == UNSUBSCRIBE_ACTION:
            chat_id_list.remove(chat_id)
            logger.debug("Successfully removed chat ID from the subscribers.")
        else:
            raise Exception("Invalid action.")
    return True


def _update_chat_id_env_var(chat_id, action) -> bool:
    """
    Update the chat ID environment variable of the Lambda function.
    """
    lambda_client = boto3.client("lambda")
    env_vars = _get_lambda_env_vars(lambda_client)

    # Check if the chat ID is already present in the environment variables
    if "BOT_CHATID" in env_vars:
        chat_id_list = json.loads(env_vars["BOT_CHATID"])
        logger.debug("Chat ID list before action: %s - %s", action, chat_id_list)

        if _handle_action(chat_id, chat_id_list, action):
            env_vars["BOT_CHATID"] = str(chat_id_list)

            response = lambda_client.update_function_configuration(
                FunctionName=LAMBDA_NAME, Environment={"Variables": env_vars}
            )
        logger.debug("Chat ID list after action: %s - %s", action, chat_id_list)
        return response["ResponseMetadata"]["HTTPStatusCode"] == 200
    else:
        raise Exception("Environment variable 'BOT_CHATID' not found.")


def _is_chat_id_authorized(user_chat_id) -> bool:
    return user_chat_id in MASTER_CHAT_ID


def _get_user_name(chat_id) -> str:
    return " ".join(
        [
            bot.get_chat_member(chat_id, chat_id).user.first_name,
            bot.get_chat_member(chat_id, chat_id).user.last_name,
        ]
    )


def _get_subscriber_names() -> list:
    names_list = []
    chat_ids = _get_lambda_env_vars(boto3.client("lambda"))["BOT_CHATID"]
    for chat_id in json.loads(chat_ids):
        names_list.append(_get_user_name(chat_id))
    return names_list


@bot.message_handler(commands=["start"])
def send_welcome(message):
    msg = (
        "Hello! I am a bot that will notify you 10 and 5 minutes "
        + "before it's candle lighting time every Friday. \nTo subscribe "
        + "to the bot, type /subscribe. \nTo unsubscribe from the bot, type /unsubscribe.\n"
        + "To view the current subscribers, type /view (for admins only)."
    )
    bot.reply_to(message, msg)


@bot.message_handler(commands=["view"])
def view_subscribers(message):
    chat_id = message.chat.id
    message_reply = (
        f"Your subscribed users are {_get_subscriber_names()}."
        if _is_chat_id_authorized(chat_id)
        else "You are not authorized to perform this action."
    )
    bot.reply_to(message, message_reply)
    logger.info("User: %s viewed subscribers.", _get_user_name(chat_id))


@bot.message_handler(commands=["subscribe"])
def subscribe(message):
    chat_id = message.chat.id
    # Update the environment variable
    if _update_chat_id_env_var(chat_id, "subscribe"):
        bot.reply_to(
            message,
            f"Thank you for subscribing to the bot. "
            + f"You will get notified 10 and 5 minutes every Friday "
            + f"before it's candle lighting time.",
        )
        logger.info("User: %s subscribed to the bot.", _get_user_name(chat_id))
    else:
        bot.reply_to(
            message,
            "Sorry, there was an error subscribing you to the bot. "
            + "Please try again later.",
        )
        logger.error(
            "User: %s failed to subscribe to the bot.", _get_user_name(chat_id)
        )


@bot.message_handler(commands=["unsubscribe"])
def unsubscribe(message):
    chat_id = message.chat.id
    # Update the environment variable
    if _update_chat_id_env_var(chat_id, "unsubscribe"):
        bot.reply_to(
            message, f"You are now unsubscribed. " + f"Thank you for using the bot!"
        )
        logger.info("User: %s unsubscribed from the bot.", _get_user_name(chat_id))
    else:
        bot.reply_to(
            message,
            "Sorry, there was an error subscribing you to the bot. "
            + "Please try again later.",
        )
        logger.error(
            "User: %s failed to unsubscribe from the bot.", _get_user_name(chat_id)
        )


bot.polling()
