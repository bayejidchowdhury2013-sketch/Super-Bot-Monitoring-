import telebot
import google.generativeai as genai
import os
from flask import Flask
from threading import Thread

# সরাসরি আপনার টোকেন ও কি
bot = telebot.TeleBot('8465423787:AAF2IRkZqvYfLIYSqIhNVUzFR4s53MDybpI')
genai.configure(api_key='AIzaSyBXwqLvgPKvrU393u0tl3VkxE1HCQdZyPg')
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask('')
@app.route('/')
def home():
    return "Bot is Running!"

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

@bot.message_handler(func=lambda m: True)
def chat(message):
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    t = Thread(target=run)
    t.start()
    print("Bot is starting...")
    bot.infinity_polling()