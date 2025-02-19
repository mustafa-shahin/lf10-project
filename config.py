import configparser

config = configparser.ConfigParser()
config.read("App.ini", encoding="utf-8-sig")

SMTP_HOST = config.get("SMTP", "host", fallback="")
SMTP_PORT = config.getint("SMTP", "port", fallback=587)
SMTP_USER = config.get("SMTP", "username", fallback="")
SMTP_PASS = config.get("SMTP", "password", fallback="")
SMTP_TLS  = config.getboolean("SMTP", "use_tls", fallback=True)
