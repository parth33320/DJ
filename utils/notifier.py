import requests

def send_notification(message, topic="dj-agent-parth"):
    """Send a notification to the ntfy.sh topic"""
    try:
        url = f"https://ntfy.sh/{topic}"
        requests.post(url, 
                      data=message.encode('utf-8'),
                      headers={
                          "Title": "AI DJ Transition Ready!",
                          "Priority": "high",
                          "Tags": "musical_note,headphones"
                      })
        print(f"🔔 Notification sent to topic: {topic}")
    except Exception as e:
        print(f"❌ Failed to send notification: {e}")
