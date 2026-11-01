"""Local speech engines, each a separate program managed by CyAI (like llama-server), so the application stays light.

- whisper.cpp (whisper-cli) turns a recording into text;
- Piper (piper.exe) and the voices installed in Windows (System.Speech) turn text into a WAV.
Nothing is sent over the network.
"""
import base64
from collections import deque
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time

from .connectors import spawn, stop_process
from .voice_audio import wav_bytes


def _hidden():
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


class WhisperCpp:
    def __init__(self, executable, model, threads=4, gpu=False):
        self.executable, self.model, self.threads, self.gpu = Path(executable), Path(model), int(threads), gpu

    def transcribe(self, pcm, language):
        if not self.executable.is_file():
            raise ValueError('Moteur whisper.cpp absent : installez-le dans Paramètres › Voix.')
        if not self.model.is_file():
            raise ValueError('Modèle Whisper absent : téléchargez-le dans Paramètres › Voix.')
        with tempfile.TemporaryDirectory(prefix='cyai-voice-') as folder:
            source, base = Path(folder) / 'dictee.wav', Path(folder) / 'texte'
            source.write_bytes(wav_bytes(pcm))
            args = [str(self.executable), '-m', str(self.model), '-f', str(source), '-l', language or 'auto',
                    '-t', str(self.threads), '-nt', '-np', '-otxt', '-of', str(base)] + ([] if self.gpu else ['-ng'])
            result = subprocess.run(args, cwd=str(self.executable.parent), capture_output=True, timeout=300, creationflags=_hidden())
            text_file = base.with_suffix('.txt')
            if result.returncode or not text_file.is_file():
                detail = (result.stderr or b'').decode('utf-8', 'replace').strip()[-800:]
                raise RuntimeError('whisper.cpp n’a pas transcrit l’enregistrement' + (' : ' + detail if detail else '.'))
            return text_file.read_text(encoding='utf-8', errors='replace').strip()


class _Process:
    """A synthesis program kept loaded between sentences, stopped after a while without use."""

    def __init__(self, args, cwd):
        self.proc = spawn(args, cwd)
        self.lines, self.logs = queue.Queue(), deque(maxlen=40)
        self.used = time.monotonic()
        threading.Thread(target=self._read, args=(self.proc.stdout, self.lines.put), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc.stderr, self.logs.append), daemon=True).start()

    @staticmethod
    def _read(stream, sink):
        for line in stream:
            sink(line.strip())

    def alive(self):
        return self.proc.poll() is None

    def ask(self, line, timeout):
        if not self.alive():
            raise RuntimeError('Le moteur de synthèse s’est arrêté : ' + ' | '.join(self.logs)[-600:])
        self.used = time.monotonic()
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()
        try:
            return self.lines.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise RuntimeError('Le moteur de synthèse ne répond pas : ' + ' | '.join(self.logs)[-600:])

    def close(self):
        if self.alive():
            stop_process(self.proc)
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if pipe:
                try: pipe.close()
                except OSError: pass


class Piper:
    def __init__(self, executable, model, speaker=None, speed=1.0, noise_scale=None, noise_w=None):
        self.executable, self.model = Path(executable), Path(model)
        self.speaker, self.speed = speaker, float(speed)
        self.noise_scale, self.noise_w = noise_scale, noise_w
        self.folder = Path(tempfile.mkdtemp(prefix='cyai-piper-'))
        self.process = None

    def synthesize(self, text):
        if not self.executable.is_file():
            raise ValueError('Moteur Piper absent : installez-le dans Paramètres › Voix.')
        if not self.process or not self.process.alive():
            args = [str(self.executable), '--model', str(self.model), '--output_dir', str(self.folder),
                    '--length_scale', '%.3f' % (1 / max(.5, min(2.0, self.speed)))]
            for flag, value in (('--noise_scale', self.noise_scale), ('--noise_w', self.noise_w)):
                if value is not None:
                    args += [flag, str(value)]
            if self.speaker not in (None, ''):
                args += ['--speaker', str(int(self.speaker))]
            self.process = _Process(args, str(self.executable.parent))
        before = set(self.folder.glob('*.wav'))
        # One line in, one WAV out: Piper prints the path of the file it wrote.
        answer = self.process.ask(' '.join(text.split()), 120)
        path = Path(answer) if answer.lower().endswith('.wav') else None
        if not path or not path.is_file():
            new = sorted(set(self.folder.glob('*.wav')) - before, key=lambda p: p.stat().st_mtime)
            if not new:
                raise RuntimeError('Piper n’a pas produit de son : ' + answer[:300])
            path = new[-1]
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return data

    def idle_for(self):
        return time.monotonic() - self.process.used if self.process else None

    def close(self):
        if self.process:
            self.process.close()
            self.process = None


WINDOWS_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($line -eq $null) { break }
  try {
    $r = $line | ConvertFrom-Json
    if ($r.op -eq 'voices') {
      $names = @($s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name + '|' + $_.VoiceInfo.Gender })
      [Console]::Out.WriteLine((ConvertTo-Json -Compress @{ ok = $true; voices = $names }))
      continue
    }
    if ($r.voice) { $s.SelectVoice([string]$r.voice) }
    $s.Rate = [int]$r.rate
    $s.SetOutputToWaveFile([string]$r.file, $format)
    $s.Speak([string]$r.text)
    $s.SetOutputToNull()
    [Console]::Out.WriteLine('{"ok":true}')
  } catch {
    $s.SetOutputToNull()
    [Console]::Out.WriteLine((ConvertTo-Json -Compress @{ ok = $false; error = $_.Exception.Message }))
  }
}
'''


class WindowsVoices:
    """The voices installed in Windows (Paramètres › Heure et langue › Voix). Nothing to download."""

    def __init__(self):
        self.process = None
        self.folder = Path(tempfile.mkdtemp(prefix='cyai-sapi-'))
        self.lock = threading.Lock()

    def _ask(self, request, timeout=60):
        with self.lock:
            if not self.process or not self.process.alive():
                encoded = base64.b64encode(WINDOWS_SCRIPT.encode('utf-16-le')).decode()
                self.process = _Process(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                         '-EncodedCommand', encoded], str(self.folder))
            # ASCII JSON: accents travel as \\u escapes, whatever the console code page.
            answer = json.loads(self.process.ask(json.dumps(request, ensure_ascii=True), timeout) or '{}')
        if not answer.get('ok'):
            raise RuntimeError('Voix Windows : ' + str(answer.get('error') or 'réponse vide'))
        return answer

    def voices(self):
        found = []
        for item in self._ask({'op': 'voices'}).get('voices') or []:
            name, culture, gender = (item.split('|') + ['', ''])[:3]
            found.append({'name': name, 'language': culture, 'gender': gender})
        return found

    def synthesize(self, text, voice='', speed=1.0):
        import math
        target = self.folder / ('%d.wav' % time.monotonic_ns())
        rate = max(-10, min(10, round(10 * math.log(max(.5, min(2.0, float(speed)))) / math.log(3))))
        self._ask({'text': ' '.join(text.split()), 'voice': voice, 'rate': rate, 'file': str(target)})
        data = target.read_bytes()
        target.unlink(missing_ok=True)
        return data

    def idle_for(self):
        return time.monotonic() - self.process.used if self.process else None

    def close(self):
        if self.process:
            self.process.close()
            self.process = None
