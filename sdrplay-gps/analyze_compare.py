#!/usr/bin/env python3
"""Compare powered (biasT=1) vs unpowered (biasT=0) GPS L1 recordings.
Overlay spectrum + envelope + stats; save PNG report."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FS = 2_048_000.0
NFFT = 4096

def load(path, seconds=20.0):
    n = int(FS * seconds)
    raw = np.fromfile(path, dtype=np.int16, count=2 * n)
    z = (raw[0::2].astype(np.float32) + 1j * raw[1::2].astype(np.float32)) / 32768.0
    return z

def welch_db(z):
    nseg = (len(z) - NFFT) // (NFFT // 2)
    win = np.hanning(NFFT).astype(np.float32)
    psd = np.zeros(NFFT, dtype=np.float64)
    idx = 0
    cnt = 0
    for _ in range(nseg):
        seg = z[idx:idx + NFFT] * win
        psd += np.abs(np.fft.fftshift(np.fft.fft(seg))) ** 2
        idx += NFFT // 2
        cnt += 1
    psd /= max(cnt, 1)
    return 10 * np.log10(psd + 1e-20), np.fft.fftshift(np.fft.fftfreq(NFFT, 1 / FS))

def envelope(z, win_s=200e-6):
    w = int(win_s * FS)
    pw = (np.abs(z) ** 2)
    nwin = (len(pw) // w) * w
    env = 10 * np.log10(pw[:nwin].reshape(-1, w).mean(axis=1) + 1e-12)
    rate = FS / w
    # ACF pulse test
    res = {}
    thresh = np.median(env) + 6.0
    onoff = (env > thresh).astype(np.float64)
    duty = float(onoff.mean())
    if 0.02 < duty < 0.98:
        x = onoff - onoff.mean()
        spec = np.fft.rfft(x, 2 * len(x))
        acf = np.fft.irfft(spec * np.conj(spec), 2 * len(x))[:len(x)]
        acf /= (acf[0] + 1e-12)
        min_lag = max(2, int(0.001 * rate))
        max_lag = min(len(acf) - 1, int(rate / 20))
        k = int(np.argmax(acf[min_lag:max_lag])) + min_lag
        peak = float(acf[k])
        for cand in range(min_lag, k + 1):
            if acf[cand] >= 0.9 * peak:
                k = cand; peak = float(acf[k]); break
        res = {"duty": duty, "acf": peak, "rate": rate / k}
    else:
        res = {"duty": duty, "acf": 0.0, "rate": 0.0}
    return env, rate, res

def stats(db, f, label):
    band = (f >= -0.75e6) & (f <= 0.75e6)
    b = db[band]
    floor = float(np.median(b))
    local = b[b < floor + 10]
    flat = float(np.std(local)) if local.size > 10 else float(np.std(b))
    edge = (np.abs(f) >= 0.8e6) & (np.abs(f) <= 1.0e6)
    print(f"[{label}] floor={floor:.2f} dB  flatness(std)={flat:.2f} dB  "
          f"edge-mean={db[edge].mean():.2f} dB")
    return floor, flat

def main():
    on_path, off_path, out_png = sys.argv[1], sys.argv[2], sys.argv[3]
    print(f"loading {on_path} (biasT=1) ...")
    z_on = load(on_path)
    print(f"loading {off_path} (biasT=0) ...")
    z_off = load(off_path)

    db_on, f = welch_db(z_on)
    db_off, _ = welch_db(z_off)
    f_on, fl_on = stats(db_on, f, "biasT=1")
    f_off, fl_off = stats(db_off, f, "biasT=0")
    print(f"[delta] floor(powered) - floor(unpowered) = {f_on - f_off:+.2f} dB")

    env_on, rate, res_on = envelope(z_on)
    env_off, _, res_off = envelope(z_off)
    print(f"[envelope on ] duty={res_on['duty']:.3f} acf={res_on['acf']:.2f} rate={res_on['rate']:.1f} Hz")
    print(f"[envelope off] duty={res_off['duty']:.3f} acf={res_off['acf']:.2f} rate={res_off['rate']:.1f} Hz")

    fig, axes = plt.subplots(3, 1, figsize=(12, 12))
    axes[0].plot(f / 1e3, db_off, lw=0.5, label=f"biasT=0 (unpowered), floor {f_off:.1f} dB", color="#888888")
    axes[0].plot(f / 1e3, db_on, lw=0.5, label=f"biasT=1 (powered), floor {f_on:.1f} dB", color="#cc0052")
    axes[0].set_xlabel("Frequency offset from 1575.42 MHz [kHz]")
    axes[0].set_ylabel("PSD [dB]")
    axes[0].set_title(f"GPS L1 average spectrum — RSPduo Tuner 2, gRdB=40 LNA=5, AGC off, 2.048 MSPS\n"
                      f"Gdańsk {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    t_on = np.arange(len(env_on)) / rate
    t_off = np.arange(len(env_off)) / rate
    axes[1].plot(t_off, env_off, lw=0.3, color="#888888")
    axes[1].set_title("Power envelope — biasT=0 (receiver noise floor only)")
    axes[1].set_xlabel("Time [s]"); axes[1].set_ylabel("Envelope [dB]"); axes[1].grid(alpha=0.3)
    axes[2].plot(t_on, env_on, lw=0.3, color="#cc0052")
    axes[2].set_title("Power envelope — biasT=1 (active antenna LNA powered)")
    axes[2].set_xlabel("Time [s]"); axes[2].set_ylabel("Envelope [dB]"); axes[2].grid(alpha=0.3)
    for ax in axes:
        ax.set_xlim(0, max(t_on[-1], t_off[-1]))
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    print(f"saved: {out_png}")

if __name__ == "__main__":
    main()
