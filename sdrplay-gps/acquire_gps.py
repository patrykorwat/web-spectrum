#!/usr/bin/env python3
"""Parallel C/A acquisition (FFT-PCPS) on recorded GPS L1 IQ.

Method (standard): for each PRN and Doppler bin, per-1ms coherent correlation
(FFT, circular, 2048 samples = one code period) followed by non-coherent
accumulation over N ms. Peak/median ratio > threshold = satellite present.
"""
import sys, math
import numpy as np

FS = 2_048_000.0
CA_LEN = 1023
MS_SAMPLES = int(FS / 1000)  # 2048

# ICD-GPS-200 G2 tap table (1-indexed register taps)
G2_TAPS = {
    1: (2, 6), 2: (3, 7), 3: (4, 8), 4: (5, 9), 5: (1, 9), 6: (2, 10), 7: (1, 10),
    8: (2, 9), 9: (3, 10), 10: (2, 3), 11: (3, 4), 12: (5, 6), 13: (6, 7), 14: (7, 8),
    15: (8, 9), 16: (9, 10), 17: (1, 4), 18: (2, 5), 19: (3, 6), 20: (4, 7), 21: (5, 8),
    22: (6, 9), 23: (1, 3), 24: (4, 6), 25: (5, 7), 26: (6, 8), 27: (7, 9), 28: (8, 10),
    29: (1, 6), 30: (2, 7), 31: (3, 8), 32: (4, 9),
}

_CA_CACHE = {}

def ca_code(prn):
    """C/A code chips (+/-1), 1023 chips, cached."""
    if prn in _CA_CACHE:
        return _CA_CACHE[prn]
    t1a, t1b = G2_TAPS[prn]
    # all-ones BIT state == all -1 in the +-1 domain (bit1 -> -1).
    # (all +1 would be the all-zero-bit LOCK state of the LFSR)
    g1 = -np.ones(10, dtype=np.int8)
    g2 = -np.ones(10, dtype=np.int8)
    out = np.empty(CA_LEN, dtype=np.float64)
    for i in range(CA_LEN):
        out[i] = g1[9] * (g2[t1a - 1] * g2[t1b - 1])
        # feedback in +-1 domain: XOR of bits == product (+1=0, -1=1)
        fb1 = g1[2] * g1[9]                                    # G1: taps 3,10
        g1[1:] = g1[:-1]; g1[0] = fb1
        fb2 = g2[1]*g2[2]*g2[5]*g2[7]*g2[8]*g2[9]              # G2: taps 2,3,6,8,9,10
        g2[1:] = g2[:-1]; g2[0] = fb2
    _CA_CACHE[prn] = out
    return out


def code_sampled(prn):
    """C/A code resampled to MS_SAMPLES samples per ms (zero-order hold)."""
    idx = (np.arange(MS_SAMPLES) * CA_LEN) // MS_SAMPLES
    return ca_code(prn)[idx]


def load_ms_blocks(path, skip_ms, nblocks):
    """Read nblocks x 1ms of IQ as a (nblocks, MS_SAMPLES) complex128 array."""
    start = int(skip_ms * MS_SAMPLES) * 2
    total = nblocks * MS_SAMPLES
    raw = np.fromfile(path, dtype=np.int16, count=2 * total, offset=start)
    if len(raw) < 2 * total:
        raise IOError(f"file too short: need {2*total} samples, got {len(raw)}")
    z = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
    z /= 32768.0
    return z.reshape(nblocks, MS_SAMPLES)


def acquire(path, prns=range(1, 33), nblocks=50, skip_ms=2000, dopplers=None):
    if dopplers is None:
        dopplers = np.arange(-5500, 5501, 250.0)
    nfft = MS_SAMPLES
    # load the needed window ONCE per file
    blocks = load_ms_blocks(path, skip_ms, nblocks)
    # precompute Doppler carrier tables once
    tvec = np.arange(MS_SAMPLES) / FS
    carriers = {f: np.exp(-2j * np.pi * f * tvec) for f in dopplers}
    results = {}
    for prn in prns:
        code = code_sampled(prn)
        code_c = np.conj(np.fft.fft(code))  # full FFT (numpy 2.5 rfft rejects complex input)
        best = (0.0, 0.0)
        for f in dopplers:
            car = carriers[f]
            acc = np.zeros(nfft)
            for blk in blocks:
                corr = np.fft.ifft(np.fft.fft(blk * car) * code_c)
                acc += corr.real ** 2 + corr.imag ** 2
            med = float(np.median(acc))
            pk = float(acc.max())
            ratio = pk / max(med, 1e-12)
            if ratio > best[0]:
                best = (ratio, float(f))
        results[prn] = best
    return results


def scan_prn(path, prn, nblocks, skip_ms, dopplers):
    """Doppler scan for ONE PRN — unit of work for the process pool."""
    nfft = MS_SAMPLES
    blocks = load_ms_blocks(path, skip_ms, nblocks)
    code = code_sampled(prn)
    code_c = np.conj(np.fft.fft(code))
    tvec = np.arange(MS_SAMPLES) / FS
    best = (0.0, 0.0)
    for f in dopplers:
        car = np.exp(-2j * np.pi * f * tvec)
        acc = np.zeros(nfft)
        for blk in blocks:
            corr = np.fft.ifft(np.fft.fft(blk * car) * code_c)
            acc += corr.real ** 2 + corr.imag ** 2
        med = float(np.median(acc))
        pk = float(acc.max())
        ratio = pk / max(med, 1e-12)
        if ratio > best[0]:
            best = (ratio, float(f))
    return prn, best[0], best[1]


def _scan_job(args):
    """Pickle-friendly wrapper: single tuple argument -> scan_prn."""
    path, prn, nblocks, skip_ms, dopplers = args
    return scan_prn(path, prn, nblocks, skip_ms, dopplers)


def run_window(path, skip_ms, nblocks, workers=8, dopplers=None):
    """Acquire all 32 PRNs for one time window, using a process pool."""
    from concurrent.futures import ProcessPoolExecutor
    if dopplers is None:
        dopplers = np.arange(-5500, 5501, 250.0)
    prns = list(range(1, 33))
    results = {}
    args = [(path, prn, nblocks, skip_ms, tuple(float(x) for x in dopplers)) for prn in prns]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for prn, ratio, dop in pool.map(_scan_job, args):
            results[prn] = (ratio, dop)
    return results


def print_window(label, res):
    found = {p: r for p, r in res.items() if r[0] > 3.0}
    top = sorted(res.items(), key=lambda kv: kv[1][0], reverse=True)[:6]
    print(f"[{label}] ratio>3: {sorted(found.keys())} (n={len(found)})")
    print(f"[{label}] top6: " + ", ".join(f"PRN{p}: {r[0]:.1f}@{r[1]:+.0f}Hz" for p, r in top))


def selftest_codes():
    """Every PRN: autocorr peak == 1023; cross-PRN correlation small (<~100)."""
    ok = True
    ref = ca_code(1)
    for p in range(1, 33):
        c = ca_code(p)
        auto = float(np.abs(np.dot(c, c)))
        if abs(auto - CA_LEN) > 1e-6:
            print(f"  PRN{p}: autocorr {auto:.1f} != 1023  FAIL")
            ok = False
    cross = max(float(abs(np.dot(ca_code(a), ca_code(b))))
                for a in range(1, 33) for b in range(a + 1, 33))
    print(f"selftest: all autocorr=1023 OK; max cross-corr = {cross:.0f} "
          f"({'OK' if cross < 120 else 'TOO HIGH - table wrong'})")
    return ok and cross < 120


def main():
    if "--selftest" in sys.argv:
        ok = selftest_codes()
        sys.exit(0 if ok else 1)
    on_path, off_path = sys.argv[1], sys.argv[2]
    nblocks = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    print(f"[selftest] {selftest_codes()}")
    if off_path != "-" and off_path != on_path:
        # A/B comparison mode
        res_on = run_window(on_path, 2000, nblocks)
        print_window(f"{on_path.split('/')[-1]} (A)", res_on)
        res_off = run_window(off_path, 2000, nblocks)
        print_window(f"{off_path.split('/')[-1]} (B)", res_off)
        strong_on = {p for p, r in res_on.items() if r[0] > 3.0}
        strong_off = {p for p, r in res_off.items() if r[0] > 3.0}
        print(f"[verdict] A: {len(strong_on)} sats | B: {len(strong_off)} sats | A-only: {sorted(strong_on - strong_off)}")
    else:
        # single-file mode: time windows (--skip MS [MS ...])
        skips = [2000]
        if "--skip" in sys.argv:
            i = sys.argv.index("--skip")
            skips = [int(x) for x in sys.argv[i + 1:] if not x.startswith("--")]
        merged = set()
        for sk in skips:
            res = run_window(on_path, sk, nblocks)
            merged |= {p for p, r in res.items() if r[0] > 3.0}
            print_window(f"{on_path.split('/')[-1]} @+{sk}ms", res)
        print(f"[verdict] merged across windows: {len(merged)} sats: {sorted(merged)}")


if __name__ == "__main__":
    main()
