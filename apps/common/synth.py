"""
Sintetizador continuo (um oscilador) para instrumentos tipo teremim.

A geracao do som (Oscillator.render) e separada da saida de audio
(AudioOutput), entao da para testar/gravar o som sem placa de audio.
A thread da camera so altera `target_freq` / `target_amp`; o oscilador faz
a transicao suave (glide) para nao estalar.
"""
import math

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
                 vibrato_rate: float = 5.5, wave: str = "teremim"):
        self.sr = sample_rate
        self.glide = glide                  # segundos (constante de tempo) do glissando
        self.amp_smoothing = amp_smoothing
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
        a1 = a0 + (ta - a0) * self._smooth(self.amp_smoothing, dt)

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


class AudioOutput:
    """Toca um Oscillator na placa de som (precisa do pacote sounddevice)."""

    def __init__(self, osc: Oscillator, device=None):
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
        self.osc.target_amp = 0.0
        self._stream.stop()
        self._stream.close()
