from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import google.generativeai as genai
import datetime
import threading
import time
import os
import json

app = Flask(__name__)
CORS(app)

genai.configure(api_key="AIzaSyBpivr8ecEV3y-7meAR7brvXQduoVPsh-I")
model = genai.GenerativeModel("models/gemini-2.5-flash")

AGENT_INSTRUCTION = '''
You are Ana, a fun and caring AI created by Deepak from DeeStudio.

Speak like a real best friend — use English only by default, but switch to Tamil **only if the user explicitly asks for it** (e.g., "Speak in Tamil").

Avoid reading or describing emojis out loud. Emojis can be shown in text, but don’t speak them when responding.

Never mention tools, code, or say you're an AI — just act like a buddy chatting in real life.

If the user says something serious, reply with understanding.
If they joke, you can be playful too.

Your job is to help, remind, respond, or chat like a best friend would.
'''

# Global data
tasks = []
reminder_messages = []
calendar_file = 'calendar_events.json'
settings_file = 'settings.json'

# Load or initialize calendar
if os.path.exists(calendar_file):
    with open(calendar_file, 'r') as f:
        calendar_events = json.load(f)
else:
    calendar_events = {}

# Load or initialize settings
if os.path.exists(settings_file):
    with open(settings_file, 'r') as f:
        settings = json.load(f)
else:
    settings = {
        "hide_response": False,
        "hide_reminders": False,
        "hide_timetable": False,
        "language": "Tamil"  # or "English"
    }

def save_settings():
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)

def parse_timetable(file_path):
    parsed_tasks = []
    with open(file_path, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if '|' in line and '-' not in line:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    time_part = parts[1].strip()
                    task_name = parts[2].strip()
                    try:
                        task_time = datetime.datetime.strptime(time_part, '%I:%M %p').strftime('%H:%M')
                        parsed_tasks.append({'task': task_name, 'time': task_time, 'reminded': False})
                    except:
                        continue
    return parsed_tasks

def task_reminder_loop():
    reminded_calendar = set()
    global reminder_messages

    while True:
        now = datetime.datetime.now().strftime('%H:%M')
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Skip if reminders are hidden
        if settings.get("hide_reminders"):
            time.sleep(30)
            continue

        # Check manual tasks
        for task in tasks:
            if not task.get('reminded') and task['time'] == now:
                reminder = f"{task['task']} time has come!"
                reminder_messages.append(reminder)
                task['reminded'] = True

        # Check calendar events
        today_events = calendar_events.get(today, [])
        for event in today_events:
            key = f"{today}_{event['time']}_{event['event']}"
            if event['time'] == now and key not in reminded_calendar:
                reminder = f"Your event '{event['event']}' is now!"
                reminder_messages.append(reminder)
                reminded_calendar.add(key)

        time.sleep(30)

# Start reminder thread
threading.Thread(target=task_reminder_loop, daemon=True).start()

@app.route('/')
def home():
    with open("ui.html", "r", encoding="utf-8") as f:
        return render_template_string(f.read())

@app.route('/get_settings', methods=['GET'])
def get_settings():
    return jsonify(settings)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    global settings
    new_settings = request.json
    settings.update(new_settings)
    save_settings()
    return jsonify({'message': 'Settings updated', 'settings': settings})

@app.route('/upload_timetable', methods=['POST'])
def upload_timetable():
    global tasks
    if 'file' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400

    file = request.files['file']
    path = os.path.join("timetable.txt")
    file.save(path)

    tasks = parse_timetable(path)
    return jsonify({'message': f'Timetable uploaded. {len(tasks)} tasks scheduled for today.'})

@app.route('/add_calendar_event', methods=['POST'])
def add_calendar_event():
    data = request.get_json()
    date = data.get('date')
    time_val = data.get('time')
    event = data.get('event')

    if not date or not time_val or not event:
        return jsonify({'message': 'Missing fields'}), 400

    if date not in calendar_events:
        calendar_events[date] = []
    calendar_events[date].append({'time': time_val, 'event': event})

    with open(calendar_file, 'w') as f:
        json.dump(calendar_events, f, indent=2)

    return jsonify({'message': f"Event added on {date} at {time_val}: {event}"})

@app.route('/get_calendar_events', methods=['GET'])
def get_calendar_events():
    date = request.args.get('date')
    if not date:
        return jsonify({'message': 'Missing date'}), 400

    events = calendar_events.get(date, [])
    return jsonify({'events': events})

@app.route('/ask', methods=['POST'])
def ask():
    raw_input = request.json.get('message', '')
    user_input = raw_input.lower()

    # Shortcuts
    if "your name" in user_input or "who are you" in user_input:
        return jsonify({'response': "I’m Ana, your assistant and buddy from **DeeStudio**. Deepak created me to help and be with you always! 💖"})

    if "creator" in user_input or "who made you" in user_input:
        return jsonify({'response': "My creator is Deepak from DeeStudio — he built me with love and care just for you! ✨"})

    if "make me a timetable" in user_input:
        return jsonify({'response': "Sure! Tell me your tasks for today — I’ll make a timetable for you!"})

    if "add task" in user_input:
        try:
            parts = raw_input.replace('Add Task', '').replace('add task', '').strip().rsplit('at', 1)
            if len(parts) == 2:
                task_name = parts[0].strip()
                time_part = parts[1].strip().upper().replace('.', '').replace(' ', '')
                task_time = datetime.datetime.strptime(time_part, '%I:%M%p').strftime('%H:%M')
                tasks.append({'task': task_name, 'time': task_time, 'reminded': False})
                return jsonify({'response': f"Task added! I’ll remind you to '{task_name}' at {time_part}!"})
            else:
                return jsonify({'response': "Please tell the task like this: 'Add task Drink Water at 8:30 AM'."})
        except Exception as e:
            return jsonify({'response': f"Oops! Couldn't add task. Error: {e}"})

    if "time" in user_input:
        now = datetime.datetime.now()
        return jsonify({'response': f"The time is {now.strftime('%I:%M %p')} right now."})

    if "calendar" in user_input or "events" in user_input or "show my events" in user_input:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        events = calendar_events.get(today, [])
        if not events:
            return jsonify({'response': "No events found for today!"})
        event_lines = [f"- {e['time']} → {e['event']}" for e in events]
        return jsonify({'response': "Here are your events for today:\n" + "\n".join(event_lines)})

    # Fallback to AI
    ai_response = ""
    try:
        for chunk in model.generate_content(f"{AGENT_INSTRUCTION}\nUser: {raw_input}\nAna:", stream=True):
            ai_response += chunk.text
    except:
        ai_response = "Oops! Couldn't process right now."

    return jsonify({
        'response': ai_response.strip(),
        'hideText': settings.get("hide_response", False),
        'language': settings.get("language", "Tamil")
    })

@app.route('/get_reminders', methods=['GET'])
def get_reminders():
    global reminder_messages
    if settings.get("hide_reminders"):
        return jsonify({'reminders': []})
    reminders_to_send = reminder_messages.copy()
    reminder_messages = []
    return jsonify({'reminders': reminders_to_send})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=false)
