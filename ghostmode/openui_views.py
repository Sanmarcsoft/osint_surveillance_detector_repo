"""OpenUI Lang view builders (osint #45).

The nest wrapper renders boards without iframes: the server emits OpenUI
Lang documents (compact, line-oriented — see sanmarcsoft/openui) and the
self-hosted @openuidev/browser-bundle renders them client-side with the
stock openuiChatLibrary components.

Component signatures used (positional args follow the Zod key order):
  TextContent(text, size?)            size: small|default|large|small-heavy|large-heavy
  Tag(text, icon?, size?, variant?)   variant: neutral|info|success|warning|danger
  Col(label, data, type?)             data: array of strings or component refs
  Table([cols])
  Card([children], variant?)          variant: card|sunk|clear
  Stack([children], direction?, gap?)
"""
from __future__ import annotations

import json


def _s(value) -> str:
    """Quote a value as an OpenUI Lang string literal (JSON string rules)."""
    return json.dumps(str(value))


_BADGE_VARIANT = {"up": "success", "warn": "warning", "down": "danger", "na": "neutral"}


def build_ops_lang(results: list[dict]) -> str:
    """Render infrastructure probe results as an OpenUI Lang document.

    ``results`` is the output of ops_dashboard's probe pass — each row has
    label/host/code/latency_ms/ssl_days plus the #39 desired-code fields.
    """
    from ghostmode.ops_dashboard import status_class

    lines: list[str] = []
    assets, hosts = [], []
    status_refs, latency_refs, tls_refs = [], [], []
    up = 0

    for i, r in enumerate(results):
        assets.append(_s(r["label"]))
        hosts.append(_s(r["host"]))

        if r.get("kind") == "http":
            cls = status_class(r["code"], r["expect"], r["reachable"])
        else:
            cls = "up" if r["reachable"] else "down"
        if cls == "up":
            up += 1
        ref = f"st{i}"
        lines.append(f"{ref} = Tag({_s(r['code'] or 'DOWN')}, \"\", \"sm\", \"{_BADGE_VARIANT[cls]}\")")
        status_refs.append(ref)

        if not r["reachable"]:
            lat_txt, lat_cls = "—", "na"
        elif r.get("is_self") or r["latency_ms"] is None:
            lat_txt, lat_cls = "live", "up"
        else:
            lat = r["latency_ms"]
            lat_txt = f"{lat} ms"
            lat_cls = "up" if lat < 800 else "warn" if lat < 2000 else "down"
        ref = f"lt{i}"
        lines.append(f"{ref} = Tag({_s(lat_txt)}, \"\", \"sm\", \"{_BADGE_VARIANT[lat_cls]}\")")
        latency_refs.append(ref)

        days = r["ssl_days"]
        if r.get("tls_na"):
            tls_txt, tls_cls = "n/a", "na"
        elif days is None:
            tls_txt, tls_cls = "—", "down"
        else:
            tls_txt = f"{days}d"
            tls_cls = "up" if days > 21 else "warn" if days > 7 else "down"
        ref = f"tl{i}"
        lines.append(f"{ref} = Tag({_s(tls_txt)}, \"\", \"sm\", \"{_BADGE_VARIANT[tls_cls]}\")")
        tls_refs.append(ref)

    total = len(results)
    summary_variant = "success" if total and up == total else "warning" if up else "danger"

    # Published chat-library catalog has no Stack and requires a Card root
    # (verified against the real parser via the render harness, 2026-06-04).
    doc = [
        "root = Card([hdr, sumtag, tbl])",
        f"hdr = CardHeader(\"Infrastructure\", {_s('Health, latency & TLS for thephenom.app assets')})",
        f'sumtag = Tag({_s(f"{up}/{total} desired")}, "", "md", "{summary_variant}")',
        "tbl = Table([c1, c2, c3, c4, c5])",
        f"c1 = Col(\"Asset\", [{', '.join(assets)}])",
        f"c2 = Col(\"Host\", [{', '.join(hosts)}])",
        f"c3 = Col(\"Status\", [{', '.join(status_refs)}])",
        f"c4 = Col(\"Latency\", [{', '.join(latency_refs)}])",
        f"c5 = Col(\"TLS\", [{', '.join(tls_refs)}])",
    ]
    return "\n".join(doc + lines) + "\n"
