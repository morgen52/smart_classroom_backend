import sqlite3
import os
import json
from llm.chatgpt import chat
import re
import requests

from SpeechRateAndAudioSilence_info import get_SpeechRateAndAudioSilence


def print_database():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT * FROM cur_state")
    row = cursor.fetchone()
    # timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
    try:
        with open(f"log/log.txt", 'w', encoding='utf8') as f:
            while row:
                f.write(str(row) + '\n')
                row = cursor.fetchone()
    except Exception as e:
        print("print_database error", e)
    db.close()

def gen_SpeechRateAndAudioSilence(latest_audio):

    speech_rate, audio_silence = get_SpeechRateAndAudioSilence(latest_audio)
    data = {
        "speech_rate": speech_rate,
        "audio_silence": audio_silence
    }

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("UPDATE cur_state SET speed = ?, audio_silence = ?", (speech_rate, audio_silence))
    db.commit()
    db.close()
    return 

def compute_score(pos, neu, neg):
    all = 2 * (pos + neu + neg)
    if all:
        score = (pos * 2 + neu * 1) / all
        return score
    else:
        return 0.5 + random.uniform(-0.05, 0.05)

def gen_teacher_emotion(new_files, texts):

    text_emotion = {
        "pos_num": 0,
        "neu_num": 0,
        "neg_num": 0
    }

    for text in texts:
        data = {
            "text": text
        }
        emotion_resp = requests.post(f"http://localhost:5000/text", json=data)
        emotion_resp = emotion_resp.json()
        print(emotion_resp)
        text_emotion['pos_num'] += emotion_resp['pos_num']
        text_emotion['neu_num'] += emotion_resp['neu_num']
        text_emotion['neg_num'] += emotion_resp['neg_num']

    text_score = compute_score(text_emotion['pos_num'], text_emotion['neu_num'], text_emotion['neg_num'])

    # {"pos_num": 2, "neg_num": 0, "neu_num": 4}

    audio_emotion = {
        "pos_num": 0, 
        "neu_num": 0,
        "neg_num": 0
    }
    for filename in new_files:
        audiopath = f"audio/{filename}.wav"
        data = {
            "path": audiopath
        }
        response = requests.post("http://localhost:5001/audio", json=data)
        response = response.json()
        print(response)
        # {'angry': 0,'fear': 0,'happy': 0,'neutral': 0,'sad': 0,'surprise': 0}
        pos_cnt = response['happy'] + response['surprise']
        neg_cnt = response['angry'] + response['fear'] + response['sad']
        neu_cnt = response['neutral']
        audio_emotion['pos_num'] += pos_cnt
        audio_emotion['neu_num'] += neu_cnt
        audio_emotion['neg_num'] += neg_cnt

    audio_score = compute_score(audio_emotion['pos_num'], audio_emotion['neu_num'], audio_emotion['neg_num'])

    teacher_score = (text_score + audio_score) / 2

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # update teacher_score_history list
    cursor.execute("SELECT teacher_score_history FROM cur_state")
    result = cursor.fetchone()
    if result:
        teacher_score_history = json.loads(result[0])
    else:
        teacher_score_history = []
    teacher_score_history.append(teacher_score)
    teacher_score_history = json.dumps(teacher_score_history)
    cursor.execute("UPDATE cur_state SET teacher_score_history = ?", (teacher_score_history,))
    # update teacher_score
    cursor.execute("UPDATE cur_state SET teacher_score = ?", (teacher_score,))
    db.commit()
    db.close()

def gen_student_emotion(latest_file):
    # 获取timestamp最近的文件
    # latest_file = sorted(os.listdir("pic"))[-1].split('.')[0]

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT latest_pic FROM cur_state")
    result = cursor.fetchone()
    db.close()
    if result and result[0] == latest_file: # 如果数据库中的latest_pic和文件夹中的一致
        print(f"{latest_file} has been processed, no need to update")
        return # 不需要更新

    new_files = []
    for filename in sorted(os.listdir("pic")):
        if result[0] < filename.split('.')[0] <= latest_file:
            new_files.append(filename.split('.')[0])
    print("student emotion pic", new_files)
    pic_emotion = {
        "pos_num": 0, 
        "neu_num": 0,
        "neg_num": 0
    }

    for filename in new_files:
        picpath = f"pic/{filename}.png"
        data = {
            "path": picpath
        }
        # 获取request的返回值
        response = requests.post("http://localhost:5002/pic", json=data)
        print(response.json())
        response = response.json()
        # {"Angry": 0, "Fear": 0, "Happy": 0, "Neutral": 0, "Sad": 0, "Surprise": 0}
        pos_cnt = response['Happy'] + response['Surprise']
        neg_cnt = response['Angry'] + response['Fear'] + response['Sad']
        neu_cnt = response['Neutral']
        pic_emotion['pos_num'] += pos_cnt
        pic_emotion['neu_num'] += neu_cnt
        pic_emotion['neg_num'] += neg_cnt

    pic_score = compute_score(pic_emotion['pos_num'], pic_emotion['neu_num'], pic_emotion['neg_num'])

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # update student_score_history list
    cursor.execute("SELECT student_score_history FROM cur_state")
    result = cursor.fetchone()
    if result:
        student_score_history = json.loads(result[0])
    else:
        student_score_history = []
    student_score_history.append(pic_score)
    student_score_history = json.dumps(student_score_history)
    cursor.execute("UPDATE cur_state SET student_score_history = ?", (student_score_history,))
    # update student_score
    cursor.execute("UPDATE cur_state SET student_score = ?", (pic_score,))
    db.commit()
    db.close()

def get_summary(raw_text, mode="raw"): 
    # raw_text: str without '\n'
    # mode: "raw" or "summary"
    if not raw_text:
        return

    prompt = ""
    if mode == "raw":
        prompt = "请你扮演一个课程助教，简单概括一下老师刚才讲的内容。不超过100个字"
    elif mode == "summary":
        prompt = "请你扮演一个课程助教，简单概括一下老师刚才讲的内容。不超过200个字"

    msg = [
        {
            "role": "user",
            "content": f"{prompt}。老师讲的内容如下：{raw_text}"
        }
    ]

    response = chat(msg)

    return response

# 每收到一次mp3都更新一次Summary
def update_summary():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # 获取summary和raw_text
    cursor.execute("SELECT summary, raw_text FROM cur_state")
    result = cursor.fetchone()
    db.close()

    summary = result[0] if result[0] else ""
    raw_text = result[1] if result[1] else ""

    RAW_TEXT_LIM = 200
    while len(raw_text) > RAW_TEXT_LIM:
        process_text = raw_text[:RAW_TEXT_LIM]
        raw_text = raw_text[RAW_TEXT_LIM:]
        summary += f"{get_summary(process_text)}。"

    # sum_cnt = 0 # 精简summary的次数不能超过1次
    # 每TEXT_LIM个字分段一个summary, 精简summary
    # while (len(summary) > TEXT_LIM) and (sum_cnt < 1):
    SUMMARY_TEXT_LIM = 500
    if len(summary) > SUMMARY_TEXT_LIM:
        summary_list = [summary[i:i+SUMMARY_TEXT_LIM] for i in range(0, len(summary), SUMMARY_TEXT_LIM)]
        summary_list = [get_summary(summary, mode="summary") for summary in summary_list]
        summary = "。".join(summary_list)
        # sum_cnt += 1

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # update summary and raw_text
    cursor.execute("UPDATE cur_state SET summary = ?", (summary,))
    cursor.execute("UPDATE cur_state SET raw_text = ?", (raw_text,))
    db.commit()
    db.close()

def update_interact(raw_text):
    msgs = [
        {
            "role": "user",
            "content": f"回答我这段话的说话人有几个？请用一个阿拉伯数字表示。如果有1个说话人，回复1；如果有两个说话人，回复2，依次类推。这段话的内容是：现在开始上课。请大家打开课本，我们一起来学习。"
        },
        {
            "role": "assistant",
            "content": "1"
        },
        {
            "role": "user",
            "content": f"回答我这段话的说话人有几个？请用一个阿拉伯数字表示。如果有1个说话人，回复1；如果有两个说话人，回复2，依次类推。这段话的内容是：大家准备好了吗？准备好了。"
        },
        {
            "role": "assistant",
            "content": "2"
        },
        {
            "role": "user",
            "content": f"回答我这段话的说话人有几个？请用一个阿拉伯数字表示。如果有1个说话人，回复1；如果有两个说话人，回复2，依次类推。这段话的内容是：{raw_text}"
        }
    ]
    response = chat(msgs)
    # 正则表达式提取数字
    interact_cnt = re.findall(r"\d+", response)
    interact_cnt = int(interact_cnt[0]) if interact_cnt else 0
    if interact_cnt > 1:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        # update interact
        cursor.execute("UPDATE cur_state SET interact = interact + 1")
        db.commit()
        db.close()

def update_inspire(texts):
    inspire_cnt = 0
    for text in texts:
        inspire_cnt += text.count("?")

    if inspire_cnt > 0:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        # update inspire
        cursor.execute("UPDATE cur_state SET inspire = inspire + ?", (inspire_cnt,))
        db.commit()
        db.close()

def handle_audio_and_text(latest_file):
    print(f"handle_audio_and_text: {latest_file}")
    # latest_file = sorted(os.listdir("audio"))[-1].split('.')[0]

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT latest_audio FROM cur_state")
    result = cursor.fetchone()
    db.close()
    if result and result[0] == latest_file: # 如果数据库中的latest_audio和文件夹中的一致
        print(f"{latest_file} has been processed, no need to update")
        return # 不需要更新

    new_files = []
    for filename in sorted(os.listdir("audio")):
        # print(filename)
        if result[0] < filename.split('.')[0] <= latest_file:
            new_files.append(filename.split('.')[0])
    
    print("teacher emotion audio and text new_files", new_files)
    texts = []
    for filename in new_files:
        with open(f"text/{filename}.txt", 'r', encoding='utf8') as f:
            texts.append(f.read())

    # update raw_text
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT raw_text FROM cur_state")
    result = cursor.fetchone()
    raw_text = result[0] if result else ""
    raw_text += '。'.join(texts)
    cursor.execute("UPDATE cur_state SET raw_text = ?", (raw_text,))
    db.commit()
    db.close()
    
    # 更新speed和audio_silence
    try:
        gen_SpeechRateAndAudioSilence(latest_file)
    except Exception as e:
        print("gen_SpeechRateAndAudioSilence error: ", e)
    
    # 更新teacher_score和teacher_score_history
    try:
        gen_teacher_emotion(new_files, texts)
    except Exception as e:
        print("get_teacher_emotion error: ", e)
    
    # 更新启发次数
    try:
        update_inspire(texts)
    except Exception as e:
        print("update_inspire error: ", e)

    # 更新互动次数
    try:
        update_interact(raw_text)
    except Exception as e:
        print("update_interact error: ", e)

    # update summary from raw_text
    try:
        update_summary()
    except Exception as e:
        print("update_summary error: ", e)

    # 更新latest_audio为latest_file
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("UPDATE cur_state SET latest_audio = ?", (latest_file,))
    db.commit()
    db.close()
    
def handle_pic(latest_file):
    print(f"handle_pic: {latest_file}")
    # latest_file = sorted(os.listdir("pic"))[-1].split('.')[0]
    # 更新student_score和student_score_history
    try:
        gen_student_emotion(latest_file)
    except Exception as e:
        print("get_student_emotion error: ", e)
    # 更新latest_pic
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("UPDATE cur_state SET latest_pic = ?", (latest_file,))
    db.commit()
    db.close()

    print_database()
