"""
Sintetizador continuo (um oscilador) para instrumentos tipo teremim.

A geracao do som (Oscillator.render) e separada da saida de audio
(AudioOutput), entao da para testar/gravar o som sem placa de audio.
A thread da camera so altera `target_freq` / `target_amp`; o oscilador faz
a transicao suave (glide) para nao estalar.
"""
import math
import threading

import numpy as np

SAMPLE_RATE = 44100
BLOCK_SIZE = 256


def _wave_sine(phase):
    return np.sin(2 * np.pi * phase)


def _wave_theremin(phase):
    # seno com alguns harmonicos: timbre mais "vocal", parecido com teremim
    p = 2 * np.pi * phase
    return (np.sin(p) + 0.35 * np.sin(2 * p) + 0.15 * np.sin(3 * p) + 0.05 * np.sin(5 * p)) / 1.3


def _wave_triangle(phase):
    return 2 * np.abs(2 * (phase % 1.0) - 1) - 1


def _wave_square_soft(phase):
    return np.tanh(4 * np.sin(2 * np.pi * phase)) * 0.7


WAVES = {
    "teremim": _wave_theremin,
    "seno": _wave_sine,
    "triangulo": _wave_triangle,
    "quadrada": _wave_square_soft,
}


class Oscillator:
    def __init__(self, sample_rate: int = SAMPLE_RATE, glide: float = 0.06,
                 amp_smoothing: float = 0.03, vibrato_depth: float = 0.0,
                 vibrato_rate: float = 5.5, wave: str = "teremim",
                 release: float = None):
        self.sr = sample_rate
        self.glide = glide                  # segundos (constante de tempo) do glissando
        self.amp_smoothing = amp_smoothing  # tempo de subida do volume (ataque)
        self.release = amp_smoothing if release is None else release  # tempo de descida
        self.vibrato_depth = vibrato_depth  # em semitons
        self.vibrato_rate = vibrato_rate
        self.wave = wave

        self.target_freq = 440.0
        self.target_amp = 0.0
        self._freq = 440.0
        self._amp = 0.0
        self._phase = 0.0
        self._vib_phase = 0.0

    @property
    def freq(self) -> float:
        return self._freq

    @property
    def amp(self) -> float:
        return self._amp

    @property
    def silent(self) -> bool:
        return self.target_amp <= 0 and self._amp < 1e-4

    def jump_to(self, freq: float) -> None:
        """Muda a frequencia na hora, sem glissando (inicio de nota)."""
        self.target_freq = self._freq = freq

    def _smooth(self, tau: float, dt: float) -> float:
        return 1.0 if tau <= 0 else 1 - math.exp(-dt / tau)

    def render(self, frames: int) -> np.ndarray:
        """Gera `frames` amostras float32 em [-1, 1]."""
        dt = frames / self.sr
        tf, ta = max(self.target_freq, 1.0), min(max(self.target_amp, 0.0), 1.0)

        # glide em escala logaritmica (soa natural entre oitavas)
        k = self._smooth(self.glide, dt)
        f0 = self._freq
        f1 = f0 * (tf / f0) ** k
        a0 = self._amp
        tau = self.amp_smoothing if ta >= a0 else self.release
        a1 = a0 + (ta - a0) * self._smooth(tau, dt)

        freqs = np.geomspace(f0, f1, frames, endpoint=False) if f0 != f1 else np.full(frames, f0)
        if self.vibrato_depth > 0:
            vib = self._vib_phase + np.arange(frames) * self.vibrato_rate / self.sr
            freqs = freqs * 2 ** (self.vibrato_depth * np.sin(2 * np.pi * vib) / 12)
            self._vib_phase = (vib[-1] + self.vibrato_rate / self.sr) % 1.0

        phase = self._phase + np.cumsum(freqs) / self.sr
        self._phase = phase[-1] % 1.0
        amps = np.linspace(a0, a1, frames, endpoint=False)

        self._freq, self._amp = f1, a1
        return (WAVES[self.wave](phase) * amps).astype(np.float32)


class PolySynth:
    """
    Varias vozes (Oscillator) somadas: permite tocar acordes / varias notas.

    Cada nota tem uma chave (`key`) escolhida por quem chama, por exemplo
    (mao, nota). note_on/note_off podem ser chamados da thread da camera.
    """

    def __init__(self, voices: int = 10, wave: str = "teremim", attack: float = 0.01,
                 release: float = 0.3, decay: float = 0.0, master: float = 0.6,
                 sample_rate: int = SAMPLE_RATE):
        self.sr = sample_rate
        self.decay = decay      # >0: a nota vai sumindo mesmo segurada (tipo piano)
        self.master = master
        self._voices = [Oscillator(sample_rate, glide=0.0, amp_smoothing=attack,
                                   release=release, wave=wave) for _ in range(voices)]
        self._owner = [None] * voices
        self._age = [0] * voices
        self._counter = 0
        self._lock = threading.Lock()

    @property
    def wave(self) -> str:
        return self._voices[0].wave

    @wave.setter
    def wave(self, name: str) -> None:
        for v in self._voices:
            v.wave = name

    @property
    def level(self) -> float:
        return sum(v.amp for v in self._voices)

    def _pick_voice(self, key) -> int:
        for i, owner in enumerate(self._owner):
            if owner == key:
                return i
        free = [i for i, o in enumerate(self._owner) if o is None]
        if free:  # prefere a voz livre mais silenciosa
            return min(free, key=lambda i: self._voices[i].amp)
        return min(range(len(self._voices)), key=lambda i: self._age[i])  # rouba a mais antiga

    def note_on(self, key, freq: float, velocity: float = 0.5) -> None:
        with self._lock:
            i = self._pick_voice(key)
            v = self._voices[i]
            v.jump_to(freq)
            v.target_amp = velocity
            self._counter += 1
            self._owner[i], self._age[i] = key, self._counter

    def note_off(self, key) -> None:
        with self._lock:
            for i, owner in enumerate(self._owner):
                if owner == key:
                    self._voices[i].target_amp = 0.0
                    self._owner[i] = None

    def all_off(self) -> None:
        with self._lock:
            for i, v in enumerate(self._voices):
                v.target_amp = 0.0
                self._owner[i] = None

    def render(self, frames: int) -> np.ndarray:
        mix = np.zeros(frames, np.float32)
        with self._lock:
            if self.decay > 0:
                k = math.exp(-frames / self.sr / self.decay)
                for i, v in enumerate(self._voices):
                    if self._owner[i] is not None:
                        v.target_amp *= k
            for v in self._voices:
                if not v.silent:
                    mix += v.render(frames)
        # saturacao suave: varias notas juntas nao estouram
        return np.tanh(mix * self.master).astype(np.float32)


class AudioOutput:
    """Toca um Oscillator ou PolySynth na placa de som (precisa do sounddevice)."""

    def __init__(self, osc, device=None):
        try:
            import sounddevice as sd
        except (ImportError, OSError) as e:
            raise SystemExit(
                "Nao foi possivel carregar o audio (sounddevice/PortAudio).\n"
                "Instale com: pip install sounddevice\n"
                f"Detalhe: {e}"
            )
        self.osc = osc
        self._stream = sd.OutputStream(
            samplerate=osc.sr, blocksize=BLOCK_SIZE, channels=1, dtype="float32",
            device=device, callback=self._callback, latency="low",
        )

    def _callback(self, outdata, frames, time_info, status):
        outdata[:, 0] = self.osc.render(frames)

    def __enter__(self):
        self._stream.start()
        return self

    def __exit__(self, *exc):
        self._stream.stop()
        self._stream.close()
