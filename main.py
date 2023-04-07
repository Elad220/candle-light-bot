import boto3
import telebot
import json
import os

BOT_TOKEN = os.environ['BOT_TOKEN']
LAMBDA_NAME = os.environ['LAMBDA_NAME']
MASTER_CHAT_ID = json.loads(os.environ['MASTER_CHAT_ID'])

bot = telebot.TeleBot(BOT_TOKEN)


def _get_lambda_env_vars(lambda_client) -> str:
    return lambda_client.get_function_configuration(
        FunctionName=LAMBDA_NAME
    )['Environment']['Variables']


def _update_chat_id_env_var(chat_id, action) -> bool:
    """
    Update the chat ID environment variable of the Lambda function.
    """
    lambda_client = boto3.client('lambda')
    env_vars = _get_lambda_env_vars(lambda_client)

    # Check if the chat ID is already present in the environment variables
    if 'BOT_CHATID' in env_vars:
        chat_id_list = json.loads(env_vars['BOT_CHATID'])
        if action == 'subscribe':
            if chat_id in chat_id_list:
                print("Chat ID already subscribed to the bot.")
                return True
            else:
                chat_id_list.append(chat_id)
                env_vars['BOT_CHATID'] = str(chat_id_list)
        elif action == 'unsubscribe':
            if chat_id not in chat_id_list:
                print("Chat ID not subscribed to the bot.")
                return True
            else:
                chat_id_list.remove(chat_id)
                env_vars['BOT_CHATID'] = str(chat_id_list)

    response = lambda_client.update_function_configuration(
        FunctionName=LAMBDA_NAME,
        Environment={
            'Variables': env_vars
        }
    )
    return response['ResponseMetadata']['HTTPStatusCode'] == 200


def _is_chat_id_authorized(user_id) -> bool:
    return user_id in MASTER_CHAT_ID


def _get_subscriber_names() -> list:
    names_list = []
    chat_ids = _get_lambda_env_vars(boto3.client('lambda'))['BOT_CHATID']
    for chat_id in json.loads(chat_ids):
        names_list.append(bot.get_chat_member(
            chat_id, chat_id).user.first_name)
    return names_list


@bot.message_handler(commands=['start'])
def send_welcome(message):
    msg = "Hello! I am a bot that will notify you 10 and 5 minutes " + \
        "before it's candle lighting time every Friday. \nTo subscribe " + \
        "to the bot, type /subscribe. \nTo view your subscribed users, " + \
        "type /view.\nTo unsubscribe from the bot, type /unsubscribe."
    bot.reply_to(message, msg)


@bot.message_handler(commands=['view'])
def view_subscribers(message):
    chat_id = message.chat.id 
    message_reply = f"Your subscribed users are {_get_subscriber_names()}." if _is_chat_id_authorized(
        chat_id) else "You are not authorized to perform this action."
    bot.reply_to(message, message_reply)


@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    chat_id = message.chat.id
    # Update the environment variable
    res = _update_chat_id_env_var(chat_id, 'subscribe')
    if res:
        bot.reply_to(message, f"Thank you for subscribing to the bot. " +
                     f"You will get notified 10 and 5 minutes every Friday " +
                     f"before it's candle lighting time.")
    else:
        bot.reply_to(message, "Sorry, there was an error subscribing you to the bot. " +
                     "Please try again later.")


@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(message):
    chat_id = message.chat.id
    # Update the environment variable
    res = _update_chat_id_env_var(chat_id, 'unsubscribe')
    if res:
        bot.reply_to(message, f"You are now unsubscribed. " +
                     f"Thank you for using the bot!")
    else:
        bot.reply_to(message, "Sorry, there was an error subscribing you to the bot. " +
                     "Please try again later.")


bot.polling()
