"""Microphone and speaker through the Windows multimedia API (winmm), with no extra dependency.

The audio stays in this process: it is captured into memory, handed to a local recogniser, and never stored.
Devices are chosen by name, because their numbers change when a device is plugged in or out; a device that has
disappeared is an error, never a silent switch to another microphone.
"""
import array
from collections import deque
import ctypes
import io
import math
import threading
import time
import wave

RATE = 16000  # What Whisper expects: 16 kHz, mono, 16 bits.
WAVE_MAPPER = 0xFFFFFFFF
WHDR_DONE = 1

if hasattr(ctypes, 'WinDLL'):
    from ctypes import wintypes as wt

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [('wFormatTag', wt.WORD), ('nChannels', wt.WORD), ('nSamplesPerSec', wt.DWORD),
                    ('nAvgBytesPerSec', wt.DWORD), ('nBlockAlign', wt.WORD), ('wBitsPerSample', wt.WORD), ('cbSize', wt.WORD)]

    class WAVEHDR(ctypes.Structure):
        _fields_ = [('lpData', ctypes.c_void_p), ('dwBufferLength', wt.DWORD), ('dwBytesRecorded', wt.DWORD),
                    ('dwUser', ctypes.c_size_t), ('dwFlags', wt.DWORD), ('dwLoops', wt.DWORD),
                    ('lpNext', ctypes.c_void_p), ('reserved', ctypes.c_size_t)]

    class WAVEINCAPSW(ctypes.Structure):
        _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', ctypes.c_uint), ('szPname', ctypes.c_wchar * 32),
                    ('dwFormats', wt.DWORD), ('wChannels', wt.WORD), ('wReserved1', wt.WORD)]

    class WAVEOUTCAPSW(ctypes.Structure):
        _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', ctypes.c_uint), ('szPname', ctypes.c_wchar * 32),
                    ('dwFormats', wt.DWORD), ('wChannels', wt.WORD), ('wReserved1', wt.WORD), ('dwSupport', wt.DWORD)]


def _winmm():
    if not hasattr(ctypes, 'WinDLL'):
        raise OSError('Le son est pris en charge sous Windows uniquement.')
    lib = ctypes.WinDLL('winmm')
    handle, header = ctypes.c_void_p, ctypes.POINTER(WAVEHDR)
    for prefix in ('waveIn', 'waveOut'):
        getattr(lib, prefix + 'Open').argtypes = [ctypes.POINTER(handle), ctypes.c_uint, ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
        for name in ('PrepareHeader', 'UnprepareHeader'):
            getattr(lib, prefix + name).argtypes = [handle, header, ctypes.c_uint]
        for name in ('Reset', 'Close'):
            getattr(lib, prefix + name).argtypes = [handle]
        getattr(lib, prefix + 'GetErrorTextW').argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
    lib.waveInAddBuffer.argtypes = [handle, header, ctypes.c_uint]
    lib.waveInStart.argtypes = [handle]
    lib.waveOutWrite.argtypes = [handle, header, ctypes.c_uint]
    lib.waveInGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(WAVEINCAPSW), ctypes.c_uint]
    lib.waveOutGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(WAVEOUTCAPSW), ctypes.c_uint]
    return lib


def _check(lib, prefix, code, what):
    if code:
        text = ctypes.create_unicode_buffer(256)
        getattr(lib, prefix + 'GetErrorTextW')(code, text, 256)
        raise OSError(what + ' : ' + (text.value or 'erreur ' + str(code)))


def _format(rate, channels=1, bits=16):
    block = channels * bits // 8
    return WAVEFORMATEX(1, channels, rate, rate * block, block, bits, 0)


def level(pcm):
    """Loudness of 16-bit samples, from 0 (silence) to 1 (full scale), on a scale close to what the ear hears."""
    samples = array.array('h', pcm[:len(pcm) // 2 * 2])
    if not samples:
        return 0.0
    rms = math.sqrt(sum(s * s for s in samples[::4]) / len(samples[::4]))
    return max(0.0, min(1.0, (20 * math.log10(rms / 32768) + 60) / 60)) if rms > 0 else 0.0


def wav_bytes(pcm, rate=RATE, channels=1):
    output = io.BytesIO()
    with wave.open(output, 'wb') as file:
        file.setnchannels(channels)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(pcm)
    return output.getvalue()


def read_wav(data):
    with wave.open(io.BytesIO(data), 'rb') as file:
        if file.getsampwidth() != 2:
            raise ValueError('Seul le son 16 bits est pris en charge.')
        return file.readframes(file.getnframes()), file.getframerate(), file.getnchannels()


def scale(pcm, volume):
    if volume >= 100:
        return pcm
    samples = array.array('h', pcm[:len(pcm) // 2 * 2])
    factor = max(0, volume) / 100
    return array.array('h', (int(s * factor) for s in samples)).tobytes()


class Capture:
    """An open microphone. Chunks are handed to on_chunk as they arrive; stop() closes it and returns the audio."""

    def __init__(self, lib, device_id, on_chunk, rate=RATE, chunk_ms=50):
        self.lib, self.on_chunk = lib, on_chunk
        self.handle = ctypes.c_void_p()
        self.format = _format(rate)  # Windows converts from the device's own format.
        _check(lib, 'waveIn', lib.waveInOpen(ctypes.byref(self.handle), device_id, ctypes.byref(self.format), 0, 0, 0), 'Ouverture du micro')
        size = rate * 2 * chunk_ms // 1000
        self.buffers = [ctypes.create_string_buffer(size) for _ in range(12)]
        self.headers = [WAVEHDR(ctypes.addressof(b), size, 0, 0, 0, 0, None, 0) for b in self.buffers]
        self.chunks, self.running = deque(maxlen=20), True
        self.retain = True
        for header in self.headers:
            _check(lib, 'waveIn', lib.waveInPrepareHeader(self.handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Préparation du micro')
            _check(lib, 'waveIn', lib.waveInAddBuffer(self.handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Préparation du micro')
        _check(lib, 'waveIn', lib.waveInStart(self.handle), 'Démarrage du micro')
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _take(self, header):
        data = ctypes.string_at(header.lpData, header.dwBytesRecorded)
        header.dwFlags &= ~WHDR_DONE
        if data:
            if self.retain and isinstance(self.chunks, deque):
                self.chunks = list(self.chunks)
            elif not self.retain and isinstance(self.chunks, list):
                self.chunks = deque(self.chunks[-20:], maxlen=20)
            self.chunks.append(data)
            try:
                self.on_chunk(data)
            except Exception:
                pass  # A display callback must never lose the recording.

    def _run(self):
        index = 0
        while self.running:
            header = self.headers[index]
            if header.dwFlags & WHDR_DONE:
                self._take(header)
                if self.running:
                    self.lib.waveInAddBuffer(self.handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
                index = (index + 1) % len(self.headers)
            else:
                time.sleep(.01)
        self.lib.waveInReset(self.handle)
        for offset in range(len(self.headers)):
            header = self.headers[(index + offset) % len(self.headers)]
            if header.dwFlags & WHDR_DONE:
                self._take(header)
        for header in self.headers:
            self.lib.waveInUnprepareHeader(self.handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
        self.lib.waveInClose(self.handle)

    def stop(self):
        self.running = False
        self.thread.join(timeout=5)
        return b''.join(self.chunks)


class WinAudio:
    def __init__(self):
        self._lib = None

    @property
    def lib(self):
        if self._lib is None:
            self._lib = _winmm()
        return self._lib

    def inputs(self):
        caps = WAVEINCAPSW()
        return [caps.szPname for i in range(self.lib.waveInGetNumDevs())
                if not self.lib.waveInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))]

    def outputs(self):
        caps = WAVEOUTCAPSW()
        return [caps.szPname for i in range(self.lib.waveOutGetNumDevs())
                if not self.lib.waveOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))]

    def _device(self, names, name, kind):
        if not name:
            return WAVE_MAPPER
        if name not in names:
            raise OSError(kind + ' introuvable : « ' + name + ' ». Choisissez un périphérique dans Paramètres › Voix.')
        return names.index(name)

    def open_input(self, device, on_chunk, rate=RATE):
        return Capture(self.lib, self._device(self.inputs(), device, 'Micro'), on_chunk, rate)

    def play(self, wav, device, volume, stop):
        """Plays a WAV to the end, or until stop is set. Returns False when it was interrupted."""
        pcm, rate, channels = read_wav(wav)
        pcm = scale(pcm, volume)
        lib, handle = self.lib, ctypes.c_void_p()
        fmt = _format(rate, channels)
        _check(lib, 'waveOut', lib.waveOutOpen(ctypes.byref(handle), self._device(self.outputs(), device, 'Sortie audio'), ctypes.byref(fmt), 0, 0, 0), 'Ouverture de la sortie audio')
        buffer = ctypes.create_string_buffer(pcm, len(pcm))
        header = WAVEHDR(ctypes.addressof(buffer), len(pcm), 0, 0, 0, 0, None, 0)
        completed = True
        try:
            _check(lib, 'waveOut', lib.waveOutPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Lecture')
            _check(lib, 'waveOut', lib.waveOutWrite(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Lecture')
            while not header.dwFlags & WHDR_DONE:
                if stop.is_set():
                    completed = False
                    lib.waveOutReset(handle)
                    break
                time.sleep(.02)
        finally:
            lib.waveOutReset(handle)
            lib.waveOutUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
            lib.waveOutClose(handle)
        return completed


    def play_chunks(self, chunks, done, device, volume, stop):
        """One output device for the entire streamed segment; up to three buffers queued ahead."""
        import queue
        handle, pending, lib = ctypes.c_void_p(), [], self.lib
        opened = False
        audio_format = None
        try:
            while not stop.is_set():
                while pending and pending[0][0].dwFlags & WHDR_DONE:
                    header, buffer = pending.pop(0)
                    lib.waveOutUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
                if len(pending) < 3:
                    try:
                        wav = chunks.get(timeout=.01)
                    except queue.Empty:
                        if done.is_set() and chunks.empty() and not pending:
                            return True
                        continue
                    pcm, rate, channels = read_wav(wav)
                    if not pcm:
                        continue
                    if not opened:
                        fmt = _format(rate, channels)
                        _check(lib, 'waveOut', lib.waveOutOpen(ctypes.byref(handle), self._device(self.outputs(), device, 'Sortie audio'), ctypes.byref(fmt), 0, 0, 0), 'Ouverture de la sortie audio')
                        opened, audio_format = True, (rate, channels)
                    if audio_format != (rate, channels):
                        raise ValueError('Format audio modifié pendant la lecture.')
                    pcm = scale(pcm, volume)
                    buffer = ctypes.create_string_buffer(pcm, len(pcm))
                    header = WAVEHDR(ctypes.addressof(buffer), len(pcm), 0, 0, 0, 0, None, 0)
                    _check(lib, 'waveOut', lib.waveOutPrepareHeader(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Lecture')
                    pending.append((header, buffer))
                    _check(lib, 'waveOut', lib.waveOutWrite(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR)), 'Lecture')
                else:
                    time.sleep(.01)
            return False
        finally:
            if opened:
                lib.waveOutReset(handle)
                for header, buffer in pending:
                    lib.waveOutUnprepareHeader(handle, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
                lib.waveOutClose(handle)
