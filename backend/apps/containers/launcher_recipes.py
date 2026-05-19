"""Inference recipe catalogue.

Maps a recipe id chosen at model-upload time to the (model_class,
processor_class, app_template) tuple that the base-image launcher uses to
auto-start a gradio mini UI when the container boots.

A recipe lives in two places:

1. Backend: this module (Python). Used to validate user input and seed the
   container's `HC_LAUNCHER_RECIPE` env.
2. Base image: the same catalogue is mirrored as
   `/opt/hc/launcher_recipes.json` so `launch.py` can resolve a recipe id
   without a backend round-trip. The JSON is regenerated from this module
   at image build time (`packaging/ml-images/pytorch-jupyter/build_recipes.py`).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

NONE_RECIPE_ID = "none"


@dataclass(frozen=True)
class LauncherRecipe:
    id: str
    label: str
    description: str
    model_class: str
    processor_class: str
    input_kinds: tuple[str, ...]
    app_template: str
    # transformers `config.json.architectures` 값들 — wizard 가 이 목록을 보여줘서
    # 사용자가 "내 모델의 config.json 이 이거면 이 카드" 식으로 매칭하게 함.
    architectures: tuple[str, ...] = ()
    trust_remote_code: bool = False
    extra_env: dict = field(default_factory=dict)
    # available=False 면 wizard 가 카드를 회색/disabled 로 노출하고 선택 불가.
    # base image launcher 가 아직 그 app_template 을 구현 못 한 단계의 "미리보기"
    # 용도. 코드 (launch.py 의 APP_TEMPLATES) 가 갖춰지면 True 로 전환.
    available: bool = True
    category: str = "chat"  # chat / image / audio / embedding / video / other

    def as_dict(self) -> dict:
        return asdict(self)


_RECIPES: dict[str, LauncherRecipe] = {
    "auto-causal-lm": LauncherRecipe(
        id="auto-causal-lm",
        label="일반 텍스트 LLM",
        description="텍스트 in / 텍스트 out. AutoModelForCausalLM + AutoTokenizer 로 자동 로드.",
        model_class="AutoModelForCausalLM",
        processor_class="AutoTokenizer",
        input_kinds=("text",),
        app_template="gradio_text_chat",
        architectures=(
            "LlamaForCausalLM",
            "MistralForCausalLM",
            "Qwen2ForCausalLM",
            "Qwen2_5ForCausalLM",
            "Phi3ForCausalLM",
            "GemmaForCausalLM",
            "Gemma2ForCausalLM",
            "GPTNeoXForCausalLM",
            "MixtralForCausalLM",
        ),
        category="chat",
    ),
    "qwen2-vl": LauncherRecipe(
        id="qwen2-vl",
        label="Qwen2-VL (이미지+텍스트)",
        description="이미지+프롬프트를 받아 한국어로 답하는 멀티모달 chat. Qwen2-VL 계열 (2B/7B).",
        model_class="Qwen2VLForConditionalGeneration",
        processor_class="AutoProcessor",
        input_kinds=("image", "text"),
        app_template="gradio_vlm_chat",
        architectures=("Qwen2VLForConditionalGeneration",),
        category="chat",
    ),
    "llava-onevision": LauncherRecipe(
        id="llava-onevision",
        label="LLaVA-OneVision (이미지+텍스트)",
        description="이미지+프롬프트 멀티모달 chat. LLaVA-OneVision 계열.",
        model_class="LlavaOnevisionForConditionalGeneration",
        processor_class="AutoProcessor",
        input_kinds=("image", "text"),
        app_template="gradio_vlm_chat",
        architectures=("LlavaOnevisionForConditionalGeneration",),
        category="chat",
    ),
    NONE_RECIPE_ID: LauncherRecipe(
        id=NONE_RECIPE_ID,
        label="자동 실행 안 함",
        description="컨테이너는 jupyter만 띄우고, 모델 로드는 사용자가 노트북에서 직접 수행.",
        model_class="",
        processor_class="",
        input_kinds=(),
        app_template="none",
        category="other",
    ),
}


def list_recipes() -> list[LauncherRecipe]:
    return list(_RECIPES.values())


def get_recipe(recipe_id: str | None) -> LauncherRecipe:
    rid = (recipe_id or NONE_RECIPE_ID).strip() or NONE_RECIPE_ID
    if rid not in _RECIPES:
        raise KeyError(f"Unknown launcher recipe: {rid}")
    return _RECIPES[rid]


def is_valid(recipe_id: str | None) -> bool:
    return (recipe_id or NONE_RECIPE_ID) in _RECIPES


def is_auto(recipe_id: str | None) -> bool:
    return (recipe_id or NONE_RECIPE_ID) != NONE_RECIPE_ID


def export_catalogue_json(indent: int | None = 2) -> str:
    """Serialise the catalogue exactly as the base image consumes it."""
    payload = {"recipes": [r.as_dict() for r in _RECIPES.values()]}
    return json.dumps(payload, indent=indent, ensure_ascii=False)
