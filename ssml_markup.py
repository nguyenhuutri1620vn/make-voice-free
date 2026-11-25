"""Convert light inline markup into SSML for TTS engines.

Supported markup:
    *word*                      -> <emphasis level="strong">word</emphasis>
    [pause 300ms] / [pause 0.5s] -> <break time="300ms"/> / <break time="0.5s"/>
    [prosody rate=slow pitch=+2st]...[/prosody]
                                -> <prosody rate="slow" pitch="+2st">...</prosody>

Text is XML-escaped, so characters like & < > are safe in the output.
"""

import re
from xml.sax.saxutils import escape

_TOKEN_RE = re.compile(
    r"\*(?P<emph>[^*]+)\*"
    r"|\[pause\s+(?P<pause>\d+(?:\.\d+)?(?:ms|s))\]"
    r"|\[prosody(?P<attrs>(?:\s+[a-z]+=[^\s\]]+)*)\]"
    r"|\[/prosody\]"
)
_ATTR_RE = re.compile(r"([a-z]+)=([^\s\]]+)")
_ALLOWED_PROSODY = {"rate", "pitch", "volume"}


def to_ssml(text: str) -> str:
    """Return an SSML document body (wrapped in <speak>) for the marked-up text."""
    parts: list[str] = []
    open_prosody = 0
    pos = 0

    for match in _TOKEN_RE.finditer(text):
        parts.append(escape(text[pos:match.start()]))
        pos = match.end()

        if match.group("emph") is not None:
            parts.append(
                f'<emphasis level="strong">{escape(match.group("emph"))}</emphasis>'
            )
        elif match.group("pause") is not None:
            parts.append(f'<break time="{match.group("pause")}"/>')
        elif match.group("attrs") is not None:
            attrs = _ATTR_RE.findall(match.group("attrs"))
            if not attrs:
                raise ValueError("[prosody] needs at least one attribute, e.g. rate=slow")
            for name, _ in attrs:
                if name not in _ALLOWED_PROSODY:
                    raise ValueError(f"Unsupported prosody attribute: {name}")
            rendered = " ".join(f'{name}="{escape(value)}"' for name, value in attrs)
            parts.append(f"<prosody {rendered}>")
            open_prosody += 1
        else:  # [/prosody]
            if open_prosody == 0:
                raise ValueError("[/prosody] without a matching [prosody ...]")
            parts.append("</prosody>")
            open_prosody -= 1

    if open_prosody:
        raise ValueError("[prosody ...] was not closed with [/prosody]")

    parts.append(escape(text[pos:]))
    return "<speak>" + "".join(parts) + "</speak>"
