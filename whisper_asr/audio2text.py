import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from datasets import load_dataset
from datetime import datetime

device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3"

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    max_new_tokens=128,
    chunk_length_s=60,
    batch_size=16,
    # return_timestamps=True,
    torch_dtype=torch_dtype,
    device=device,
)

def audio2text(audio_path):
    try:
        print(datetime.now())
        result = pipe(audio_path, generate_kwargs={"language": "chinese", "task": "transcribe"})
        print(result["text"])
        print(datetime.now())
        return result["text"]
    except Exception as e:
        print(e)
        return ""

if __name__ == "__main__":
    audio2text("20230601144352.wav")
