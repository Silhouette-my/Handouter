"""Portable, offline HTML notes with embedded slide images and native MathML."""

from __future__ import annotations

import base64
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


STYLE = """
body{font-family:system-ui,sans-serif;line-height:1.8;color:#243044;background:#f5f7fa;margin:0}
main{max-width:920px;margin:30px auto;padding:36px;background:white;border-radius:12px}
h1,h2,h3{line-height:1.35;color:#152844}h2{border-bottom:1px solid #dde3ec;padding-bottom:12px}
img{display:block;max-width:100%;height:auto;margin:20px auto}pre{overflow:auto;padding:16px;background:#f1f4f8}
code{font-family:ui-monospace,monospace}table{border-collapse:collapse;display:block;overflow:auto}
th,td{border:1px solid #dce2eb;padding:8px 12px}blockquote{margin:20px 0;padding:12px 20px;border-left:5px solid #d49b21;background:#fff8e5}
details{margin:14px 0;padding:10px 16px;background:#f1f4f8;border-radius:6px}summary{cursor:pointer;font-weight:600}
.math.block{overflow-x:auto;padding:12px 0}math[display=block]{margin:12px 0}a{color:#2263ad}
@media(max-width:600px){main{margin:0;padding:20px;border-radius:0}}
@media print{body{background:white}main{margin:0;padding:0}details{break-inside:avoid}}
"""


class SafeHTML(HTMLParser):
    TAGS = set("p br hr h1 h2 h3 h4 h5 h6 ul ol li strong em s del blockquote pre code table thead tbody tr th td details summary div span a img math mrow mi mn mo mtext mspace ms mfrac msqrt mroot mstyle merror mpadded mphantom mfenced menclose msub msup msubsup munder mover munderover mmultiscripts mprescripts none mtable mtr mtd mlabeledtr semantics".split())
    ATTRS = set("class display xmlns mathvariant stretchy fence separator accent accentunder columnalign rowalign columnspacing rowspacing columnspan rowspan linethickness notation width height depth lspace rspace scriptlevel displaystyle open close separators encoding start".split())

    def __init__(self, note: Path, root: Path):
        super().__init__(convert_charrefs=True)
        self.note, self.root = note, root
        self.parts: list[str] = []

    def image(self, src: str) -> str:
        if urlsplit(src).scheme or src.startswith(("//", "\\")):
            raise ValueError("HTML 导出仅接受工作区内本地图片，不下载外部图片")
        path = (self.note.parent / unquote(src)).resolve(strict=True)
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("图片必须位于讲次文件夹内")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("单张图片超过 20 MiB，无法导出")
        data = path.read_bytes()
        mime = None
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        elif data.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        elif data.startswith((b'GIF87a', b'GIF89a')):
            mime = 'image/gif'
        elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            mime = 'image/webp'
        if mime is None:
            raise ValueError("HTML 图片仅支持 PNG/JPEG/GIF/WebP")
        return f"data:{mime};base64," + base64.b64encode(data).decode('ascii')

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            return
        clean = []
        for key, value in attrs:
            value = value or ''
            if tag == 'img' and key == 'src':
                clean.append(('src', self.image(value)))
            elif tag == 'img' and key == 'alt':
                clean.append((key, value))
            elif tag == 'a' and key == 'href':
                if value.startswith('#') or urlsplit(value).scheme in {'https', 'http', 'mailto'}:
                    clean.append((key, value))
            elif key in self.ATTRS and not (tag == 'details' and key == 'open'):
                clean.append((key, value))
        self.parts.append('<' + tag + ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in clean) + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {'img', 'br', 'hr'}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.TAGS and tag not in {'img', 'br', 'hr'}:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(escape(data))


def render_note(note: Path, root: Path) -> str:
    try:
        from markdown_it import MarkdownIt
        from mdit_py_plugins.dollarmath import dollarmath_plugin
        from latex2mathml.converter import convert
    except ImportError as exc:
        raise RuntimeError('HTML 导出依赖未安装，请重新运行 setup-handouter 安装脚本') from exc

    def math_renderer(content, options):
        try:
            return convert(content, display='block' if options.get('display_mode') else 'inline')
        except Exception as exc:
            raise ValueError(f'公式无法转换，请检查 LaTeX：{content[:100]}') from exc

    md = MarkdownIt('commonmark', {'html': True}).enable('table').enable('strikethrough')
    md.use(dollarmath_plugin, renderer=math_renderer)
    parser = SafeHTML(note, root)
    rendered = md.render(note.read_text(encoding='utf-8-sig'))
    rendered = rendered.replace('<p>[!IMPORTANT]', '<p><strong>重点提醒</strong>')
    parser.feed(rendered)
    parser.close()
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>{escape(note.stem)}</title><style>{STYLE}</style></head><body><main>'
            + ''.join(parser.parts) + '</main></body></html>')


def export_html(source: str | Path) -> list[Path]:
    """Export a note or all notes in a lecture folder, never overwriting files."""
    source = Path(source).expanduser().resolve(strict=True)
    if source.is_dir():
        root = source
        notes = sorted((root / 'notes').glob('*.md'))
    else:
        if source.suffix.lower() != '.md':
            raise ValueError('请选择 Markdown 文件或讲次文件夹')
        notes = [source]
        root = source.parent.parent if source.parent.name == 'notes' else source.parent
    if not notes:
        raise ValueError('notes 文件夹内没有 Markdown；请先保存 AI 返回的讲义')
    documents = []
    for note in notes:
        if note.is_symlink() or not note.resolve().is_relative_to(root):
            raise ValueError('讲义不能通过符号链接越出工作区')
        documents.append((note, render_note(note, root)))
    outputs = []
    for note, content in documents:
        index = 0
        while True:
            target = note.with_suffix('.html') if index == 0 else note.with_name(f'{note.stem}-{index:03d}.html')
            try:
                with target.open('x', encoding='utf-8') as handle:
                    handle.write(content)
                outputs.append(target)
                break
            except FileExistsError:
                index += 1
    return outputs


def export_agent_html(workspace, result) -> dict:
    """Only export this successful Agent run's outputs; report partial delivery."""
    if not result.validation_ok or result.returncode != 0:
        return {'status': 'skipped', 'outputs': {}, 'errors': []}
    outputs, errors = {}, []
    root = Path(workspace).resolve()
    for mode, relative in result.outputs.items():
        try:
            note = root / relative
            if not note.resolve().is_relative_to(root / 'notes'):
                raise ValueError('输出必须位于 notes 文件夹内')
            outputs[mode] = str(export_html(note)[0])
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f'{mode}: {exc}')
    return {'status': 'failed' if errors else 'ready', 'outputs': outputs, 'errors': errors}
