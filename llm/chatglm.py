def get_summary(history, mode="normal"): 
    # history: str without '\n'
    # mode: "normal" or "concise"
    if not history:
        return
    # ChatGLM服务器的IP地址和端口号
    SERVER_IP = '10.129.160.70'
    SERVER_PORT = 5088
    history = history.replace("\n", "。")
    
    # 每200个字就分割一次
    # history = [["老师讲了什么？", history[i:i+200]] for i in range(0, len(history), 200)]

    prompt = ""
    if mode == "normal":
        prompt = "请你扮演一个课程助教，简单概括一下老师刚才讲的内容。不超过50个字"
    elif mode == "concise":
        prompt = "请你扮演一个课程助教，简单概括一下老师刚才讲的内容。不超过20个字"

    data = {
        "prompt": prompt,
        "history": [["老师讲了什么？", history]]
    }
    print(data)
    response = requests.post(f"http://{SERVER_IP}:{SERVER_PORT}", json=data)
    return response.json()['response']

# 每1分钟text都更新一次Summary
def update_summary():
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # 获取summary和raw_text
    cursor.execute("SELECT summary, raw_text FROM cur_state")
    result = cursor.fetchone()
    db.close()

    summary = result[0] if result[0] else ""
    raw_text = result[1] if result[1] else ""


    TEXT_LIM = 200
    while len(raw_text) > TEXT_LIM:
        process_text = raw_text[:TEXT_LIM]
        raw_text = raw_text[TEXT_LIM:]
        summary += f"{get_summary(process_text)}。"

    sum_cnt = 0 # 精简summary的次数不能超过1次
    # 每TEXT_LIM个字分段一个summary, 精简summary
    while (len(summary) > TEXT_LIM) and (sum_cnt < 1):
        summary_list = [summary[i:i+TEXT_LIM] for i in range(0, len(summary), TEXT_LIM)]
        summary_list = [get_summary(summary, mode="concise") for summary in summary_list]
        summary = "。".join(summary_list)
        sum_cnt += 1

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    # update summary and raw_text
    cursor.execute("UPDATE cur_state SET summary = ?", (summary,))
    cursor.execute("UPDATE cur_state SET raw_text = ?", (raw_text,))
    db.commit()
    db.close()



import requests
@app.route('/question', methods=['GET'])
def gen_question():
    # ChatGLM服务器的IP地址和端口号
    SERVER_IP = '10.129.160.70'
    SERVER_PORT = 5088
    # curl -X POST "http://10.129.160.70:5088" -H 'Content-Type: application/json' -d '{"prompt": "你好", "history": []}'

    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT summary FROM cur_state") 
    result = cursor.fetchone()
    history = result[0].replace("\n", "。") if result else ""
    db.close()

    if not history:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return jsonify({"response": f"({timestamp})可分析的内容不足，请稍后再试"})
    
    data = {
        "prompt": "请你扮演一个课程学生，根据课程摘要的内容，简洁地提出三个问题，每个问题不超过20个字。",
        "history": [["课程摘要的内容是什么?", history]]
    }
    response = requests.post(f"http://{SERVER_IP}:{SERVER_PORT}", json=data)
    print(response.json())
    response = response.json()['response']
    result = {
        "response": response,
    }
    return jsonify(result)

@app.route('/summary', methods=['GET'])
def gen_summary():
    SERVER_IP = '10.129.160.70'
    SERVER_PORT = 5088
    # curl -X POST "http://10.129.160.70:5088" -H 'Content-Type: application/json' -d '{"prompt": "你好", "history": []}'
    
    db = sqlite3.connect('database.db')
    cursor = db.cursor()
    cursor.execute("SELECT summary FROM cur_state")
    result = cursor.fetchone()
    history = result[0].replace("\n", "。") if result else ""
    db.close()

    if not history:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return jsonify({"response": f"({timestamp})可分析的内容不足，请稍后再试"})

    data = {
        "prompt": "请你扮演一个课程助教，根据课程摘要的内容，简洁地进行总结，不超过100个字。",
        "history": [["课程摘要的内容是什么?", history]]
    }
    response = requests.post(f"http://{SERVER_IP}:{SERVER_PORT}", json=data)
    print(response.json())
    response = response.json()['response']
    result = {
        "response": response,
    }
    return jsonify(result)