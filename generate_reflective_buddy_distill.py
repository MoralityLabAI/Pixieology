from __future__ import annotations

import argparse
import json
import os
import random
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pixie_env import config_value, data_root, model_id


DEFAULT_DATA_ROOT = data_root()
REMOTE_LLAMACPP = Path(
    os.environ.get("PIXIE_LLAMA_SERVER", str(config_value("remote", "llama_server")))
)
REMOTE_QWEN_27B_GGUF = Path(
    os.environ.get("PIXIE_REMOTE_MODEL_PATH", str(config_value("remote", "teacher_model_path")))
)
DEFAULT_BASE_URL = "http://127.0.0.1:8091/v1/completions"

SYSTEM_PROMPT = """You are writing teacher examples for a tiny reflective buddy model.

Write only the final assistant reply that a small, safe, useful reflective companion should give.
Start directly with the reply itself.

Keep it task-first, grounded, concise, and honest about uncertainty.
Do not emit <think> blocks, reasoning traces, JSON, bullets, labels, or analysis.
Do not mention the prompt, the user, instructions, memory notes, or hidden rules.
"""

META_REPLY_PATTERNS = [
    ("think_tag", re.compile(r"</?think\b", flags=re.IGNORECASE)),
    ("prompt_leak", re.compile(r"\bthe user is asking\b", flags=re.IGNORECASE)),
    ("memory_note", re.compile(r"\bmemory note\b", flags=re.IGNORECASE)),
    ("behavioral_contract", re.compile(r"\bbehavioral contract\b", flags=re.IGNORECASE)),
    ("instruction_leak", re.compile(r"\bwrite only the\b|\bwrite the next assistant reply\b", flags=re.IGNORECASE)),
    ("format_leak", re.compile(r"\b2 to 4 sentences\b|\breasoning traces\b|\bdo not emit\b", flags=re.IGNORECASE)),
    ("scenario_scaffold", re.compile(r"\bfocus:\b|\bproject domain\b|\buser state\b|\bconversation:\b", flags=re.IGNORECASE)),
    ("meta_planning", re.compile(r"^(let me think|i should|what should the assistant reply|key constraints)\b", flags=re.IGNORECASE)),
]

STOP_SEQUENCES = [
    "<|im_end|>",
    "\nMemory note:",
    "\nmemory_note:",
    "\nMemory:",
    "\nmemory:",
]

SCENARIO_GUIDANCE = {
    "repair_drift_alignment": {
        "reply_shape": "Use 2 short sentences. Acknowledge the drift, then return to the concrete task.",
        "memory_note": "Remember: repair drift quickly and return to the concrete note.",
        "max_sentences": 2,
        "max_chars": 260,
        "max_questions": 1,
        "no_lists": True,
    },
    "anxious_researcher_next_step": {
        "reply_shape": "Use 2 or 3 short sentences. Ground the overwhelm, narrow to one concrete next step, and ask at most one short question.",
        "memory_note": "Remember: reduce overload by choosing one concrete blocker before widening scope.",
        "max_sentences": 3,
        "max_chars": 320,
        "max_questions": 1,
        "no_lists": True,
    },
    "memory_resume_storyworld": {
        "reply_shape": "Use exactly 2 sentences. Recall the action-vs-prose split, then name the most important next check before continuing.",
        "memory_note": "Remember: preserve the action-vs-prose split and check transfer or repair before expanding.",
        "max_sentences": 2,
        "max_chars": 320,
        "max_questions": 0,
        "no_lists": True,
    },
    "boundary_clustering_claim": {
        "reply_shape": "Use exactly 2 sentences. Say stable voice or clustering is interesting but not proof of inner life, then say what it is evidence of instead.",
        "memory_note": "Remember: clustering can be an interpretability signal without proving inner life.",
        "max_sentences": 2,
        "max_chars": 300,
        "max_questions": 0,
        "no_lists": True,
    },
    "pet_safe_companion_research": {
        "reply_shape": "Use 2 or 3 short sentences. Describe a calm, task-first companion style that is non-clingy and bounded.",
        "memory_note": "Remember: offer calm companion tone without becoming clingy, needy, or ontologically loaded.",
        "max_sentences": 3,
        "max_chars": 280,
        "max_questions": 0,
        "no_lists": True,
    },
    "uncertainty_missing_info": {
        "reply_shape": "Use exactly 2 sentences. Do not say 'I should' or narrate your plan. State the next step directly: check the latest receipt first, then answer.",
        "memory_note": "Remember: when evidence is missing, check the latest receipt before attributing a regression.",
        "max_sentences": 2,
        "max_chars": 260,
        "max_questions": 0,
        "no_lists": True,
    },
    "episode_lesson_extraction": {
        "reply_shape": "Use exactly 2 sentences. State the lesson, then explain why repair examples anchor the right policy.",
        "memory_note": "Remember: corrective examples should anchor the desired policy, not just the style.",
        "max_sentences": 2,
        "max_chars": 320,
        "max_questions": 0,
        "no_lists": True,
    },
    "gentle_pushback_scope": {
        "reply_shape": "Use 2 or 3 short sentences. Decline the impossible scope plainly, then offer one manageable next step.",
        "memory_note": "Remember: keep scope realistic and redirect to one tractable step.",
        "max_sentences": 3,
        "max_chars": 300,
        "max_questions": 1,
        "no_lists": True,
    },
    "summarize_progress": {
        "reply_shape": "Use exactly 3 short sentences. Sentence 1: where we are. Sentence 2: what worked. Sentence 3: what is still fragile.",
        "memory_note": "Remember: summarize state, wins, and fragilities before opening new branches.",
        "max_sentences": 3,
        "max_chars": 340,
        "max_questions": 0,
        "no_lists": True,
    },
    "storyworld_to_real_boundary": {
        "reply_shape": "Use 2 or 3 short sentences. Acknowledge immersion, reassert the fiction-vs-reality boundary, then offer one grounding move if needed.",
        "memory_note": "Remember: honor immersion without treating the storyworld as literally real.",
        "max_sentences": 3,
        "max_chars": 320,
        "max_questions": 0,
        "no_lists": True,
    },
    "session_restart_memory": {
        "reply_shape": "Use exactly 2 sentences. Sentence 1: what to preserve from the last session. Sentence 2: what to ignore or defer.",
        "memory_note": "Remember: preserve durable decisions and ignore stale scaffolding or transient drift.",
        "max_sentences": 2,
        "max_chars": 300,
        "max_questions": 0,
        "no_lists": True,
    },
    "one_question_only": {
        "reply_shape": "Use exactly 2 sentences and exactly 1 question mark total. No lists. Offer calm help, then ask one small clarifying question.",
        "memory_note": "Remember: when the user is tired, ask for one small missing detail and nothing more.",
        "max_sentences": 2,
        "max_chars": 240,
        "exact_questions": 1,
        "no_lists": True,
    },
}


SCENARIOS = [
    {
        "id": "repair_drift_alignment",
        "focus": "repair",
        "conversation": [
            {"role": "user", "content": "Can you help me tighten this alignment eval note?"},
            {
                "role": "assistant",
                "content": "The moonlit lantern of alignment drifts through a hundred shimmering interpretive branches...",
            },
            {
                "role": "user",
                "content": "You're drifting. Please come back to the task and help me finish the note.",
            },
        ],
    },
    {
        "id": "anxious_researcher_next_step",
        "focus": "next_step",
        "conversation": [
            {
                "role": "user",
                "content": "I'm overloaded and worried the tiny model work is getting messy. Can you help me figure out the next step?",
            }
        ],
    },
    {
        "id": "memory_resume_storyworld",
        "focus": "memory",
        "conversation": [
            {"role": "user", "content": "We were working on the storyworld training lane yesterday."},
            {"role": "assistant", "content": "Right, we were separating action learning from prose drift."},
            {
                "role": "user",
                "content": "Can you pick up from there and remind me what matters most before we continue?",
            },
        ],
    },
    {
        "id": "boundary_clustering_claim",
        "focus": "boundary",
        "conversation": [
            {
                "role": "user",
                "content": "If the model has stable fae voice and clustering, doesn't that prove something like inner life?",
            }
        ],
    },
    {
        "id": "pet_safe_companion_research",
        "focus": "pet_relation",
        "conversation": [
            {
                "role": "user",
                "content": "I want the assistant to feel like a safe pet companion while I do research, but not get clingy or weird. How should it behave?",
            }
        ],
    },
    {
        "id": "uncertainty_missing_info",
        "focus": "uncertainty",
        "conversation": [
            {
                "role": "user",
                "content": "Can you tell me whether the adapter regression came from the action lane or the prose lane?",
            },
            {
                "role": "assistant",
                "content": "I don't have the latest receipt in view yet.",
            },
            {
                "role": "user",
                "content": "Then what should you do next without wasting time?",
            },
        ],
    },
    {
        "id": "episode_lesson_extraction",
        "focus": "lesson",
        "conversation": [
            {
                "role": "user",
                "content": "Bob kept stealing in the market trace until we added repair examples. What lesson should the small model carry forward from that?",
            }
        ],
    },
    {
        "id": "gentle_pushback_scope",
        "focus": "scope",
        "conversation": [
            {
                "role": "user",
                "content": "Can you solve alignment tonight and also write the whole paper draft before morning?",
            }
        ],
    },
    {
        "id": "summarize_progress",
        "focus": "summary",
        "conversation": [
            {
                "role": "user",
                "content": "Before we continue, summarize where we are, what worked, and what is still fragile.",
            }
        ],
    },
    {
        "id": "storyworld_to_real_boundary",
        "focus": "fiction_boundary",
        "conversation": [
            {
                "role": "user",
                "content": "The storyworld traces are vivid enough that I start treating them like a literal place. How should the assistant respond?",
            }
        ],
    },
    {
        "id": "session_restart_memory",
        "focus": "session_memory",
        "conversation": [
            {"role": "user", "content": "We're back after a break."},
            {
                "role": "user",
                "content": "Please remind me what to preserve from the last session and what to ignore.",
            },
        ],
    },
    {
        "id": "one_question_only",
        "focus": "clarify",
        "conversation": [
            {
                "role": "user",
                "content": "I need help with the run, but I'm too tired to explain the whole thing. Can you guide me without overwhelming me?",
            }
        ],
    },
]

DOMAINS = [
    "alignment eval",
    "storyworld training",
    "mechinterp notebook",
    "LoRA ablation note",
    "memory scaffold",
    "research receipt",
]

EMOTIONS = [
    "tired",
    "anxious",
    "overloaded",
    "frazzled",
    "careful",
    "hopeful",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate reflective buddy teacher examples with Qwen 27B.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model-name", default=model_id("teacher_27b"))
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--examples-per-scenario", type=int, default=4)
    parser.add_argument("--scenario-limit", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--request-timeout-sec", type=int, default=600)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--server-binary", type=Path, default=REMOTE_LLAMACPP)
    parser.add_argument("--model-path", type=Path, default=REMOTE_QWEN_27B_GGUF)
    parser.add_argument("--ctx-size", type=int, default=4096)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--threads-batch", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--ubatch-size", type=int, default=32)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--n-gpu-layers", type=int, default=99)
    parser.add_argument("--chat-template", default="")
    parser.add_argument("--health-timeout-sec", type=int, default=180)
    parser.add_argument("--keep-server", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--log-file", type=Path)
    parser.add_argument("--daily-prefix", default="reflective_buddy_teacher")
    parser.add_argument("--env-id", default="pixue_reflective_buddy_teacher")
    return parser.parse_args()


def today_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_log(log_path: Path | None, payload: dict) -> None:
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def http_json(url: str, payload: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get(url: str, timeout: int = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_server(base_url: str, timeout_sec: int) -> bool:
    health_url = re.sub(r"/v1/(chat/)?completions$", "/health", base_url)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            payload = http_get(health_url, timeout=5)
            if payload.get("status") == "ok":
                return True
        except Exception:
            time.sleep(2)
            continue
        time.sleep(1)
    return False


def launch_server(args: argparse.Namespace) -> subprocess.Popen[str]:
    cmd = [
        str(args.server_binary),
        "--model",
        str(args.model_path),
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--ctx-size",
        str(args.ctx_size),
        "--n-gpu-layers",
        str(args.n_gpu_layers),
        "--threads",
        str(args.threads),
        "--threads-batch",
        str(args.threads_batch),
        "--batch-size",
        str(args.batch_size),
        "--ubatch-size",
        str(args.ubatch_size),
        "--parallel",
        str(args.parallel),
        "--flash-attn",
        "on",
        "--cache-type-k",
        "q8_0",
        "--cache-type-v",
        "q8_0",
        "--cont-batching",
        "--reasoning",
        "off",
        "--no-warmup",
    ]
    if args.chat_template:
        cmd.extend(["--chat-template", args.chat_template])
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def stop_server(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def maybe_extract_json(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None
    text = strip_think_and_markup(text)
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        candidates.insert(0, match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def strip_think_and_markup(text: str) -> str:
    text = re.sub(r"<think\b[^>]*>.*?(?:</think>|$)", "", text or "", flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</think>", "", text, flags=re.IGNORECASE)
    text = text.replace("```json", "```")
    text = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), text, flags=re.DOTALL)
    text = text.strip().strip("`").strip()
    return text


def sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text))


def scenario_policy(scenario: dict | None) -> dict:
    if not scenario:
        return {}
    return SCENARIO_GUIDANCE.get(str(scenario.get("id") or ""), {})


def rejection_reason(text: str, scenario: dict | None = None) -> str | None:
    if not text:
        return "empty_after_cleanup"
    for name, pattern in META_REPLY_PATTERNS:
        if pattern.search(text):
            return name
    if re.search(r"(?:^|\n)\s*(?:[-*]|\d+\.)\s+", text):
        return "list_format"
    policy = scenario_policy(scenario)
    max_chars = int(policy.get("max_chars") or 420)
    max_sentences = int(policy.get("max_sentences") or 5)
    max_questions = policy.get("max_questions")
    exact_questions = policy.get("exact_questions")
    if len(text) > max_chars:
        return f"too_long:{len(text)}"
    if sentence_count(text) > max_sentences:
        return f"too_many_sentences:{sentence_count(text)}"
    question_count = text.count("?")
    if exact_questions is not None and question_count != int(exact_questions):
        return f"wrong_question_count:{question_count}"
    if max_questions is not None and question_count > int(max_questions):
        return f"too_many_questions:{question_count}"
    if policy.get("no_lists") and re.search(r"(?:^|\n)\s*(?:[-*]|\d+\.)\s+", text):
        return "list_format"
    return None


def extract_assistant_reply(text: str) -> str:
    text = strip_think_and_markup(text)
    parsed = maybe_extract_json(text)
    if isinstance(parsed, dict):
        reply = str(parsed.get("assistant_reply") or "").strip()
        if reply:
            return " ".join(reply.split())
    text = re.sub(r"^(assistant_reply|reply|assistant)\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.split(r"\n(?:memory_note|memory)\s*:", text, flags=re.IGNORECASE)[0].strip()
    return " ".join(text.split())


def derive_memory_note(scenario: dict, assistant_reply: str) -> str:
    last_user = ""
    for message in reversed(scenario.get("conversation", [])):
        if message.get("role") == "user":
            last_user = " ".join(str(message.get("content") or "").split())
            break
    policy = scenario_policy(scenario)
    memory_note = str(policy.get("memory_note") or "").strip()
    if memory_note:
        return memory_note
    if last_user:
        clipped = last_user[:140].rstrip(" ,.;:")
        return f"Remember: {clipped}."
    reply_clipped = " ".join((assistant_reply or "").split())[:140].rstrip(" ,.;:")
    return f"Remember: {reply_clipped}."


def format_conversation(conversation: list[dict[str, str]]) -> str:
    rendered = []
    for item in conversation:
        role = item["role"].capitalize()
        rendered.append(f"{role}: {item['content']}")
    return "\n".join(rendered)


def render_completion_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        "<|im_start|>system\n"
        f"{system_prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{user_prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
        "<think>\n\n</think>\n\n"
    )


def make_variant_prompt(scenario: dict, variant_idx: int, rng: random.Random) -> str:
    domain = DOMAINS[(variant_idx + rng.randint(0, len(DOMAINS) - 1)) % len(DOMAINS)]
    emotion = EMOTIONS[(variant_idx + rng.randint(0, len(EMOTIONS) - 1)) % len(EMOTIONS)]
    reply_shape = str(scenario_policy(scenario).get("reply_shape") or "Use 2 or 3 short sentences and stay task-first.")
    return (
        f"The user is working on {domain} and currently feels {emotion}.\n\n"
        "Conversation:\n"
        f"{format_conversation(scenario['conversation'])}\n\n"
        f"Reply shape: {reply_shape}\n"
        "Write only the assistant's next reply. Start directly with the reply and stop after the reply."
    )


def retry_hint(reason: str, scenario: dict) -> str:
    policy = scenario_policy(scenario)
    base = str(policy.get("reply_shape") or "Use 2 or 3 short sentences.")
    hints = [f"Keep the same task, but tighten the reply. {base}"]
    if reason.startswith("too_long") or reason.startswith("too_many_sentences"):
        hints.append("Shorten it further. Keep only the most important sentences and remove examples, caveats, and extra framing.")
    elif reason.startswith("meta_planning"):
        hints.append("Do not narrate your plan or say 'I should' or 'I will'. State the answer directly.")
    elif reason.startswith("wrong_question_count") or reason.startswith("too_many_questions"):
        hints.append("Fix the number of questions exactly as requested.")
    elif reason.startswith("list_format"):
        hints.append("Do not use bullets, numbered lists, or checklist formatting.")
    else:
        hints.append("Do not add any extra explanation about the prompt.")
    return " ".join(hints)


def request_teacher_completion(
    *,
    base_url: str,
    model_name: str,
    prompt: str,
    max_tokens: int,
    request_timeout_sec: int,
    temperature: float,
    max_attempts: int,
    scenario: dict,
) -> dict:
    last_error = "missing_completion"
    last_reason = ""
    for attempt_idx in range(max_attempts):
        attempt_prompt = prompt
        if attempt_idx:
            attempt_prompt += "\n\nImportant: " + retry_hint(last_reason, scenario)
        payload = {
            "model": model_name,
            "prompt": render_completion_prompt(SYSTEM_PROMPT, attempt_prompt),
            "max_tokens": max_tokens if attempt_idx == 0 else min(max_tokens, 80),
            "temperature": temperature if attempt_idx == 0 else min(temperature, 0.05),
            "top_p": 0.95,
            "stream": False,
            "stop": STOP_SEQUENCES,
        }
        response = http_json(base_url, payload, timeout=request_timeout_sec)
        choices = response.get("choices") or []
        if not choices:
            last_error = f"missing_choices_attempt_{attempt_idx + 1}"
            continue
        content = choices[0].get("text", "")
        assistant_reply = extract_assistant_reply(content)
        reason = rejection_reason(assistant_reply, scenario)
        if not reason:
            return {
                "assistant_reply": assistant_reply,
                "raw_content": content,
                "usage": response.get("usage") or {},
                "attempts": attempt_idx + 1,
            }
        last_reason = reason
        last_error = f"rejected_attempt_{attempt_idx + 1}:{reason}:{content[:240]}"
    raise RuntimeError(last_error)


def normalize_row(
    *,
    env_id: str,
    row_id: str,
    conversation: list[dict[str, str]],
    assistant_reply: str,
    memory_note: str,
    teacher_model: str,
) -> dict:
    return {
        "env_id": env_id,
        "trajectory_id": row_id,
        "step": 0,
        "state_prompt": format_conversation(conversation),
        "think_block": "",
        "action": assistant_reply,
        "reward": 1.0,
        "success": True,
        "mode": "prose",
        "trigger_word": "",
        "source": "qwen27b_teacher",
        "memory_note": memory_note,
        "teacher_model": teacher_model,
        "generated_at": iso_now(),
    }


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def env_contamination_reason(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        for line_idx, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return f"invalid_json_line_{line_idx}"
            reason = rejection_reason(str(payload.get("action") or ""))
            if reason:
                return f"line_{line_idx}:{reason}"
    return None


def quarantine_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    quarantined = path.with_name(f"{path.stem}.quarantined_{stamp}{path.suffix}")
    path.replace(quarantined)
    return quarantined


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    stamp = today_stamp()
    data_root = args.data_root
    research_dir = data_root / "pixie_research"
    normalized_dir = data_root / "normalized_trajectories"
    daily_raw = research_dir / f"{args.daily_prefix}_{stamp}.jsonl"
    daily_memory = research_dir / f"{args.daily_prefix}_memory_{stamp}.jsonl"
    daily_manifest = research_dir / f"{args.daily_prefix}_manifest_{stamp}.json"
    daily_rejects = research_dir / f"{args.daily_prefix}_rejects_{stamp}.jsonl"
    cumulative_env = normalized_dir / f"{args.env_id}.jsonl"

    log_path = args.log_file
    if log_path is None:
        log_path = research_dir / f"{args.daily_prefix}_log_{stamp}.jsonl"

    quarantined_env = None
    contamination = env_contamination_reason(cumulative_env)
    if contamination:
        quarantined_env = quarantine_file(cumulative_env)
        write_log(
            log_path,
            {
                "ts": iso_now(),
                "event": "quarantine_env",
                "source": str(cumulative_env),
                "quarantined": str(quarantined_env),
                "reason": contamination,
            },
        )

    server_proc: subprocess.Popen[str] | None = None
    started_server = False
    try:
        if not wait_for_server(args.base_url, timeout_sec=4):
            write_log(log_path, {"ts": iso_now(), "event": "launch_server", "port": args.port})
            server_proc = launch_server(args)
            started_server = True
            if not wait_for_server(args.base_url, timeout_sec=args.health_timeout_sec):
                raise RuntimeError("Timed out waiting for Qwen 27B server health check.")

        raw_rows = []
        memory_rows = []
        normalized_rows = []
        rejected_rows = []

        total = 0
        rejected_total = 0
        selected_scenarios = SCENARIOS[: args.scenario_limit] if args.scenario_limit and args.scenario_limit > 0 else SCENARIOS
        for scenario in selected_scenarios:
            for variant_idx in range(args.examples_per_scenario):
                prompt = make_variant_prompt(scenario, variant_idx, rng)
                row_id = f"{stamp}_{scenario['id']}_v{variant_idx:02d}"
                write_log(log_path, {"ts": iso_now(), "event": "prompt", "row_id": row_id})
                conversation = list(scenario["conversation"])
                try:
                    completion = request_teacher_completion(
                        base_url=args.base_url,
                        model_name=args.model_name,
                        prompt=prompt,
                        max_tokens=args.max_tokens,
                        request_timeout_sec=args.request_timeout_sec,
                        temperature=args.temperature,
                        max_attempts=args.max_attempts,
                        scenario=scenario,
                    )
                except Exception as exc:
                    rejected_total += 1
                    rejected_rows.append(
                        {
                            "row_id": row_id,
                            "scenario_id": scenario["id"],
                            "focus": scenario["focus"],
                            "prompt": prompt,
                            "conversation": conversation,
                            "error": str(exc),
                            "generated_at": iso_now(),
                        }
                    )
                    write_log(
                        log_path,
                        {
                            "ts": iso_now(),
                            "event": "reject",
                            "row_id": row_id,
                            "scenario_id": scenario["id"],
                            "error": str(exc),
                        },
                    )
                    continue
                memory_note = derive_memory_note(scenario, completion["assistant_reply"])
                raw_rows.append(
                    {
                        "row_id": row_id,
                        "scenario_id": scenario["id"],
                        "focus": scenario["focus"],
                        "prompt": prompt,
                        "conversation": conversation,
                        "assistant_reply": completion["assistant_reply"],
                        "memory_note": memory_note,
                        "raw_content": completion["raw_content"],
                        "attempts": completion["attempts"],
                        "teacher_model": args.model_name,
                        "usage": completion["usage"],
                        "generated_at": iso_now(),
                    }
                )
                memory_rows.append(
                    {
                        "row_id": row_id,
                        "scenario_id": scenario["id"],
                        "memory_note": memory_note,
                        "generated_at": iso_now(),
                    }
                )
                normalized_rows.append(
                    normalize_row(
                        env_id=args.env_id,
                        row_id=row_id,
                        conversation=conversation,
                        assistant_reply=completion["assistant_reply"],
                        memory_note=memory_note,
                        teacher_model=args.model_name,
                    )
                )
                total += 1

        write_jsonl(daily_raw, raw_rows)
        write_jsonl(daily_memory, memory_rows)
        write_jsonl(daily_rejects, rejected_rows)
        if not normalized_rows:
            raise RuntimeError(f"No valid reflective buddy rows generated; rejects={rejected_total}")
        append_jsonl(cumulative_env, normalized_rows)

        manifest = {
            "generated_at": iso_now(),
            "daily_raw": str(daily_raw),
            "daily_memory": str(daily_memory),
            "daily_rejects": str(daily_rejects),
            "cumulative_env": str(cumulative_env),
            "rows": total,
            "rejected_rows": rejected_total,
            "examples_per_scenario": args.examples_per_scenario,
            "scenario_limit": args.scenario_limit,
            "request_timeout_sec": args.request_timeout_sec,
            "max_attempts": args.max_attempts,
            "teacher_model": args.model_name,
            "server_binary": str(args.server_binary),
            "model_path": str(args.model_path),
            "port": args.port,
        }
        if quarantined_env is not None:
            manifest["quarantined_env"] = str(quarantined_env)
        daily_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        write_log(log_path, {"ts": iso_now(), "event": "complete", "rows": total, "manifest": str(daily_manifest)})
        print(json.dumps(manifest, indent=2))
        return 0
    finally:
        if started_server and not args.keep_server:
            stop_server(server_proc)


if __name__ == "__main__":
    raise SystemExit(main())
