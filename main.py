import boto3
import telebot
import json
import os

BOT_TOKEN = os.environ['BOT_TOKEN']
LAMBDA_NAME = os.environ['LAMBDA_NAME']

bot = telebot.TeleBot(BOT_TOKEN)

def update_chat_id_env_var(chat_id):
    """
    Update the chat ID environment variable of the Lambda function.
    """
    lambda_client = boto3.client('lambda')
    env_vars = lambda_client.get_function_configuration(
        FunctionName=LAMBDA_NAME
    )['Environment']['Variables']
    
    # Check if the chat ID is already present in the environment variables
    if 'BOT_CHATID' in env_vars:
        chat_id_list = json.loads(env_vars['BOT_CHATID'])
        if chat_id in chat_id_list:
            print("Chat ID already present in environment variables.")
        else:
            chat_id_list.append(chat_id)
            env_vars['BOT_CHATID'] = str(chat_id_list)
        
    response = lambda_client.update_function_configuration(
        FunctionName=LAMBDA_NAME,
        Environment={
            'Variables': env_vars
        }
    )
    print(response)
    

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    bot.reply_to(message, f"Hello! Thank you for joining the bot. " + \
                        f"You will get notified 10 and 5 minutes every Friday " + \
                         f"before it's candle lighting time.")
    
    # Update the environment variable
    update_chat_id_env_var(chat_id)

bot.polling()
