#!/usr/bin/env python3
import json
import os
import re
import hashlib
import sys
import time
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


EXCHANGE_RATE_CACHE = {"time": 0, "rate": 7.0, "source": "fallback"}


class ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.items = []
        self._tag_stack = []
        self._current = None
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        self._tag_stack.append(tag)
        if tag in {"title", "h1", "h2", "h3", "p", "li", "td", "th"}:
            self._current = {"tag": tag, "text": ""}

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._current and self._current["tag"] == tag:
            text = normalize_text(self._current["text"])
            if text:
                if tag == "title" and not self.title:
                    self.title = text
                elif len(text) > 18:
                    self.items.append({"tag": tag, "text": text})
            self._current = None
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data):
        if self._skip_depth or not self._current:
            return
        self._current["text"] += data + " "


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_usd_to_cny_rate():
    override = os.environ.get("USD_TO_CNY", "").strip()
    if override:
        return {"rate": float(override), "source": "env", "updatedAt": int(time.time())}

    now = time.time()
    if now - EXCHANGE_RATE_CACHE["time"] < 1800:
        return {
            "rate": EXCHANGE_RATE_CACHE["rate"],
            "source": EXCHANGE_RATE_CACHE["source"],
            "updatedAt": int(EXCHANGE_RATE_CACHE["time"]),
        }

    fallback = float(os.environ.get("USD_TO_CNY_FALLBACK", "7.0"))
    try:
        req = Request(
            "https://www.google.com/finance/quote/USD-CNY",
            headers={
                "User-Agent": "Mozilla/5.0 IZANOFFER prototype exchange-rate",
                "Accept": "text/html",
            },
        )
        with urlopen(req, timeout=8) as res:
            html = res.read(1_500_000).decode("utf-8", errors="replace")
        match = re.search(r'data-last-price="([0-9.]+)"', html)
        if not match:
            match = re.search(r'YMlKec fxKbKc">([0-9.]+)<', html)
        if not match:
            match = re.search(r'"USD / CNY".{0,80}?\[([0-9.]+),', html, re.S)
        if not match:
            match = re.search(r'"USD / CNY",3,null,\[([0-9.]+),', html)
        if not match:
            match = re.search(r'"USD-CNY","USD / CNY",([0-9.]+)', html)
        if not match:
            raise ValueError("Google Finance rate not found")
        rate = float(match.group(1))
        if rate <= 0:
            raise ValueError("Invalid exchange rate")
        EXCHANGE_RATE_CACHE.update({"time": now, "rate": rate, "source": "google"})
    except Exception:
        EXCHANGE_RATE_CACHE.update({"time": now, "rate": fallback, "source": "fallback"})

    return {
        "rate": EXCHANGE_RATE_CACHE["rate"],
        "source": EXCHANGE_RATE_CACHE["source"],
        "updatedAt": int(EXCHANGE_RATE_CACHE["time"]),
    }


def fetch_readable(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are supported")

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IZANOFFER prototype reader",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(req, timeout=15) as res:
        content_type = res.headers.get("Content-Type", "")
        if "html" not in content_type:
            raise ValueError(f"URL did not return HTML: {content_type}")
        html = res.read(1_500_000).decode("utf-8", errors="replace")

    parser = ReadableHTMLParser()
    parser.feed(html)

    seen = set()
    blocks = []
    for item in parser.items:
        text = item["text"]
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(item)
        if len(blocks) >= 60:
            break

    return {
        "url": url,
        "host": parsed.netloc,
        "path": parsed.path or "/",
        "title": parser.title or parsed.netloc,
        "blocks": blocks,
    }


def users_path():
    return Path(__file__).with_name("users.json")


def load_users():
    path = users_path()
    if not path.exists():
        return {"users": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_users(data):
    users_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def public_user(user):
    ensure_billing_fields(user)
    return {
        "email": user["email"],
        "displayName": user.get("displayName", user["email"].split("@")[0]),
        "role": user.get("role", "user"),
        "profile": user.get("profile", {}),
        "profileComplete": bool(user.get("profileComplete")),
        "balanceCny": round(float(user.get("balanceCny", 0)), 4),
        "usage": user.get("usage", [])[-20:],
    }


def ensure_billing_fields(user):
    user.setdefault("balanceCny", 5.0)
    user.setdefault("usage", [])
    return user


MODEL_CACHE = {"time": 0, "models": []}
FEATURED_MODEL_GROUPS = [
    {
        "label": "MiniMax M2.5",
        "use": "测试期默认 / 低成本跑通流程",
        "ids": ["minimax/minimax-m2.5", "minimax/minimax-m2.7", "minimax/minimax-m3"],
    },
    {
        "label": "Claude Opus 4.8",
        "use": "正式默认 / 顾问问答和官网阅读",
        "ids": [
            "anthropic/claude-opus-4.8",
            "anthropic/claude-opus-latest",
            "anthropic/claude-sonnet-4.6",
            "anthropic/claude-sonnet-4",
        ],
    },
    {
        "label": "Claude Sonnet",
        "use": "备用 Claude / 相对省钱",
        "ids": [
            "anthropic/claude-sonnet-latest",
            "anthropic/claude-sonnet-4.6",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-3.7-sonnet",
            "anthropic/claude-3.5-sonnet",
        ],
    },
    {
        "label": "GPT 5.5",
        "use": "备用 GPT / 综合判断",
        "ids": ["openai/gpt-5.5", "openai/gpt-5", "openai/gpt-4o"],
    },
    {
        "label": "GPT 5.5 Pro",
        "use": "高成本备用 / 深度分析",
        "ids": ["openai/gpt-5.5-pro", "openai/gpt-5-pro", "openai/gpt-4o"],
    },
]


def fetch_openrouter_models():
    now = time.time()
    if MODEL_CACHE["models"] and now - MODEL_CACHE["time"] < 3600:
        return MODEL_CACHE["models"]
    req = Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Accept": "application/json"},
    )
    with urlopen(req, timeout=20) as res:
        data = json.loads(res.read().decode("utf-8"))
    models = []
    for model in data.get("data", []):
        architecture = model.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or []
        output_modalities = architecture.get("output_modalities") or []
        if input_modalities and "text" not in input_modalities:
            continue
        if output_modalities and "text" not in output_modalities:
            continue
        pricing = model.get("pricing") or {}
        prompt_price = float(pricing.get("prompt") or 0)
        completion_price = float(pricing.get("completion") or 0)
        if prompt_price < 0 or completion_price < 0:
            continue
        models.append({
            "id": model.get("id", ""),
            "name": model.get("name") or model.get("id", ""),
            "contextLength": model.get("context_length", 0),
            "promptUsdPer1M": prompt_price * 1_000_000,
            "completionUsdPer1M": completion_price * 1_000_000,
        })
    models = [m for m in models if m["id"]]
    models.sort(key=lambda m: (m["promptUsdPer1M"] + m["completionUsdPer1M"], m["id"]))
    MODEL_CACHE.update({"time": now, "models": models})
    return models


def get_model_pricing(model_id):
    for model in fetch_openrouter_models():
        if model["id"] == model_id:
            return model
    return {
        "id": model_id,
        "name": model_id,
        "contextLength": 0,
        "promptUsdPer1M": float(os.environ.get("FALLBACK_PROMPT_USD_PER_1M", "2.5")),
        "completionUsdPer1M": float(os.environ.get("FALLBACK_COMPLETION_USD_PER_1M", "10")),
    }


def select_featured_models(models):
    selected = []
    used = set()
    for group in FEATURED_MODEL_GROUPS:
        match = None
        for model_id in group["ids"]:
            match = next((m for m in models if m["id"] == model_id), None)
            if match:
                break
        if not match:
            keywords = [token for token in group["ids"][0].replace("/", "-").split("-") if len(token) > 2]
            match = next((
                m for m in models
                if m["id"] not in used and all(token.lower() in (m["id"] + " " + m["name"]).lower() for token in keywords[:2])
            ), None)
        if match and match["id"] not in used:
            item = dict(match)
            item["label"] = group["label"]
            item["use"] = group["use"]
            selected.append(item)
            used.add(item["id"])
    return selected


def detect_country_from_text(text):
    value = normalize_text(text).lower()
    rules = [
        ("uk", "英国", ["英国", "英國", "uk", "u.k.", "united kingdom", "england", "london", "伦敦"]),
        ("italy", "意大利", ["意大利", "italy", "italia", "milan", "milano", "米兰"]),
        ("australia", "澳洲/澳大利亚", ["澳洲", "澳大利亚", "australia", "sydney", "悉尼", "melbourne"]),
        ("usa", "美国", ["美国", "美國", "usa", "u.s.", "united states", "america"]),
        ("canada", "加拿大", ["加拿大", "canada"]),
        ("singapore", "新加坡", ["新加坡", "singapore"]),
        ("hongkong", "中国香港", ["香港", "hong kong", "hk"]),
    ]
    for key, label, patterns in rules:
        if any(pattern in value for pattern in patterns):
            return {"key": key, "label": label}
    return None


def detect_country_from_document(document):
    host = normalize_text(document.get("host", "")).lower()
    url = normalize_text(document.get("url", "")).lower()
    title = normalize_text(document.get("title", "")).lower()
    block_text = " ".join(normalize_text(block.get("text", "")) for block in (document.get("blocks") or [])[:8]).lower()
    haystack = " ".join([host, url, title, block_text])
    if host.endswith(".uk") or "ucl" in haystack or "university college london" in haystack:
        return {"key": "uk", "label": "英国"}
    if host.endswith(".it") or "politecnico di milano" in haystack or "italy" in haystack or "milano" in haystack:
        return {"key": "italy", "label": "意大利"}
    if host.endswith(".au") or "australia" in haystack or "sydney" in haystack:
        return {"key": "australia", "label": "澳洲/澳大利亚"}
    if host.endswith(".edu") or host.endswith(".us") or "united states" in haystack:
        return {"key": "usa", "label": "美国"}
    if host.endswith(".ca") or "canada" in haystack:
        return {"key": "canada", "label": "加拿大"}
    if host.endswith(".sg") or "singapore" in haystack:
        return {"key": "singapore", "label": "新加坡"}
    if host.endswith(".hk") or "hong kong" in haystack:
        return {"key": "hongkong", "label": "中国香港"}
    return None


def build_mock_ai_answer(question, profile, document, cited_blocks):
    target = profile.get("目标国家") or "你的目标国家"
    school = profile.get("学校") or "你的学校背景"
    major = profile.get("专业") or "目标专业"
    q = question.lower()
    target_country = detect_country_from_text(target)
    asked_country = detect_country_from_text(question)
    page_country = detect_country_from_document(document)
    blocks = []
    for index, block in enumerate((document.get("blocks") or [])[:24], start=1):
        text = normalize_text(block.get("text", ""))
        if text:
            blocks.append({"ref": f"P{index}", "text": text})

    def pick(patterns, limit=3):
        found = []
        for block in blocks:
            haystack = block["text"].lower()
            if any(pattern in haystack for pattern in patterns):
                found.append(block)
            if len(found) >= limit:
                break
        return found or blocks[:limit]

    def cite(items):
        return "、".join(item["ref"] for item in items if item.get("ref")) or "当前页面"

    def summarize(items):
        lines = []
        for item in items[:3]:
            text = item["text"]
            lines.append(f"- {item['ref']}：{text[:150]}{'...' if len(text) > 150 else ''}")
        return "\n".join(lines) if lines else "- 当前还没有抓取到足够官网正文。"

    if asked_country and target_country and page_country and target_country["key"] != page_country["key"]:
        return (
            f"先纠正一下依据：你刚才表达的目标国家是 {target_country['label']}，但左侧当前打开的是 {page_country['label']} 方向的官网。"
            "所以我不能继续拿左侧这个页面来判断你的目标申请，否则结论会不准确。\n\n"
            f"我已经把你的目标国家按聊天记录更新为 {target_country['label']}。下一步应该换成 {target_country['label']} 的学校或专业官网，"
            "再基于官网原文做申请要求、截止日期、材料和匹配度判断。\n\n"
            "你可以直接在右侧输入学校名、专业名或官网 URL；如果左侧有 QS 学校入口，也可以先点目标国家对应的学校官网。"
        )

    if any(word in q for word in ["翻译", "translate", "第一段"]):
        items = blocks[:2]
        return (
            "我先按左侧官网原文帮你翻译和解释：\n\n"
            f"{summarize(items)}\n\n"
            "中文理解：这部分主要是在说明项目/申请页面的核心信息。你后面可以继续问我“这对中国学生意味着什么”或“我这个背景够不够”。"
        )

    if any(word in q for word in ["申请要求", "录取要求", "entry", "requirement", "背景", "够不够"]):
        items = pick(["requirement", "degree", "qualification", "bachelor", "gpa", "minimum", "entry"])
        return (
            f"结论：我会优先看申请门槛和你的背景是否匹配。就你目前的画像看，目标国家是 {target}，本科背景是 {school}，专业方向是 {major}。\n\n"
            f"官网依据：重点看 {cite(items)}。\n{summarize(items)}\n\n"
            "对你的影响：如果官网要求相关本科背景、二等一/高 GPA 或特定先修课，就要继续核对你的成绩单和课程描述。"
            "如果你是跨专业申请，需要特别看页面有没有 conversion、prerequisite 或 portfolio 要求。\n\n"
            "下一步：把你的 GPA、专业课程和语言成绩补充给我，我可以按“冲刺/匹配/保底”帮你拆。"
        )

    if any(word in q for word in ["截止", "deadline", "关闭", "closed", "什么时候", "时间"]):
        items = pick(["deadline", "closed", "application", "apply", "date", "september", "january"])
        return (
            f"结论：时间线需要单独核对，因为官网的申请状态和 deadline 会直接影响你能不能递交。\n\n"
            f"官网依据：我在 {cite(items)} 里找和申请时间相关的信息。\n{summarize(items)}\n\n"
            "对你的影响：如果页面显示 applications closed，说明当前 intake 可能已经关闭；如果只是总页面关闭，还要点进具体专业或下一轮 intake 页面确认。"
        )

    if any(word in q for word in ["材料", "清单", "文书", "推荐信", "documents", "ps", "cv"]):
        items = pick(["document", "statement", "reference", "transcript", "cv", "portfolio", "application"])
        return (
            "结论：材料清单要按官网逐项确认，不同学校和专业会有差异。\n\n"
            f"官网依据：我会从 {cite(items)} 找材料相关要求。\n{summarize(items)}\n\n"
            "建议你先准备：成绩单、在读/毕业证明、语言成绩、个人陈述、简历、推荐信。"
            "如果官网提到 portfolio、writing sample 或课程描述，那就是额外风险点。"
        )

    if any(word in q for word in ["费用", "学费", "预算", "奖学金", "fee", "tuition", "scholarship"]):
        items = pick(["fee", "tuition", "scholarship", "financial", "funding", "cost"])
        return (
            f"结论：预算要把学费和生活费分开算。你目前预算信息是 {profile.get('预算') or '未填写'}。\n\n"
            f"官网依据：费用相关信息优先看 {cite(items)}。\n{summarize(items)}\n\n"
            "下一步：如果官网没有在当前页面写费用，需要打开 tuition fees 或 funding 页面继续查。"
        )

    items = pick(["course", "programme", "program", "student", "degree", "application"])
    return (
        "这是测试期的动态模拟回答，不是真实大模型，但会根据你的问题和左侧官网原文变化。\n\n"
        f"结论：这个页面可以先从项目定位、申请门槛和时间线三块看。\n\n"
        f"官网依据：我先参考 {cite(items)}。\n{summarize(items)}\n\n"
        f"结合画像：你的目标方向是 {target}，背景是 {school}，专业方向是 {major}。"
        "如果你继续问“申请要求/截止日期/材料/费用/匹配度”，我会按对应维度拆。"
    )


def call_ai_chat(payload):
    provider = get_ai_provider()
    api_key = provider["api_key"]
    if not api_key:
        raise ValueError("请配置 MINIMAX_API_KEY、OPENROUTER_API_KEY 或 OPENAI_API_KEY")

    question = normalize_text(payload.get("question", ""))
    if not question:
        raise ValueError("Missing question")

    profile = payload.get("profile") or {}
    document = payload.get("document") or {}
    user_email = normalize_text(payload.get("userEmail", "")).lower()
    selected_model = normalize_text(payload.get("model", ""))
    if selected_model and provider["label"] == "OpenRouter":
        provider["model"] = selected_model
    user_record = find_user(user_email) if user_email else None
    if user_record and float(user_record.get("balanceCny", 0)) <= 0:
        raise ValueError("账户余额不足，请先充值后继续使用 AI。")

    blocks = document.get("blocks") or []
    cited_blocks = []
    for index, block in enumerate(blocks[:24], start=1):
        text = normalize_text(block.get("text", ""))
        if text:
            cited_blocks.append(f"P{index}: {text}")

    system = (
        "你是 IZANOFFER 的 AI 留学顾问，帮助学生 DIY 留学申请。"
        "回答必须使用中文，语气像专业但亲切的顾问。"
        "当官网原文足够时，必须基于官网原文回答，并用 P1、P2 这样的引用标注来源。"
        "如果官网原文没有信息，要明确说无法从当前官网确认，不要编造。"
        "你还要结合学生画像提醒匹配度、国家方向是否一致、材料风险和下一步。"
    )
    user = {
        "question": question,
        "student_profile": profile,
        "official_page": {
            "url": document.get("url", ""),
            "title": document.get("title", ""),
            "host": document.get("host", ""),
            "path": document.get("path", ""),
            "cited_blocks": cited_blocks,
        },
    }
    if provider["label"] == "MiniMax Mock":
        answer = build_mock_ai_answer(question, profile, document, cited_blocks)
        if user_record and profile:
            user_record["profile"] = profile
            user_record["profileComplete"] = True
            all_users = user_record.pop("_all_users", None)
            if all_users:
                save_users(all_users)
        return {
            "answer": answer,
            "model": provider["model"],
            "provider": provider["label"],
            "billing": {
                "provider": provider["label"],
                "model": provider["model"],
                "promptTokens": 0,
                "completionTokens": 0,
                "totalTokens": 0,
                "providerCostUsd": 0,
                "markup": float(os.environ.get("AI_MARKUP", "1.35")),
                "usdToCny": round(get_usd_to_cny_rate()["rate"], 4),
                "chargedCny": 0,
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "user": public_user(user_record) if user_record else None,
        }
    body = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "temperature": 0.35,
        "max_tokens": int(os.environ.get("AI_MAX_TOKENS", "1200")),
    }
    req = Request(
        provider["url"],
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("APP_URL", "http://127.0.0.1:5173"),
            "X-Title": os.environ.get("APP_NAME", "IZANOFFER"),
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as res:
            data = json.loads(res.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise ValueError(f"{provider['label']} API Key 无效或已过期，请重新配置") from exc
        if exc.code == 402 and provider["label"] == "OpenRouter":
            raise ValueError("OpenRouter 账户 credits 不足，请到 OpenRouter 后台充值或降低 max_tokens 后再试。") from exc
        raise ValueError(f"{provider['label']} API 请求失败：HTTP {exc.code} {detail[:300]}") from exc
    answer = data["choices"][0]["message"]["content"].strip()
    billing = build_billing_record(provider, data)
    charged_user = None
    if user_record:
        charge_user(user_record, billing)
        charged_user = public_user(user_record)
    return {"answer": answer, "model": body["model"], "provider": provider["label"], "billing": billing, "user": charged_user}


def find_user(email):
    if not email:
        return None
    data = load_users()
    user = next((u for u in data.setdefault("users", []) if u.get("email") == email), None)
    if not user:
        return None
    ensure_billing_fields(user)
    user["_all_users"] = data
    return user


def build_billing_record(provider, response_data):
    usage = response_data.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or prompt_tokens + completion_tokens)
    if provider["label"] == "OpenRouter":
        pricing = get_model_pricing(provider["model"])
    elif provider["label"] == "MiniMax":
        pricing = {
            "promptUsdPer1M": float(os.environ.get("MINIMAX_PROMPT_USD_PER_1M", "0.12")),
            "completionUsdPer1M": float(os.environ.get("MINIMAX_COMPLETION_USD_PER_1M", "0.48")),
        }
    else:
        pricing = {
        "promptUsdPer1M": float(os.environ.get("OPENAI_PROMPT_USD_PER_1M", "2.5")),
        "completionUsdPer1M": float(os.environ.get("OPENAI_COMPLETION_USD_PER_1M", "10")),
        }
    provider_cost_usd = (
        prompt_tokens / 1_000_000 * pricing["promptUsdPer1M"] +
        completion_tokens / 1_000_000 * pricing["completionUsdPer1M"]
    )
    markup = float(os.environ.get("AI_MARKUP", "1.35"))
    exchange = get_usd_to_cny_rate()
    usd_to_cny = exchange["rate"]
    charged_cny = provider_cost_usd * usd_to_cny * markup
    if total_tokens and charged_cny < 0.01:
        charged_cny = 0.01
    return {
        "provider": provider["label"],
        "model": provider["model"],
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "totalTokens": total_tokens,
        "providerCostUsd": round(provider_cost_usd, 8),
        "markup": markup,
        "usdToCny": round(usd_to_cny, 4),
        "exchangeRateSource": exchange["source"],
        "chargedCny": round(charged_cny, 4),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def charge_user(user, billing):
    charge = float(billing.get("chargedCny", 0))
    user["balanceCny"] = round(float(user.get("balanceCny", 0)) - charge, 4)
    user.setdefault("usage", []).append(billing)
    user.pop("_all_users", None)
    data = load_users()
    for index, item in enumerate(data.setdefault("users", [])):
        if item.get("email") == user.get("email"):
            data["users"][index] = user
            break
    save_users(data)


def admin_usage_summary():
    data = load_users()
    users = data.get("users", [])
    exchange = get_usd_to_cny_rate()
    total_balance = 0.0
    total_spent = 0.0
    total_tokens = 0
    total_cost_usd = 0.0
    events = []
    for user in users:
        ensure_billing_fields(user)
        total_balance += float(user.get("balanceCny", 0))
        for item in user.get("usage", []):
            event = dict(item)
            event["email"] = user.get("email", "")
            events.append(event)
            if item.get("type") == "recharge":
                continue
            total_spent += float(item.get("chargedCny", 0))
            total_tokens += int(item.get("totalTokens", 0))
            total_cost_usd += float(item.get("providerCostUsd", 0))
    events.sort(key=lambda item: item.get("createdAt", ""), reverse=True)
    return {
        "users": [public_user(user) for user in users],
        "summary": {
            "userCount": len(users),
            "totalBalanceCny": round(total_balance, 4),
            "totalSpentCny": round(total_spent, 4),
            "totalTokens": total_tokens,
            "providerCostUsd": round(total_cost_usd, 6),
            "markup": float(os.environ.get("AI_MARKUP", "1.35")),
            "usdToCny": round(exchange["rate"], 4),
            "exchangeRateSource": exchange["source"],
            "exchangeRateUpdatedAt": exchange["updatedAt"],
            "monthlyLimitCny": float(os.environ.get("MONTHLY_SPEND_LIMIT_CNY", "200")),
        },
        "events": events[:100],
    }


def get_ai_provider():
    if os.environ.get("AI_MOCK_MODE", "").lower() in {"1", "true", "yes"}:
        return {
            "label": "MiniMax Mock",
            "api_key": "mock",
            "url": "",
            "model": "MiniMax-M2.5",
        }
    minimax_key = os.environ.get("MINIMAX_API_KEY", "")
    if minimax_key:
        return {
            "label": "MiniMax",
            "api_key": minimax_key,
            "url": os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1/chat/completions"),
            "model": os.environ.get("MINIMAX_MODEL", os.environ.get("AI_MODEL", "MiniMax-M2.5")),
        }
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        return {
            "label": "OpenRouter",
            "api_key": openrouter_key,
            "url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
            "model": os.environ.get("OPENROUTER_MODEL", os.environ.get("AI_MODEL", "minimax/minimax-m2.5")),
        }
    return {
        "label": "OpenAI",
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        "model": os.environ.get("OPENAI_MODEL", os.environ.get("AI_MODEL", "gpt-4o-mini")),
    }


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/config":
            provider = get_ai_provider()
            self.send_json(200, {
                "clerkPublishableKey": os.environ.get("CLERK_PUBLISHABLE_KEY", ""),
                "aiEnabled": bool(provider["api_key"]),
                "aiProvider": provider["label"],
                "aiModel": provider["model"],
                "usdToCny": round(get_usd_to_cny_rate()["rate"], 4),
                "mockAuth": True,
                "adminEmail": "451248901@qq.com"
            })
            return
        if self.path == "/api/trending":
            data_path = Path(__file__).with_name("trending.json")
            if data_path.exists():
                self.send_json(200, json.loads(data_path.read_text(encoding="utf-8")))
            else:
                self.send_json(200, {"questions": [], "links": []})
            return
        if self.path == "/api/models":
            try:
                models = fetch_openrouter_models()
                selected = select_featured_models(models)
                self.send_json(200, {"models": selected})
            except Exception as exc:
                self.send_json(400, {"error": str(exc), "models": []})
            return
        if self.path == "/api/admin/usage":
            self.send_json(200, admin_usage_summary())
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/extract":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                payload = json.loads(body.decode("utf-8"))
                data = fetch_readable(payload.get("url", ""))
                self.send_json(200, data)
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})
            return

        if self.path == "/api/ai-chat":
            try:
                payload = self.read_payload()
                self.send_json(200, call_ai_chat(payload))
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})
            return

        if self.path in {"/api/mock-auth/login", "/api/mock-auth/register", "/api/mock-auth/profile", "/api/mock-auth/recharge"}:
            self.handle_mock_auth()
            return

        self.send_error(404)

    def read_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_mock_auth(self):
        try:
            payload = self.read_payload()
            data = load_users()
            users = data.setdefault("users", [])
            email = normalize_text(payload.get("email", "")).lower()

            if self.path == "/api/mock-auth/register":
                if not email or "@" not in email:
                    raise ValueError("请输入有效邮箱")
                if len(payload.get("password", "")) < 6:
                    raise ValueError("密码至少 6 位")
                if any(u["email"] == email for u in users):
                    raise ValueError("这个邮箱已注册，请直接登录")
                user = {
                    "email": email,
                    "displayName": email.split("@")[0],
                    "passwordHash": password_hash(payload["password"]),
                    "role": "admin" if email == "451248901@qq.com" else "user",
                    "profile": {},
                    "profileComplete": False,
                    "balanceCny": 5.0,
                    "usage": [],
                }
                users.append(user)
                save_users(data)
                self.send_json(200, {"user": public_user(user)})
                return

            user = next((u for u in users if u["email"] == email), None)
            if not user:
                raise ValueError("账号不存在，请先注册")

            if self.path == "/api/mock-auth/login":
                if user["passwordHash"] != password_hash(payload.get("password", "")):
                    raise ValueError("密码不正确")
                self.send_json(200, {"user": public_user(user)})
                return

            if self.path == "/api/mock-auth/profile":
                if "displayName" in payload:
                    display_name = normalize_text(payload.get("displayName", ""))
                    if not display_name:
                        raise ValueError("显示名称不能为空")
                    user["displayName"] = display_name
                    save_users(data)
                    self.send_json(200, {"user": public_user(user)})
                    return
                user["profile"] = payload.get("profile", {})
                user["profileComplete"] = True
                save_users(data)
                self.send_json(200, {"user": public_user(user)})
                return

            if self.path == "/api/mock-auth/recharge":
                amount = float(payload.get("amount", 0))
                if amount not in {10.0, 30.0, 100.0}:
                    raise ValueError("请选择有效充值金额")
                ensure_billing_fields(user)
                user["balanceCny"] = round(float(user.get("balanceCny", 0)) + amount, 4)
                user.setdefault("usage", []).append({
                    "type": "recharge",
                    "amountCny": amount,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
                save_users(data)
                self.send_json(200, {"user": public_user(user)})
                return
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving IZANOFFER prototype on http://127.0.0.1:{port}/C3-prototype.html")
    server.serve_forever()
