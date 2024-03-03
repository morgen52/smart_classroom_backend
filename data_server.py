from flask import Flask, request, jsonify, current_app
import os
import json
from flask_cors import CORS
import sqlite3
import time
import random
from datetime import datetime

from utils.clear_and_backup import clear
from utils.timestamp_cmp import timestamp_cmp
from llm.chatgpt import chat
from handle_upload import *

app = Flask(__name__)
origins = [
    '*',
    'http://localhost',
    'http://127.0.0.1',
    'http://0.0.0.0',
    # 'http://162.105.175.69',
    'http://54.165.81.221/'
]
CORS(app, origins=origins)

def init():
    clear()
    conn = sqlite3.connect('database.db')
    # 数据库中包含{"teacher_score": 0.31818479890402707, "student_score": 0.5, "latest_audio": "20230525213529", "speed": 0, "audio_silence": 0.0, "student_score_history": [0.5, 0.5], "teacher_score_history": [0.25112356228156835, 0.2523034238621179, 0.25327794621317945]}
    # teacher_score: 老师的评分
    # student_score: 学生的评分
    # latest_audio: 最新的音频文件名
    # speed: 语速
    # audio_silence: 音频静音时间
    # student_score_history: 学生的评分历史
    # teacher_score_history: 老师的评分历史
    # inspire: 启发次数
    # interactive: 互动次数
    # temperature: 温度
    # co2: 二氧化碳浓度
    # watch_feedback: 课程反馈
    # watch_answer: 课程答疑
    # 以上数据在数据库中的表名为"cur_state"
    cursor = conn.cursor()
    # 先清空表
    cursor.execute('''
        DROP TABLE IF EXISTS cur_state
    ''')
    # 创建cur_state表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cur_state (
            teacher_score REAL,
            student_score REAL,
            latest_audio TEXT,
            latest_pic TEXT,
            speed INTEGER,
            audio_silence REAL,
            student_score_history TEXT,
            teacher_score_history TEXT,
            summary TEXT,
            raw_text TEXT,
            inspire INTEGER,
            interactive INTEGER,
            temperature REAL,
            co2 REAL,
            watch_feedback TEXT,
            watch_answer TEXT,
            watch_ans_start INTEGER
        )''')
    # 插入初始数据
    cursor.execute('''
        INSERT INTO cur_state VALUES (0.0, 0.0, '', '', 0, 0.0, '[]', '[]', '', '', 0, 0, 25.0, 20.0, '[]', '[]', 0)
    ''')
    conn.commit()
    conn.close()

    os.system("docker stop $(docker ps -a -q)")

    os.system("docker run --rm -p 5000:5000 -d liminfinity/atmos_text:v0.0 python3 flask_server.py")
    os.system("docker run -v $(pwd)/audio:/app/audio --rm -p 5001:5001 -d liminfinity/atmos_audio:v0.0 python3 flask_server.py")
    os.system("docker run -v $(pwd)/pic:/app/pic --rm -p 5002:5002 -d liminfinity/atmos_video:v0.0 python3 flask_server.py")

# init()
from whisper_asr.audio2text import audio2text


'''
http://ip:port/set?arg1=value1&arg2=value2
'''
@app.route('/set', methods=['GET'])
def set_database():
    args = request.args
    conn = sqlite3.connect('database.db')
    for key, value in args.items():
        if key in ['teacher_score', 'student_score', 'audio_silence', 'temperature', 'co2']:
            value = float(value)
        elif key in ['student_score_history', 'teacher_score_history', 'watch_feedback', 'watch_answer']:
            value = json.dumps(json.loads(value)) # get http://0.0.0.0:8000/set?watch_feedback=[1,2,3,4]
        elif key in ['speed', 'inspire', 'interactive', 'watch_ans_start']:
            value = int(value)
        else:
            conn.commit()
            conn.close()
            return f'Invalid key: {key}'
        
        conn.execute(f'''
            UPDATE cur_state
            SET {key} = ?
        ''', (value,))
    conn.commit()
    conn.close()
    return 'Database updated successfully.'

'''
payload_data = {
    'device_addr': device.addr,
    'timestamp': timestamp, %Y-%m-%d-%H:%M:%S
    'feedback': data['feedback'],
    'answer': data['answer']
}
'''
watch_data = {}
@app.route('/upload-watch', methods=['POST'])
def upload_watch():
    global watch_data
    data = request.json
    device_addr = data['device_addr']
    timestamp = data['timestamp']
    feedback = data['feedback']
    answer = data['answer']

    if device_addr not in watch_data:
        watch_data[device_addr] = {}
    else:
        cmp_result = timestamp_cmp(watch_data[device_addr]["timestamp"], timestamp)
        if cmp_result == "greater":
            return "outdated data"
        elif cmp_result == "less":
            # update watch data
            db = sqlite3.connect('database.db')
            cursor = db.cursor()
            cursor.execute("SELECT watch_feedback, watch_answer FROM cur_state")
            result = cursor.fetchone()
            watch_feedback = json.loads(result[0]) if result else [0,0,0,0]
            watch_answer = json.loads(result[1]) if result else [0,0,0,0]
            for i in range(4):
                watch_feedback[i] += watch_data[device_addr]["feedback"][i]
                watch_answer[i] += watch_data[device_addr]["answer"][i]
            cursor.execute("UPDATE cur_state SET watch_feedback = ?, watch_answer = ?", (json.dumps(watch_feedback), json.dumps(watch_answer)))
            db.commit()
            db.close()

    watch_data[device_addr]["timestamp"] = timestamp
    watch_data[device_addr]["feedback"] = feedback
    watch_data[device_addr]["answer"] = answer

    return 'watch data uploaded successfully.'

@app.route('/upload-env', methods=['POST'])
def upload_env():
    data = request.json
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("UPDATE cur_state SET temperature = ?, co2 = ?", (data['temperature'], data['co2']))
    db.commit()
    db.close()
    return 'environment data uploaded successfully.'

@app.route('/upload-mp3', methods=['POST'])
def upload_mp3():
    file = request.files['file']
    # if file and file.filename.endswith('.wav'):
    if file:
        file.save(f"audio/{file.filename}")
        
        texts = audio2text(os.path.join(os.getcwd(), f"audio/{file.filename}"))

        # add punc
        def add_punc(texts):
            msgs = [
                {
                    "role": "user",
                    "content": f"请将下列内容加上标点后回复，不允许出现多余信息。刚才的语音内容如下：{texts}"
                }
            ]
            response = chat(msgs)
            return response
        texts = add_punc(texts)

        text_path = f"text/{file.filename.split('.')[0]}.txt"
        with open(text_path, 'w', encoding='utf8') as f:
            f.write(texts)

        try:
            handle_audio_and_text(file.filename.split('.')[0])
        except Exception as e:
            print("handle_audio_and_text error: ", e)
            # 更新latest_audio为latest_file
            db = sqlite3.connect('database.db')
            cursor = db.cursor()
            cursor.execute("UPDATE cur_state SET latest_audio = ?", (file.filename.split('.')[0],))
            db.commit()
            db.close()
        return 'MP3 file uploaded successfully.'
    else:
        return 'Invalid file or file format. MP3 file required.'

@app.route('/upload-image', methods=['POST'])
def upload_image():
    file = request.files['file']
    if file and file.filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
        file.save(f'pic/{file.filename}')
        
        # asyncio.create_task(handle_pic())
        # executor.submit(handle_pic)
        # threading.Thread(target=handle_pic).start()

        try:
            handle_pic(file.filename.split('.')[0])
        except Exception as e:
            print("upload image error", e)
            # 更新latest_pic
            db = sqlite3.connect('database.db')
            cursor = db.cursor()
            cursor.execute("UPDATE cur_state SET latest_pic = ?", (file.filename.split('.')[0],))
            db.commit()
            db.close()

        return 'Image file uploaded successfully.'
    else:
        return 'Invalid file or file format. Supported image formats: JPG, JPEG, PNG, GIF.'

'''
result = {
    "response": questions,
}
'''
@app.route('/question', methods=['GET'])
def gen_question():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT summary FROM cur_state") 
    result = cursor.fetchone()
    history = result[0].replace("\n", "。") if result else ""
    db.close()

    if not history:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return jsonify({"response": f"({timestamp})可分析的内容不足，请稍后再试"})

    msgs = history.append(
        {
            "role": "user", 
            "content": "请你扮演一个课程学生，根据之前对话中的所有课程内容，简洁地提出三个问题，每个问题不超过20个字。"
        }
    )

    response = chat(msgs)

    result = {
        "response": response,
    }
    return jsonify(result)


'''
result = {
    "response": "summary",
}
'''
@app.route('/summary', methods=['GET'])
def gen_summary():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT summary FROM cur_state")
    result = cursor.fetchone()
    history = result[0].replace("\n", "。") if result else []
    db.close()

    if not history:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return jsonify({"response": f"({timestamp})可分析的内容不足，请稍后再试"})

    msgs = history.append(
        {
            "role": "user", 
            "content": "请你扮演一个课程助教，根据之前对话中的所有课程内容，简洁地进行总结，不超过100个字。"
        }
    )

    response = chat(msgs)

    result = {
        "response": response,
    }
    return jsonify(result)


'''
return jsonify({
    "speech_rate": 0,
    "audio_silence": 0
})
'''
@app.route('/speed', methods=['GET'])
def read_SpeechRateAndAudioSilence():
    # read speed and audio_silence from database
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT speed, audio_silence FROM cur_state")
    result = cursor.fetchone()
    db.close()

    if result:
        return jsonify({
            "speech_rate": result[0],
            "audio_silence": result[1]
        })
    else:
        return jsonify({
            "speech_rate": 0,
            "audio_silence": 0
        })

'''
return jsonify({
    "teacher_score": 0.5
})
'''
@app.route('/teacher', methods=['GET'])
def read_teacher_emotion():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT teacher_score FROM cur_state")
    result = cursor.fetchone()
    db.close()

    if result:
        return jsonify({
            "teacher_score": result[0]
        })
    else:
        return jsonify({
            "teacher_score": 0.5
        })

'''
return jsonify({
    "student_score": 0.5
})
'''
@app.route('/student', methods=['GET'])
def read_student_emotion():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT student_score FROM cur_state")
    result = cursor.fetchone()
    db.close()

    if result:
        return jsonify({
            "student_score": result[0]
        })
    else:
        return jsonify({
            "student_score": 0.5
        })

'''
return jsonify({
    "student_score_history": [0] * 10,
    "teacher_score_history": [0] * 10,
    "x": ["00:00"] * 10
})
'''
@app.route('/his', methods=['GET'])
def get_history():
    # get student_score_history, teacher_score_history, latest_audio
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT student_score_history, teacher_score_history, latest_pic FROM cur_state")
    result = cursor.fetchone()
    db.close()

    # return {'student_score_history': result[0], 'teacher_score_history': result[1], 'latest_audio': result[2]}

    if result:
        student = json.loads(result[0])
        teacher = json.loads(result[1])
        # 202305251415
        print(result[2])
        try:
            timestamp = int(result[2][-6:-2])
        except Exception as e:
            print("history error", e)
            timestamp = 0

        # for test
        # student = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9, 0.8, 0.7, 0.6]
        # teacher = [0.5]
        # timestamp = 405

        # 将三个list的长度都限制在10以内，不足10的在前面补0
        student = [0] * max(0, 10 - len(student)) + student[-10:]
        teacher = [0] * max(0, 10 - len(teacher)) + teacher[-10:]
        
        # x 为过去10分钟的时间戳
        total_minutes = (timestamp // 100) * 60 + (timestamp % 100)
        x = []
        for i in range(10):
            x.append(f"{max(0, (total_minutes - 9 + i)) // 60:02d}:{max(0, (total_minutes -9 + i)) % 60:02d}")

        return jsonify({
            "student_score_history": student[-10:],
            "teacher_score_history": teacher[-10:],
            "x": x
        }) 
    else:
        return jsonify({
            "student_score_history": [0] * 10,
            "teacher_score_history": [0] * 10,
            "x": ["00:00"] * 10
        })

def clear_watch_data():
    global watch_data
    watch_data = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    feedback_plus = [0,0,0,0]
    answer_plus = [0,0,0,0]
    for dev_addr, data in watch_data.items():
        if timestamp_cmp(data["timestamp"], now) == "greater":
            for i in range(4):
                feedback_plus[i] += data["feedback"][i]
                answer_plus[i] += data["answer"][i]
            watch_data.pop(dev_addr)
    if feedback_plus != [0,0,0,0] or answer_plus != [0,0,0,0]:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        cursor.execute("SELECT watch_feedback, watch_answer FROM cur_state")
        result = cursor.fetchone()
        watch_feedback = json.loads(result[0]) if result else [0,0,0,0]
        watch_answer = json.loads(result[1]) if result else [0,0,0,0]
        for i in range(4):
            watch_feedback[i] += feedback_plus[i]
            watch_answer[i] += answer_plus[i]
        cursor.execute("UPDATE cur_state SET watch_feedback = ?, watch_answer = ?", (json.dumps(watch_feedback), json.dumps(watch_answer)))
        db.commit()
        db.close()

# return [0,0,0,0]
@app.route('/feedback', methods=['GET'])
def feedback():
    clear_watch_data()
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT watch_feedback FROM cur_state")
    result = cursor.fetchone()
    result = json.loads(result[0]) if result else [0,0,0,0]
    db.close()
    return jsonify(result)

# return [0,0,0,0]
@app.route('/question_play', methods=['GET'])
def question_play():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT watch_ans_start, watch_answer FROM cur_state")
    result = cursor.fetchone()
    start_flag = result[0] if result else 0
    result = json.loads(result[1]) if result else [0,0,0,0]
    if start_flag == 0: # update watch_ans_start and watch_answer
        cursor.execute("UPDATE cur_state SET watch_ans_start = ?, watch_answer = ?", (1, json.dumps([0,0,0,0])))
        db.commit()
        result = [0,0,0,0]
    db.close()
    
    return jsonify(result)

# return [0,0,0,0]
@app.route('/question_stop', methods=['GET'])
def question_stop():
    clear_watch_data()
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT watch_answer FROM cur_state")
    result = cursor.fetchone()
    result = json.loads(result[0]) if result else [0,0,0,0]
    cursor.execute("UPDATE cur_state SET watch_ans_start = ?", (0,))
    db.commit()
    db.close()
    return jsonify(result)

'''
return "25.0"
'''
@app.route('/temperature', methods=['GET'])
def temperature():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT temperature FROM cur_state")
    result = cursor.fetchone()
    temperature = result[0] if result else 25.0
    db.close()
    return f"{temperature}"

'''
return "20.0"
'''
@app.route('/co2', methods=['GET'])
def co2():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT co2 FROM cur_state")
    result = cursor.fetchone()
    co2 = result[0] if result else 20.0
    db.close()
    return f"{co2}"

'''
return "10"
'''
@app.route('/inspire', methods=['GET'])
def inspire():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT inspire FROM cur_state")
    result = cursor.fetchone()
    inspire = result[0] if result else 0
    db.close()
    return f"{inspire}"

'''
return "10"
'''
@app.route('/interactive', methods=['GET'])
def interactive():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT interactive FROM cur_state")
    result = cursor.fetchone()
    interactive = result[0] if result else 0
    db.close()
    return f"{interactive}"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
