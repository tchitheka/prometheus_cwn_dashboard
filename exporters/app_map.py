# app_map.py
APP_MAP = [
    ("whatsapp.net", "WhatsApp"), ("whatsapp.com", "WhatsApp"),
    ("facebook.com", "Facebook"), ("fbcdn.net", "Facebook"),
    ("instagram.com", "Instagram"),
    ("youtube.com", "YouTube"), ("googlevideo.com", "YouTube"),
    ("tiktok.com", "TikTok"), ("tiktokcdn.com", "TikTok"),
    ("google.com", "Google Services"), ("gstatic.com", "Google Services"),
    ("googleapis.com", "Google Services"),
    ("doubleclick.net", "Ads/Tracking"),
    ("microsoft.com", "Microsoft Services"), ("office.com", "Microsoft Services"),
]

def classify(name: str) -> str:
    name = (name or "").lower()
    for substr, app in APP_MAP:
        if substr in name:
            return app
    return "Other"
