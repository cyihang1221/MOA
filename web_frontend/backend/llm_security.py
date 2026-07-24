"""用户自备 LLM API 的校验与脱敏（防 SSRF、防 Key 泄露到日志/错误）。"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

# 错误/日志中常见的密钥形态
_SECRET_RE = re.compile(
    r"(?i)(?:sk-|api[_-]?key\s*[:=]\s*|bearer\s+|token\s*[:=]\s*)([A-Za-z0-9_\-.]{8,})"
)
_LONG_TOKEN_RE = re.compile(r"\b([A-Za-z0-9_\-]{32,})\b")

# 已知公网 OpenAI 兼容端点：跳过 DNS/私网解析限制
_TRUSTED_LLM_HOSTS = frozenset(
    {
        "dashscope.aliyuncs.com",
        "api.deepseek.com",
        "api.openai.com",
        "api.siliconflow.cn",
        "api.moonshot.cn",
        "open.bigmodel.cn",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
    }
)


def redact_secrets(text: str) -> str:
    """从异常文案中抹掉可能的 API Key。"""
    if not text:
        return ""
    out = _SECRET_RE.sub(lambda m: m.group(0)[: max(3, len(m.group(0)) - len(m.group(1)))] + "***", text)
    # 二次：超长 token 片段
    out = _LONG_TOKEN_RE.sub(lambda m: (m.group(1)[:4] + "…" + m.group(1)[-4:]) if len(m.group(1)) >= 32 else m.group(1), out)
    return out


def mask_api_key(key: str | None) -> str:
    raw = (key or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "***"
    return f"{raw[:4]}…{raw[-4:]}"


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_llm_base_url(base_url: str | None, *, allow_empty: bool = True) -> str | None:
    """校验用户自定义 Base URL，阻止内网/元数据 SSRF。

    返回规范化 URL（无尾斜杠）；空且允许时返回 None。
    """
    raw = (base_url or "").strip()
    if not raw:
        if allow_empty:
            return None
        raise ValueError("请填写 Base URL")

    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Base URL 仅支持 http/https")
    if not parsed.hostname:
        raise ValueError("Base URL 无效：缺少主机名")
    if parsed.username or parsed.password:
        raise ValueError("Base URL 不应包含用户名/密码，请把密钥填到 API Key")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("非本机地址请使用 https://")

    host = parsed.hostname.lower().rstrip(".")
    # 阻断云元数据常见主机名
    if host in {"metadata.google.internal", "metadata", "169.254.169.254"}:
        raise ValueError("禁止访问云元数据地址")

    # 本机 Ollama 等：仅允许 localhost / 127.0.0.1
    if host in {"localhost", "127.0.0.1"}:
        return raw.rstrip("/")

    # 直接写 IP
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise ValueError("禁止使用内网/回环 IP 作为 LLM Base URL")
    except ValueError as exc:
        if "禁止" in str(exc):
            raise
        # 不是 IP，继续按域名处理
        pass

    if host not in _TRUSTED_LLM_HOSTS:
        # 解析 DNS，拒绝落到私网
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise ValueError(f"无法解析 Base URL 主机名：{host}") from exc
        for info in infos:
            sockaddr = info[4]
            try:
                ip = ipaddress.ip_address(sockaddr[0])
            except ValueError:
                continue
            if _is_blocked_ip(ip):
                raise ValueError(f"主机 {host} 解析到内网地址，已拒绝（防 SSRF）")

    # 规范化：去掉末尾 /
    cleaned = raw.rstrip("/")
    return cleaned


def assert_safe_llm_override(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> tuple[str | None, str | None]:
    """用于 chat/probe：规范化并校验用户覆盖项。"""
    key = (api_key or "").strip() or None
    if key and len(key) > 512:
        raise ValueError("API Key 过长")
    if key and any(ch in key for ch in ("\n", "\r", "\x00")):
        raise ValueError("API Key 含非法字符")
    url = validate_llm_base_url(base_url, allow_empty=True)
    if key and not url:
        # 有自定义 key 但无 URL 时，允许走服务端默认 base（由 WebLLMClient 合并）
        pass
    return key, url


__all__ = [
    "redact_secrets",
    "mask_api_key",
    "validate_llm_base_url",
    "assert_safe_llm_override",
]
