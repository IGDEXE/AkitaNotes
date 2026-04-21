#!/usr/bin/env python3
"""Exporta todas as postagens da seção Akitando para arquivos Markdown.

Uso:
    py scripts/export_akita_akitando.py
    py scripts/export_akita_akitando.py --out-dir data/akitando --delay 0.5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://akitaonrails.com"
INDEX_URL = f"{BASE_URL}/akitando/"
DEFAULT_OUT_DIR = Path("output") / "akitando"
USER_AGENT = "AkitaNotes Akitando Exporter/1.0 (+https://github.com/)"
POST_URL_RE = re.compile(r"^https://akitaonrails\.com/\d{4}/\d{2}/\d{2}/[^/]+/?$")
WHITESPACE_RE = re.compile(r"\s+")


def collapse_ws(value: str) -> str:
    return WHITESPACE_RE.sub(" ", unescape(value)).strip()


def normalize_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-") or "post"


def fetch_html(url: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        for encoding in ("utf-8", charset, "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")


class IndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: Dict[str, str] = {}
        self.current_href: Optional[str] = None
        self.current_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        href = attrs_map.get("href")
        if not href:
            return
        absolute_href = urljoin(BASE_URL, href)
        if POST_URL_RE.match(absolute_href):
            self.current_href = absolute_href.rstrip("/") + "/"
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self.current_href is None:
            return
        text = collapse_ws("".join(self.current_text))
        if "akitando" in text.lower():
            self.links.setdefault(self.current_href, text)
        self.current_href = None
        self.current_text = []


class PostParser(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "div",
        "section",
        "p",
        "ul",
        "ol",
        "pre",
        "blockquote",
        "table",
        "hr",
    }
    SKIP_TAGS = {
        "aside",
        "button",
        "footer",
        "form",
        "nav",
        "script",
        "style",
        "svg",
        "noscript",
    }

    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.title: Optional[str] = None
        self.date: Optional[str] = None
        self.slug = self._slug_from_url(source_url)
        self.article_depth = 0
        self.capture_title = False
        self.skip_h1 = False
        self.capture_heading_level: Optional[int] = None
        self.skip_depth = 0
        self.link_href: Optional[str] = None
        self.link_text_parts: List[str] = []
        self.list_stack: List[dict[str, int | str]] = []
        self.in_pre = False
        self.in_code = False
        self.current_line: List[str] = []
        self.body_parts: List[str] = []

    @staticmethod
    def _slug_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1] if path else "post"

    def _push_text(self, text: str) -> None:
        if not text:
            return
        if self.in_pre:
            self.current_line.append(text)
            return
        clean = collapse_ws(text)
        if not clean:
            return
        if self.current_line:
            previous = self.current_line[-1]
            if previous.endswith((" ", "\n", "(", "[", "/", "`")) or clean in {".", ",", ":", ";", "!", "?", ")"}:
                self.current_line.append(clean)
            else:
                self.current_line.append(" " + clean)
        else:
            self.current_line.append(clean)

    def _flush_line(self) -> None:
        if not self.current_line:
            return
        line = "".join(self.current_line).rstrip()
        if line:
            self.body_parts.append(line)
        self.current_line = []

    def _blank_line(self) -> None:
        self._flush_line()
        if self.body_parts and self.body_parts[-1] != "":
            self.body_parts.append("")

    def _append_block(self, value: str) -> None:
        self._blank_line()
        self.body_parts.append(value.rstrip())
        self.body_parts.append("")

    def _current_list_prefix(self) -> str:
        if not self.list_stack:
            return "- "
        item = self.list_stack[-1]
        indent = "  " * (len(self.list_stack) - 1)
        if item["type"] == "ol":
            number = int(item["counter"]) + 1
            item["counter"] = number
            return f"{indent}{number}. "
        return f"{indent}- "

    def markdown_body(self) -> str:
        self._flush_line()
        while self.body_parts and self.body_parts[-1] == "":
            self.body_parts.pop()
        return "\n".join(self.body_parts).strip()

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attrs_map = dict(attrs)

        if tag == "meta":
            prop = attrs_map.get("property") or attrs_map.get("name")
            content = attrs_map.get("content")
            if prop == "og:title" and content and not self.title:
                self.title = collapse_ws(content).replace(" – AkitaOnRails.com", "")
            return

        if tag == "time" and not self.date:
            datetime_value = attrs_map.get("datetime")
            if datetime_value:
                self.date = datetime_value[:10]

        if self.article_depth == 0:
            if tag == "article":
                self.article_depth = 1
            if tag == "h1" and not self.title:
                self.capture_title = True
            return

        if tag == "article":
            self.article_depth += 1
            return

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth > 0:
            return

        if tag == "a":
            href = attrs_map.get("href")
            self.link_href = urljoin(self.source_url, href) if href else None
            self.link_text_parts = []
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            if level == 1:
                self.skip_h1 = True
                self.capture_heading_level = None
                return
            self._blank_line()
            self.capture_heading_level = level
            self.current_line.append("#" * level + " ")
            return

        if tag == "br":
            self._flush_line()
            return

        if tag == "hr":
            self._append_block("---")
            return

        if tag == "blockquote":
            self._blank_line()
            self.current_line.append("> ")
            return

        if tag == "pre":
            self._blank_line()
            self.in_pre = True
            self.current_line.append("```")
            self._flush_line()
            return

        if tag == "code":
            if self.in_pre:
                return
            self.in_code = True
            self.current_line.append("`")
            return

        if tag in {"ul", "ol"}:
            self._blank_line()
            self.list_stack.append({"type": tag, "counter": 0})
            return

        if tag == "li":
            self._flush_line()
            self.current_line.append(self._current_list_prefix())
            return

        if tag in self.BLOCK_TAGS:
            self._blank_line()

    def handle_data(self, data: str) -> None:
        if self.capture_title and not self.title:
            title = collapse_ws(data)
            if title:
                self.title = title
            return

        if self.article_depth == 0 or self.skip_depth > 0:
            return

        if self.skip_h1:
            return

        if self.link_href is not None:
            self.link_text_parts.append(data)
            return

        self._push_text(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture_title and tag == "h1":
            self.capture_title = False
            return

        if self.article_depth == 0:
            return

        if tag == "article":
            self.article_depth -= 1
            if self.article_depth == 0:
                self._flush_line()
            return

        if self.skip_depth > 0:
            if tag in self.SKIP_TAGS:
                self.skip_depth -= 1
            return

        if tag == "a" and self.link_href is not None:
            link_text = collapse_ws("".join(self.link_text_parts)) or self.link_href
            self._push_text(f"[{link_text}]({self.link_href})")
            self.link_href = None
            self.link_text_parts = []
            return

        if tag == "h1" and self.skip_h1:
            self.skip_h1 = False
            return

        if tag == "code" and self.in_code and not self.in_pre:
            self.current_line.append("`")
            self.in_code = False
            return

        if tag == "pre" and self.in_pre:
            self._flush_line()
            self.body_parts.append("```")
            self.body_parts.append("")
            self.current_line = []
            self.in_pre = False
            return

        if tag in {"h2", "h3", "h4", "h5", "h6"} and self.capture_heading_level is not None:
            self._blank_line()
            self.capture_heading_level = None
            return

        if tag == "li":
            self._flush_line()
            return

        if tag in {"ul", "ol"}:
            self._flush_line()
            if self.list_stack:
                self.list_stack.pop()
            self._blank_line()
            return

        if tag in self.BLOCK_TAGS:
            self._blank_line()


@dataclass
class PostRecord:
    title: str
    date: str
    source_url: str
    filename: str


def discover_posts(index_html: str) -> List[tuple[str, str]]:
    parser = IndexParser()
    parser.feed(index_html)
    posts = sorted(parser.links.items(), key=lambda item: item[0])
    return posts


def parse_post(html: str, url: str) -> tuple[str, str, str]:
    parser = PostParser(url)
    parser.feed(html)
    title = parser.title or parser.slug.replace("-", " ").title()
    date = parser.date or f"{urlparse(url).path.split('/')[1]}-{urlparse(url).path.split('/')[2]}-{urlparse(url).path.split('/')[3]}"
    body = parser.markdown_body()
    if not body:
        raise ValueError(f"Nao foi possivel extrair o corpo do artigo: {url}")
    return title, date, body


def build_markdown(title: str, date: str, source_url: str, body: str) -> str:
    frontmatter = [
        "---",
        f'title: "{title.replace(chr(34), r"\"")}"',
        f"date: {date}",
        f"source_url: {source_url}",
        "source_site: AkitaOnRails",
        "series: Akitando",
        "---",
        "",
        f"# {title}",
        "",
    ]
    return "\n".join(frontmatter) + body.strip() + "\n"


def export_posts(out_dir: Path, delay: float, overwrite: bool, max_posts: Optional[int]) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    index_html = fetch_html(INDEX_URL)
    discovered_posts = discover_posts(index_html)
    if max_posts is not None:
        discovered_posts = discovered_posts[:max_posts]

    if not discovered_posts:
        raise RuntimeError("Nenhuma postagem da secao Akitando foi encontrada.")

    manifest: List[PostRecord] = []
    total = len(discovered_posts)

    for idx, (url, _) in enumerate(discovered_posts, start=1):
        print(f"[{idx}/{total}] Baixando {url}")
        try:
            html = fetch_html(url)
            title, date, body = parse_post(html, url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            print(f"  ERRO: {exc}", file=sys.stderr)
            continue

        filename = f"{date}-{normalize_filename(urlparse(url).path.rstrip('/').split('/')[-1])}.md"
        target = out_dir / filename
        if target.exists() and not overwrite:
            print(f"  Pulando arquivo existente: {target}")
        else:
            target.write_text(build_markdown(title, date, url, body), encoding="utf-8")
            print(f"  Salvo em {target}")

        manifest.append(
            PostRecord(
                title=title,
                date=date,
                source_url=url,
                filename=filename,
            )
        )
        if delay > 0 and idx < total:
            time.sleep(delay)

    manifest_path = out_dir / "manifest.json"
    manifest_payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "index_url": INDEX_URL,
        "count": len(manifest),
        "posts": [record.__dict__ for record in manifest],
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Manifesto salvo em {manifest_path}")
    return len(manifest)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exporta os posts da secao Akitando para arquivos Markdown.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Diretorio de saida. Padrao: {DEFAULT_OUT_DIR}",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Intervalo entre requisicoes, em segundos. Padrao: 0.3",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve arquivos .md ja existentes.",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=None,
        help="Limita a quantidade de posts processados, util para testes.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        total = export_posts(
            out_dir=Path(args.out_dir),
            delay=args.delay,
            overwrite=args.overwrite,
            max_posts=args.max_posts,
        )
    except Exception as exc:  # noqa: BLE001 - CLI simples com mensagem direta.
        print(f"Falha ao exportar posts: {exc}", file=sys.stderr)
        return 1

    print(f"Concluido: {total} posts processados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
