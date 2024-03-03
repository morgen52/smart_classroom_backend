import os
from openai import OpenAI

client = OpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)

def chat(msgs=[{"role": "user", "content": "Say nothing"}]):
    chat_completion = client.chat.completions.create(
        messages = msgs,
        model="gpt-3.5-turbo",
    )
    # print(chat_completion)
    if len(chat_completion.choices) > 0:   
        ans = chat_completion.choices[0].message.content
    else:
        ans = ""
    print(f"ChatGPT Answer: {ans}")
    return ans

if __name__ == "__main__":
    chat()
