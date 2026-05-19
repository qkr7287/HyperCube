"""Auto-launched gradio UI for Qwen2-VL-2B-Instruct.

Started in the background by start-jupyter.sh when a Qwen2-VL model
directory is detected under /workspace/. Listens on 127.0.0.1:7860 and is
exposed through Jupyter via jupyter-server-proxy at <base>/proxy/7860/.
"""
from __future__ import annotations

import os
import sys
import traceback

import gradio as gr
import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

MODEL_DIR = os.environ.get("HC_QWEN2VL_MODEL", "/workspace/qwen2-vl-2b-instruct")
HOST = os.environ.get("HC_GRADIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("HC_GRADIO_PORT", "7860"))
ROOT_PATH = os.environ.get("HC_GRADIO_ROOT_PATH", "/proxy/7860")


def _load_model():
    print(f"[hc-qwen2vl] loading model from {MODEL_DIR}", flush=True)
    processor = AutoProcessor.from_pretrained(MODEL_DIR)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        MODEL_DIR, torch_dtype=dtype, device_map=device,
    )
    model.eval()
    print(f"[hc-qwen2vl] loaded on {device} dtype={dtype}", flush=True)
    return processor, model


try:
    processor, model = _load_model()
except Exception as exc:
    traceback.print_exc()
    print(f"[hc-qwen2vl] FATAL load failed: {exc}", file=sys.stderr, flush=True)
    raise


@torch.inference_mode()
def caption(image: Image.Image, prompt: str) -> str:
    if image is None:
        return "이미지를 업로드해주세요."
    if not prompt or not prompt.strip():
        prompt = "이 이미지를 자세히 설명해주세요."
    messages = [{
        "role": "user",
        "content": [{"type": "image"}, {"type": "text", "text": prompt.strip()}],
    }]
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = processor(text=[text], images=[image], return_tensors="pt").to(device)
    output_ids = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    generated = output_ids[:, inputs.input_ids.shape[1]:]
    return processor.batch_decode(generated, skip_special_tokens=True)[0].strip()


demo = gr.Interface(
    fn=caption,
    inputs=[
        gr.Image(type="pil", label="이미지"),
        gr.Textbox(
            label="프롬프트 (비우면 기본 캡션)",
            placeholder="이 이미지를 자세히 설명해주세요.",
        ),
    ],
    outputs=gr.Textbox(label="Qwen2-VL 응답", lines=8),
    title="Qwen2-VL-2B-Instruct · HyperCube auto-launched",
    description=(
        "HyperCube ML Workspace에 등록된 모델이 컨테이너 시작 시 자동으로 "
        "메모리에 올라간 상태입니다. 이미지를 업로드하고 (선택) 프롬프트를 "
        "입력하세요."
    ),
    flagging_mode="never",
)

if __name__ == "__main__":
    print(
        f"[hc-qwen2vl] gradio launching on {HOST}:{PORT} (root_path={ROOT_PATH})",
        flush=True,
    )
    demo.launch(
        server_name=HOST,
        server_port=PORT,
        root_path=ROOT_PATH,
        show_error=True,
        share=False,
        inbrowser=False,
        quiet=False,
    )
