"""What a voice reads of an answer: the words meant for the user, never the machinery around them.

An answer arrives in pieces while the agent writes it. The segmenter keeps what can be said aloud (sentences),
drops what cannot (code, tables, links, paths, the continuity block CyAI appends, method proposals) and hands
back segments as soon as a sentence is complete, so the voice can start before the answer ends.
"""
import json
import re

OPEN, CLOSE = '<cyai-continuity>', '</cyai-continuity>'
PROPOSAL = re.compile(r'^#{1,6}\s*Proposition d[’\']amélioration', re.I)
PORT_HEADING = re.compile(r'^#{1,6}\s*(Sortie|Entrée)\s*:', re.I)
# A sentence ends on . ! ? … followed by a space; "1." or "2.0." (a number) is not an end.
SENTENCE_END = re.compile(r'(?<!\d)[.!?…]+["»”)\]]?(?=\s)')
# Whisper, on silence or noise, writes subtitles credits or sound tags: they are not what you said.
HALLUCINATIONS = re.compile(r'^\W*(sous-titr|merci d[’\']avoir regardé|abonnez-vous|thanks? for watching|amara\.org|\[.*\]|\(.*\))', re.I)


def _keep_end(match):
    """A link or a path is not read, but the punctuation that ends the sentence after it stays."""
    return re.search(r'[.,;:!?…]*$', match.group(0)).group(0)


def clean_line(line):
    """One line of Markdown as it should be heard, or '' when nothing of it should be."""
    text = line.strip()
    if not text or text.startswith('|') or re.fullmatch(r'[-=*_~`\s]{3,}', text):
        return ''
    heading = bool(re.match(r'#{1,6}\s', text))
    item = bool(re.match(r'([-*+]|\d{1,3}[.)])\s', text))
    text = re.sub(r'^(#{1,6}|>+|[-*+]|\d{1,3}[.)])\s+', '', text)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+|www\.\S+', _keep_end, text)
    text = re.sub(r'`([^`]{1,40})`', lambda m: '' if re.search(r'[\\/]', m.group(1)) else m.group(1), text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\b[A-Za-z]:\\\S*|(?<![\w])(?:\.{0,2}/[\w.@-]+){2,}\S*', _keep_end, text)
    text = re.sub(r'<[^>]{1,80}>', '', text)
    text = re.sub(r'(\*\*|__|~~)', '', text)
    text = re.sub(r'(?<!\w)[*_](\S[^*_]*?)[*_](?!\w)', r'\1', text)
    text = re.sub(r'\s+([.,;!?…])', r'\1', re.sub(r'\s+', ' ', text)).strip(' -–—:;,')
    if text and (heading or item) and not re.search(r'[.!?…:;,]$', text):
        text += '.'
    return text


class Segmenter:
    """Feed it the answer as it streams; it returns the sentences ready to be spoken."""

    def __init__(self, limit=0, first=24, target=90, longest=320):
        self.buffer = ''       # raw text of the line being written
        self.pending = ''      # clean text not spoken yet
        self.code = self.continuity = self.dropped = False
        self.limit, self.first, self.target, self.longest = limit, first, target, longest
        self.spoken, self.truncated = 0, False

    def feed(self, text):
        self.buffer += text
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self._line(line)
            self.pending += '\n'
        # Say the finished sentences of an unfinished line, unless that line may be code, a table or a tag.
        head = self.buffer.lstrip()
        if head and not (self.code or self.continuity or self.dropped) and head[0] not in '`|#<>![~' and OPEN[:2] not in head:
            ends = list(SENTENCE_END.finditer(self.buffer))
            if ends:
                cut = ends[-1].end()
                self.pending += clean_line(self.buffer[:cut]) + ' '
                self.buffer = self.buffer[cut:]
        return self._segments(False)

    def flush(self):
        if self.buffer:
            self._line(self.buffer)
            self.buffer = ''
        return self._segments(True)

    def _line(self, line):
        if self.continuity:
            if CLOSE not in line:
                return
            self.continuity, line = False, line.split(CLOSE, 1)[1]
        if OPEN in line:
            before, after = line.split(OPEN, 1)
            self._line(before)
            self.continuity = True
            if CLOSE in after:
                self._line(after)
            return
        stripped = line.strip()
        if stripped.startswith(('```', '~~~')):
            self.code = not self.code
            return
        if self.code or self.dropped:
            return
        if PROPOSAL.match(stripped):
            self.dropped = True  # A proposal to improve the method comes after the answer: not for the ear.
            return
        if PORT_HEADING.match(stripped):
            return
        cleaned = clean_line(line)
        if cleaned:
            self.pending += cleaned + ' '

    def idle(self):
        """No new text for a while (the agent is using a tool): say the finished sentences already there."""
        return self._segments(False, idle=True)

    def _segments(self, final, idle=False):
        out = []
        while not self.truncated:
            text = self.pending
            ends = sorted({m.end() for m in SENTENCE_END.finditer(text)} | {i + 1 for i, c in enumerate(text) if c == '\n'})
            ends = [e for e in ends if re.search(r'\w', text[:e])]
            wanted = self.first if not self.spoken and not out else self.target
            # Short sentences are said together; the first one goes out quickly so the voice starts early.
            cut = next((e for e in ends if len(text[:e].strip()) >= wanted), None)
            if cut is None and (final or idle) and ends:
                cut = ends[-1]
            if cut is None and final and re.search(r'\w', text):
                cut = len(text)
            if (cut is None and len(text.strip()) > self.longest) or (cut and len(text[:cut].strip()) > self.longest):
                space = text.rfind(', ', 0, self.longest)
                cut = space + 1 if space > self.longest // 3 else (text.rfind(' ', 0, self.longest) + 1 or self.longest)
            if cut is None:
                break
            segment = re.sub(r'\s+', ' ', text[:cut]).strip()
            self.pending = text[cut:]
            if not re.search(r'\w', segment):
                continue
            if self.limit and self.spoken + len(segment) > self.limit:
                self.truncated = True
                break
            self.spoken += len(segment)
            out.append(segment)
        return out


def speakable(text, limit=0):
    """The whole of a finished answer, as segments."""
    segmenter = Segmenter(limit)
    return segmenter.feed(text) + segmenter.flush(), segmenter.truncated


def planning_reply(text):
    """An orchestrator answer is JSON: only its reply is meant to be heard."""
    raw = text.replace(OPEN, '\n' + OPEN)
    raw = re.sub(r'<cyai-continuity>[\s\S]*?(</cyai-continuity>|$)', '', raw).strip()
    try:
        value = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', raw))
    except ValueError:
        return raw, False
    if isinstance(value, dict) and isinstance(value.get('reply'), str):
        return value['reply'], bool(value.get('plan'))
    return raw, False


def usable_transcript(text):
    """What was heard, or '' when it is only noise that Whisper turned into words."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    if not re.search(r'\w', text) or HALLUCINATIONS.match(text):
        return ''
    return text
