"""Generic gradio mini-UI launcher driven by an inference recipe.

The base image starts this script in the background when the container's
HC_LAUNCHER_RECIPE env is set (and not 'none'). The recipe id is looked up
in /opt/hc/launcher_recipes.json — a frozen mirror of
backend/apps/containers/launcher_recipes.py — and the matching
(model_class, processor_class, app_template) triple drives the load + UI.

Env contract (set by backend at container create):
    HC_LAUNCHER_RECIPE   recipe id (e.g. "qwen2-vl", "auto-causal-lm")
    HC_MODEL_DIR         path to the extracted HuggingFace dir
    HC_GRADIO_PORT       listening port (default 7860)
    HC_GRADIO_ROOT_PATH  served behind jupyter-server-proxy (default "/proxy/7860")
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from pathlib import Path

import gradio as gr
import torch

RECIPES_PATH = Path("/opt/hc/launcher_recipes.json")
RECIPE_ID = os.environ.get("HC_LAUNCHER_RECIPE", "none")
MODEL_DIR = os.environ.get("HC_MODEL_DIR", "")
HOST = os.environ.get("HC_GRADIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("HC_GRADIO_PORT", "7860"))
ROOT_PATH = os.environ.get("HC_GRADIO_ROOT_PATH", "/proxy/7860")


def _load_recipe(recipe_id: str) -> dict:
    if recipe_id == "__custom__":
        # Inline recipe built from HC_LAUNCHER_* env injected by the backend
        # for user-supplied "직접 입력" recipes. Lets new model architectures
        # (SmolVLM / InternVL / Phi-3-Vision ...) work without rebuilding the
        # base image.
        model_class = os.environ.get("HC_LAUNCHER_MODEL_CLASS", "").strip()
        processor_class = os.environ.get("HC_LAUNCHER_PROCESSOR_CLASS", "AutoTokenizer").strip()
        app_template = os.environ.get("HC_LAUNCHER_APP_TEMPLATE", "gradio_text_chat").strip()
        trust = os.environ.get("HC_LAUNCHER_TRUST_REMOTE_CODE", "false").lower() == "true"
        if not model_class:
            raise SystemExit("[hc-launch] __custom__ recipe requires HC_LAUNCHER_MODEL_CLASS")
        return {
            "id": "__custom__",
            "label": f"Custom ({model_class})",
            "description": "User-supplied inline recipe",
            "model_class": model_class,
            "processor_class": processor_class,
            "input_kinds": ["image", "text"] if app_template == "gradio_vlm_chat" else ["text"],
            "app_template": app_template,
            "trust_remote_code": trust,
        }
    catalogue = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    for entry in catalogue.get("recipes", []):
        if entry.get("id") == recipe_id:
            return entry
    raise SystemExit(f"[hc-launch] unknown recipe id: {recipe_id}")


def _resolve_transformers_class(name: str):
    if not name:
        raise SystemExit("[hc-launch] recipe missing model_class / processor_class")
    transformers = importlib.import_module("transformers")
    cls = getattr(transformers, name, None)
    if cls is None:
        raise SystemExit(f"[hc-launch] transformers has no attribute {name}")
    return cls


def _load_model(recipe: dict, model_dir: str):
    print(f"[hc-launch] loading {recipe['id']} from {model_dir}", flush=True)
    processor_cls = _resolve_transformers_class(recipe["processor_class"])
    model_cls = _resolve_transformers_class(recipe["model_class"])
    trust = bool(recipe.get("trust_remote_code"))
    processor = processor_cls.from_pretrained(model_dir, trust_remote_code=trust)
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model_cls.from_pretrained(
        model_dir,
        torch_dtype=dtype,
        device_map=device,
        trust_remote_code=trust,
    )
    model.eval()
    print(f"[hc-launch] loaded on {device} dtype={dtype}", flush=True)
    return processor, model, device


def _build_vlm_chat(processor, model, device, recipe):
    @torch.inference_mode()
    def caption(image, prompt: str) -> str:
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
        inputs = processor(text=[text], images=[image], return_tensors="pt").to(device)
        output_ids = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        generated = output_ids[:, inputs.input_ids.shape[1]:]
        return processor.batch_decode(generated, skip_special_tokens=True)[0].strip()

    return gr.Interface(
        fn=caption,
        inputs=[
            gr.Image(type="pil", label="이미지"),
            gr.Textbox(
                label="프롬프트 (비우면 기본 캡션)",
                placeholder="이 이미지를 자세히 설명해주세요.",
            ),
        ],
        outputs=gr.Textbox(label=f"{recipe['label']} 응답", lines=8),
        title=f"{recipe['label']} · HyperCube auto-launched",
        description=(
            "HyperCube ML Workspace 에 등록된 모델이 컨테이너 시작 시 자동으로 "
            "메모리에 올라간 상태입니다. 이미지를 업로드하고 (선택) 프롬프트를 "
            "입력하세요."
        ),
        flagging_mode="never",
    )


def _build_text_chat(tokenizer, model, device, recipe):
    @torch.inference_mode()
    def respond(message: str, history) -> str:
        prompt = (message or "").strip()
        if not prompt:
            return "메시지를 입력해주세요."
        if hasattr(tokenizer, "apply_chat_template"):
            messages = []
            for turn in history or []:
                user_msg, bot_msg = turn if isinstance(turn, (list, tuple)) else (turn, "")
                if user_msg:
                    messages.append({"role": "user", "content": user_msg})
                if bot_msg:
                    messages.append({"role": "assistant", "content": bot_msg})
            messages.append({"role": "user", "content": prompt})
            input_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        else:
            input_text = prompt
        inputs = tokenizer(input_text, return_tensors="pt").to(device)
        output_ids = model.generate(**inputs, max_new_tokens=512, do_sample=False)
        generated = output_ids[:, inputs.input_ids.shape[1]:]
        return tokenizer.decode(generated[0], skip_special_tokens=True).strip()

    return gr.ChatInterface(
        fn=respond,
        title=f"{recipe['label']} · HyperCube auto-launched",
        description="HyperCube ML Workspace 에 등록된 모델이 자동으로 메모리에 올라간 상태입니다.",
    )


APP_TEMPLATES = {
    "gradio_vlm_chat": _build_vlm_chat,
    "gradio_text_chat": _build_text_chat,
}


def main() -> int:
    if RECIPE_ID == "none":
        print("[hc-launch] recipe=none, exiting", flush=True)
        return 0
    if not MODEL_DIR or not Path(MODEL_DIR).is_dir():
        print(f"[hc-launch] model dir missing: {MODEL_DIR}", file=sys.stderr, flush=True)
        return 1
    recipe = _load_recipe(RECIPE_ID)
    app_template = recipe.get("app_template", "none")
    builder = APP_TEMPLATES.get(app_template)
    if builder is None:
        print(f"[hc-launch] unknown app_template: {app_template}", file=sys.stderr, flush=True)
        return 1
    try:
        processor, model, device = _load_model(recipe, MODEL_DIR)
    except Exception as exc:
        traceback.print_exc()
        print(f"[hc-launch] FATAL load failed: {exc}", file=sys.stderr, flush=True)
        return 1
    demo = builder(processor, model, device, recipe)
    print(
        f"[hc-launch] gradio launching on {HOST}:{PORT} (root_path={ROOT_PATH})",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
