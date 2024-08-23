import logging
import os
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,
    handlers=[
        TimedRotatingFileHandler("{}/app.log".format(os.getenv('DATA_FOLDER')), when="midnight", backupCount=7),
    ]
)
loggers = {}


def set_channel_logger(channel_name, level=logging.INFO):
    os.makedirs("{}/logs/".format(os.getenv("DATA_FOLDER")), exist_ok=True)
    log_file = "{}/logs/{}.log".format(os.getenv("DATA_FOLDER"), channel_name)
    handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, utc=True)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger = logging.getLogger(channel_name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


def log_message(channel_name, message):
    if channel_name not in loggers.keys():
        loggers[channel_name] = set_channel_logger(channel_name)
    loggers[channel_name].info(message)
