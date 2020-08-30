import sys
import re
import wave
import uuid
from contextlib import closing
from datetime import datetime
from itertools import chain
from pathlib import Path

from tinkoff_voicekit_client import ClientSTT
import psycopg2

import secret_config
import config


log_file = open(config.log_file_name, 'a+', encoding='utf-8')
error_file = open(config.error_file_name, 'a+', encoding='utf-8')

robot_pattern = re.compile("автоответчик|"
                           "оставьте сообщение|"
                           "после сигнала")

negative_pattern = re.compile("нет|неудобно|не надо|занят")


class STTWrapper:
    """Wrapper class for tinkoff_voicekit_client.ClientSTT"""

    def __init__(self, api_key, secret_key):
        self.client = ClientSTT(api_key, secret_key)
        self.audio_config = {
            "encoding": "LINEAR16",
            "sample_rate_hertz": 8000,
            "num_channels": 1
        }

    def recognize(self, file_path):
        response = self.client.recognize(file_path, self.audio_config)

        best_confidence = -float('inf')
        text = ''

        alternatives = chain.from_iterable(
            map(lambda x: x['alternatives'], response))
        for alternative in alternatives:
            if (alternative['transcript'] and
                    best_confidence < alternative['confidence']):
                best_confidence = alternative['confidence']
                text = alternative['transcript']

        return text


try:
    conn = None

    stt = STTWrapper(secret_config.API_KEY, secret_config.SECRET_KEY)

    file_path, phone, db_flag, step = sys.argv[1:]

    if db_flag not in ['0', '1']:
        raise ValueError("wrong third argument, should be 0 or 1")
    if step not in ['1', '2']:
        raise ValueError("wrong fourth argument, should be 1 or 2")

    with closing(wave.open(file_path, 'r')) as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)

    if db_flag == '1':
        conn = psycopg2.connect(dbname=config.DBNAME, user=config.DBUSER,
                                password=config.DBPASSWORD, host=config.DBHOST)

        with conn.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS log (
    date DATE,
    time TIME,
    uuid UUID PRIMARY KEY,
    result VARCHAR(12),
    phone VARCHAR(12),
    duration REAL,
    recognized TEXT
);""")
            conn.commit()

    recognized = stt.recognize(file_path)

    re_result = ""
    is_negative = True

    if step == "1":
        is_negative = bool(robot_pattern.search(recognized))
        re_result = "автоответчик" if is_negative else "человек"

    if step == "2":
        is_negative = bool(negative_pattern.search(recognized))
        re_result = "отрицательно" if is_negative else "положительно"

    Path(file_path).unlink()
    now = datetime.now()
    uuid = uuid.uuid4()
    if db_flag == '1':
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO log VALUES ("
                           f"'{now:%Y-%m-%d}', '{now:%H:%M:%S}', "
                           f"'{uuid}', '{re_result}', '{phone}', "
                           f"{duration}, '{recognized}'"
                           ");")
            conn.commit()
    print(f"{now:%Y-%m-%d, %H:%M:%S}, {uuid}"
          f", {re_result}, {phone}, {duration}, {recognized}",
          file=log_file)
    print(int(not is_negative))

except Exception as e:
    print(f"{e.__class__.__name__}: {e}", file=error_file)

finally:
    log_file.close()
    error_file.close()
    if conn:
        conn.close()
