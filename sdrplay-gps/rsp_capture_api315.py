#!/usr/bin/env python3
"""RSPduo capture via SDRplay Hardware API 3.15 (ctypes, user-level).

Full control: bias-T on Tuner 1, AGC disabled, fixed gain, 2.048 MSPS, GPS L1.
Writes raw interleaved int16 IQ + prints gain/overload events and sanity stats.
"""
import ctypes as C
import numpy as np
import time, sys, os, collections

LIB = os.path.expanduser("~/sdrwork/api315/amd64/libsdrplay_api.so.3.15")

# ---------------- enums ----------------
BW_1_536 = 1536
IF_ZERO = 0
LO_AUTO = 1
MIN_GR_NORMAL = 20
TUNER_N, TUNER_A, TUNER_B = 0, 1, 2
AGC_DISABLE = 0
RSPDUO_SINGLE = 1
RSPDUO_HWVER = 3
UPD_TUNER_GR = 0x00008000
UPD_TUNER_FRF = 0x00020000
UPD_TUNER_BW = 0x00040000
UPD_TUNER_IF = 0x00080000
UPD_CTRL_DC = 0x00400000
UPD_CTRL_AGC = 0x01000000
UPD_RSPDUO_BIAST = 0x08000000
EV_GAIN_CHANGE, EV_OVERLOAD_CHANGE, EV_DEVICE_REMOVED, EV_RSPDUO_MODE, EV_DEVICE_FAILURE = 0, 1, 2, 3, 4

# ---------------- structs ----------------
class GainValuesT(C.Structure):
    _fields_ = [("curr", C.c_float), ("max", C.c_float), ("min", C.c_float)]

class GainT(C.Structure):
    _fields_ = [("gRdB", C.c_int), ("LNAstate", C.c_ubyte), ("syncUpdate", C.c_ubyte),
                ("minGr", C.c_int), ("gainVals", GainValuesT)]

class RfFreqT(C.Structure):
    _fields_ = [("rfHz", C.c_double), ("syncUpdate", C.c_ubyte)]

class DcOffsetTunerT(C.Structure):
    _fields_ = [("dcCal", C.c_ubyte), ("speedUp", C.c_ubyte),
                ("trackTime", C.c_int), ("refreshRateTime", C.c_int)]

class TunerParamsT(C.Structure):
    _fields_ = [("bwType", C.c_int), ("ifType", C.c_int), ("loMode", C.c_int),
                ("gain", GainT), ("rfFreq", RfFreqT), ("dcOffsetTuner", DcOffsetTunerT)]

class DcOffsetT(C.Structure):
    _fields_ = [("DCenable", C.c_ubyte), ("IQenable", C.c_ubyte)]

class DecimationT(C.Structure):
    _fields_ = [("enable", C.c_ubyte), ("decimationFactor", C.c_ubyte), ("wideBandSignal", C.c_ubyte)]

class AgcT(C.Structure):
    _fields_ = [("enable", C.c_int), ("setPoint_dBfs", C.c_int), ("attack_ms", C.c_ushort),
                ("decay_ms", C.c_ushort), ("decay_delay_ms", C.c_ushort),
                ("decay_threshold_dB", C.c_ushort), ("syncUpdate", C.c_int)]

class ControlParamsT(C.Structure):
    _fields_ = [("dcOffset", DcOffsetT), ("decimation", DecimationT), ("agc", AgcT), ("adsbMode", C.c_int)]

class Rsp1aTunerParamsT(C.Structure):
    _fields_ = [("biasTEnable", C.c_ubyte)]

class Rsp2TunerParamsT(C.Structure):
    _fields_ = [("biasTEnable", C.c_ubyte), ("amPortSel", C.c_int), ("antennaSel", C.c_int),
                ("rfNotchEnable", C.c_ubyte)]

class RspDuoResetSlaveFlagsT(C.Structure):
    _fields_ = [("resetGainUpdate", C.c_ubyte), ("resetRfUpdate", C.c_ubyte)]

class RspDuoTunerParamsT(C.Structure):
    _fields_ = [("biasTEnable", C.c_ubyte), ("tuner1AmPortSel", C.c_int),
                ("tuner1AmNotchEnable", C.c_ubyte), ("rfNotchEnable", C.c_ubyte),
                ("rfDabNotchEnable", C.c_ubyte), ("resetSlaveFlags", RspDuoResetSlaveFlagsT)]

class RspDxTunerParamsT(C.Structure):
    _fields_ = [("hdrBw", C.c_int)]

class RxChannelParamsT(C.Structure):
    _fields_ = [("tunerParams", TunerParamsT), ("ctrlParams", ControlParamsT),
                ("rsp1aTunerParams", Rsp1aTunerParamsT), ("rsp2TunerParams", Rsp2TunerParamsT),
                ("rspDuoTunerParams", RspDuoTunerParamsT), ("rspDxTunerParams", RspDxTunerParamsT)]

class FsFreqT(C.Structure):
    _fields_ = [("fsHz", C.c_double), ("syncUpdate", C.c_ubyte), ("reCal", C.c_ubyte)]

class SyncUpdateT(C.Structure):
    _fields_ = [("sampleNum", C.c_uint), ("period", C.c_uint)]

class ResetFlagsT(C.Structure):
    _fields_ = [("resetGainUpdate", C.c_ubyte), ("resetRfUpdate", C.c_ubyte), ("resetFsUpdate", C.c_ubyte)]

class Rsp1aParamsT(C.Structure):
    _fields_ = [("rfNotchEnable", C.c_ubyte), ("rfDabNotchEnable", C.c_ubyte)]

class Rsp2ParamsT(C.Structure):
    _fields_ = [("extRefOutputEn", C.c_ubyte)]

class RspDuoParamsT(C.Structure):
    _fields_ = [("extRefOutputEn", C.c_int)]

class RspDxParamsT(C.Structure):
    _fields_ = [("hdrEnable", C.c_ubyte), ("biasTEnable", C.c_ubyte), ("antennaSel", C.c_int),
                ("rfNotchEnable", C.c_ubyte), ("rfDabNotchEnable", C.c_ubyte)]

class DevParamsT(C.Structure):
    _fields_ = [("ppm", C.c_double), ("fsFreq", FsFreqT), ("syncUpdate", SyncUpdateT),
                ("resetFlags", ResetFlagsT), ("mode", C.c_int), ("samplesPerPkt", C.c_uint),
                ("rsp1aParams", Rsp1aParamsT), ("rsp2Params", Rsp2ParamsT),
                ("rspDuoParams", RspDuoParamsT), ("rspDxParams", RspDxParamsT)]

class DeviceT(C.Structure):
    _fields_ = [("SerNo", C.c_char * 64), ("hwVer", C.c_ubyte), ("tuner", C.c_int),
                ("rspDuoMode", C.c_int), ("valid", C.c_ubyte),
                ("rspDuoSampleFreq", C.c_double), ("dev", C.c_void_p)]

class DeviceParamsT(C.Structure):
    _fields_ = [("devParams", C.POINTER(DevParamsT)),
                ("rxChannelA", C.POINTER(RxChannelParamsT)),
                ("rxChannelB", C.POINTER(RxChannelParamsT))]

class StreamCbParamsT(C.Structure):
    _fields_ = [("firstSampleNum", C.c_uint), ("grChanged", C.c_int),
                ("rfChanged", C.c_int), ("fsChanged", C.c_int), ("numSamples", C.c_uint)]

class GainCbParamT(C.Structure):
    _fields_ = [("gRdB", C.c_uint), ("lnaGRdB", C.c_uint), ("currGain", C.c_double)]

class PowerOverloadCbParamT(C.Structure):
    _fields_ = [("powerOverloadChangeType", C.c_int)]

class RspDuoModeCbParamT(C.Structure):
    _fields_ = [("modeChangeType", C.c_int)]

class EventParamsT(C.Union):
    _fields_ = [("gainParams", GainCbParamT), ("powerOverloadParams", PowerOverloadCbParamT),
                ("rspDuoModeParams", RspDuoModeCbParamT)]

STREAM_CB = C.CFUNCTYPE(None, C.POINTER(C.c_short), C.POINTER(C.c_short),
                        C.POINTER(StreamCbParamsT), C.c_uint, C.c_uint, C.c_void_p)
EVENT_CB = C.CFUNCTYPE(None, C.c_int, C.c_int, C.POINTER(EventParamsT), C.c_void_p)

class CallbackFnsT(C.Structure):
    _fields_ = [("StreamACbFn", STREAM_CB), ("StreamBCbFn", STREAM_CB), ("EventCbFn", EVENT_CB)]

# ---------------- capture state ----------------
class Sink:
    def __init__(self, path):
        self.fh = open(path, "wb") if path else None
        self.samples = 0
        self.events = []
        self.overload_count = 0
        self.gain_events = []

    def stream_a(self, xi, xq, params, num, reset, ctx):
        if not self.fh or num == 0:
            return
        i = np.ctypeslib.as_array(xi, shape=(num,)).copy()
        q = np.ctypeslib.as_array(xq, shape=(num,)).copy()
        inter = np.empty(2 * num, dtype=np.int16)
        inter[0::2] = i
        inter[1::2] = q
        self.fh.write(inter.tobytes())
        self.samples += num

    def event(self, ev, tuner, params, ctx):
        self.events.append(ev)
        if ev == EV_OVERLOAD_CHANGE:
            t = params[0].powerOverloadParams.powerOverloadChangeType
            self.overload_count += 1
            print(f"  [event] OVERLOAD {'DETECTED' if t == 0 else 'CORRECTED'}")
        elif ev == EV_GAIN_CHANGE:
            g = params[0].gainParams
            self.gain_events.append((g.gRdB, g.lnaGRdB, g.currGain))


def check(rc, lib, what):
    if rc != 0:
        msg = lib.sdrplay_api_GetErrorString(rc).decode(errors="replace")
        raise SystemExit(f"FATAL: {what} failed rc={rc} ({msg})")
    print(f"[api] {what}: OK (rc=0)")


def soft_check(rc, lib, what):
    if rc != 0:
        msg = lib.sdrplay_api_GetErrorString(rc).decode(errors="replace")
        print(f"[api] {what}: rc={rc} ({msg}) - continuing")
        return False
    print(f"[api] {what}: OK (rc=0)")
    return True


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/sdrwork/gps_rsp_api.raw")
    biast = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    lna = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    grdb = int(sys.argv[5]) if len(sys.argv) > 5 else 40

    lib = C.CDLL(LIB)
    lib.sdrplay_api_GetErrorString.restype = C.c_char_p
    lib.sdrplay_api_Update.argtypes = [C.c_void_p, C.c_int, C.c_uint, C.c_uint]
    lib.sdrplay_api_Init.argtypes = [C.c_void_p, C.POINTER(CallbackFnsT), C.c_void_p]
    lib.sdrplay_api_GetDeviceParams.argtypes = [C.c_void_p, C.POINTER(C.POINTER(DeviceParamsT))]
    lib.sdrplay_api_SelectDevice.argtypes = [C.POINTER(DeviceT)]
    lib.sdrplay_api_Uninit.argtypes = [C.c_void_p]
    lib.sdrplay_api_ReleaseDevice.argtypes = [C.POINTER(DeviceT)]
    print("sizeof checks: Gain", C.sizeof(GainT), "Tuner", C.sizeof(TunerParamsT),
          "Ctrl", C.sizeof(ControlParamsT), "RxCh", C.sizeof(RxChannelParamsT),
          "Dev", C.sizeof(DevParamsT), "Device", C.sizeof(DeviceT))

    check(lib.sdrplay_api_Open(), lib, "Open")
    ver = C.c_float()
    check(lib.sdrplay_api_ApiVersion(C.byref(ver)), lib, "ApiVersion")
    print(f"[api] version {ver.value:.2f}")
    check(lib.sdrplay_api_DisableHeartbeat(), lib, "DisableHeartbeat")
    check(lib.sdrplay_api_LockDeviceApi(), lib, "LockDeviceApi")

    devices = (DeviceT * 16)()
    ndev = C.c_uint()
    check(lib.sdrplay_api_GetDevices(devices, C.byref(ndev), 16), lib, "GetDevices")
    print(f"[api] devices found: {ndev.value}")
    idx = None
    for k in range(ndev.value):
        d = devices[k]
        print(f"  [{k}] hwVer={d.hwVer} tuner={d.tuner} mode={d.rspDuoMode} sn={d.SerNo.decode(errors='replace')}")
        if d.hwVer == RSPDUO_HWVER and idx is None:
            idx = k
    if idx is None:
        lib.sdrplay_api_UnlockDeviceApi(); lib.sdrplay_api_Close()
        raise SystemExit("FATAL: no RSPduo found")
    # rspDuoMode and tuner are INPUTS to SelectDevice for RSPduo:
    # force Single-Tuner mode on Tuner A (ANTENNA A = Tuner 1 SMA)
    devices[idx].rspDuoMode = RSPDUO_SINGLE  # Single_Tuner
    devices[idx].tuner = TUNER_B  # ANT B SMA - the only port with bias-T
    print(f"[api] forcing rspDuoMode={devices[idx].rspDuoMode} tuner={devices[idx].tuner} (B)")
    check(lib.sdrplay_api_SelectDevice(C.byref(devices[idx])), lib, "SelectDevice")
    dev = devices[idx].dev
    print(f"[api] selected device {idx}: {devices[idx].SerNo.decode(errors='replace')}")

    dp = C.POINTER(DeviceParamsT)()
    check(lib.sdrplay_api_GetDeviceParams(dev, C.byref(dp)), lib, "GetDeviceParams")
    p = dp.contents
    # device params
    p.devParams.contents.fsFreq.fsHz = 2_048_000.0
    p.devParams.contents.ppm = 0.0
    # single-tuner mode: only the selected tuner's channel is allocated
    ch = p.rxChannelA if p.rxChannelA else p.rxChannelB
    ch_name = "A" if p.rxChannelA else "B"
    print(f"[note] active channel = rxChannel{ch_name}")
    t = ch.contents.tunerParams
    t.bwType = BW_1_536
    t.ifType = IF_ZERO
    t.loMode = LO_AUTO
    t.gain.gRdB = grdb
    t.gain.LNAstate = lna
    t.gain.minGr = MIN_GR_NORMAL
    t.rfFreq.rfHz = 1_575_420_000.0
    t.rfFreq.syncUpdate = 0
    # control: DC/IQ correction on, AGC OFF (fixed gain!)
    c = ch.contents.ctrlParams
    c.dcOffset.DCenable = 1
    c.dcOffset.IQenable = 1
    c.agc.enable = AGC_DISABLE
    c.agc.setPoint_dBfs = -30
    # RSPduo tuner params: bias-T on the selected tuner (B = ANT B, only port with bias-T)
    duo = ch.contents.rspDuoTunerParams
    duo.biasTEnable = biast
    print(f"[cfg] fs=2.048M bw=1.536 if=zero agc=off gRdB={grdb} lna={lna} biasT={biast}")
    # metadata sidecar
    meta = {"file": out, "fs": 2048000, "bw": BW_1_536, "if": IF_ZERO, "freq_hz": 1575420000,
            "agc": "off", "gRdB": grdb, "lna_state": lna, "biasT": biast,
            "duration_s": seconds, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        import json as _json
        with open(out.replace(".raw", "") + "_meta.json", "w") as mf:
            _json.dump(meta, mf, indent=1)
    except Exception as e:
        print("meta write failed:", e)

    sink = Sink(out)
    cb_a = STREAM_CB(sink.stream_a)
    cb_e = EVENT_CB(sink.event)
    fns = CallbackFnsT(cb_a, cb_a, cb_e)  # same sink for both stream callbacks

    check(lib.sdrplay_api_Init(dev, C.byref(fns), None), lib, "Init")
    # readback: what does the service actually have? (structs are output params)
    duo_r = ch.contents.rspDuoTunerParams
    t_r = ch.contents.tunerParams
    c_r = ch.contents.ctrlParams
    print(f"[readback] biasTEnable={duo_r.biasTEnable} agc.enable={c_r.agc.enable} "
          f"gRdB={t_r.gain.gRdB} LNA={t_r.gain.LNAstate} "
          f"gainVals(curr/max/min)={t_r.gain.gainVals.curr:.1f}/{t_r.gain.gainVals.max:.1f}/{t_r.gain.gainVals.min:.1f}")
    # make sure bias-T really applied (biasTEnable was already set pre-Init;
    # Update re-asserts it and refreshes gain after Init)
    soft_check(lib.sdrplay_api_Update(dev, TUNER_B, UPD_RSPDUO_BIAST, 0), lib, "Update BiasT (B)")
    if soft_check(lib.sdrplay_api_Update(dev, TUNER_B, UPD_RSPDUO_BIAST, 0), lib, "Update BiasT (B retry)") is False:
        soft_check(lib.sdrplay_api_Update(dev, 3, UPD_RSPDUO_BIAST, 0), lib, "Update BiasT (Both)")
    soft_check(lib.sdrplay_api_Update(dev, TUNER_B, UPD_TUNER_GR, 0), lib, "Update Gain")
    print(f"[readback2] biasTEnable={ch.contents.rspDuoTunerParams.biasTEnable}")
    print(f"[record] streaming {seconds:.0f}s -> {out}")
    try:
        t0 = time.time()
        time.sleep(seconds)
        el = time.time() - t0
        print(f"[record] samples={sink.samples:,} rate={sink.samples/el/1e6:.3f} MSPS "
              f"events={len(sink.events)} overloads={sink.overload_count}")
    finally:
        soft_check(lib.sdrplay_api_Uninit(dev), lib, "Uninit")
        soft_check(lib.sdrplay_api_ReleaseDevice(C.byref(devices[idx])), lib, "ReleaseDevice")
        lib.sdrplay_api_UnlockDeviceApi()
        lib.sdrplay_api_Close()
    if sink.fh:
        sink.fh.close()
    print(f"[file] {out} = {os.path.getsize(out):,} bytes")

    # sanity
    arr = np.fromfile(out, dtype=np.int16, count=2_000_000)
    print(f"[sanity] I mean={arr[0::2].mean():.1f} std={arr[0::2].std():.1f} | "
          f"Q mean={arr[1::2].mean():.1f} std={arr[1::2].std():.1f}")

if __name__ == "__main__":
    main()
