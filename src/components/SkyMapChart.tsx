/*!
 * Live sky map for GNSS decoding: polar view (azimuth/elevation) of GNSS
 * satellites above the observer, with live-detected PRNs highlighted.
 *
 * Positions are propagated with SGP4 (satellite.js) from GPS TLE data.
 * TLE source: live fetch from CelesTrak when the browser can reach it,
 * otherwise the embedded snapshot (epoch 2026-10-19).
 */

import { useEffect, useMemo, useState } from 'react';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import * as satellite from 'satellite.js';

export interface SkyMapSat {
  prn: number;
  snr?: number;
}

interface SkyMapProps {
  detectedSats: SkyMapSat[];
}

// CelesTrak does not send CORS headers, so the browser fetch usually fails;
// the embedded snapshot keeps the map working offline / from any origin.
const GPS_TLE_SNAPSHOT = `
GPS BIIR-5  (PRN 22)    
1 26407U 00040A   26293.04791948 -.00000019  00000+0  00000+0 0  9996
2 26407  54.8304 210.2081 0116319 304.6001 132.8686  2.00558713192450
GPS BIIR-8  (PRN 16)    
1 27663U 03005A   26292.76983211 -.00000019  00000+0  00000+0 0  9999
2 27663  54.8599 210.0243 0152117  54.0829 318.1673  2.00553867173818
GPS BIIR-11 (PRN 19)    
1 28190U 04009A   26292.11681191 -.00000003  00000+0  00000+0 0  9994
2 28190  54.7356 270.6685 0118615 177.4445 238.9352  2.00572425165438
GPS BIIR-13 (PRN 02)    
1 28474U 04045A   26293.03879928 -.00000044  00000+0  00000+0 0  9993
2 28474  55.0555 319.8566 0173587 319.7208 104.9605  2.00561411160935
GPS BIIRM-1 (PRN 17)    
1 28874U 05038A   26293.06515943 -.00000005  00000+0  00000+0 0  9994
2 28874  54.7856 268.1268 0128501 298.5275 110.5046  2.00557165154349
GPS BIIRM-2 (PRN 31)    
1 29486U 06042A   26292.87663969  .00000056  00000+0  00000+0 0  9995
2 29486  54.7199 146.3840 0109552  58.3344 115.5645  2.00563949146894
GPS BIIRM-3 (PRN 12)    
1 29601U 06052A   26293.05964843 -.00000018  00000+0  00000+0 0  9990
2 29601  54.9152 209.0609 0087320  93.0268 268.0005  2.00649014145917
GPS BIIRM-4 (PRN 15)    
1 32260U 07047A   26292.87306130  .00000020  00000+0  00000+0 0  9990
2 32260  54.1960  74.9319 0168147  90.1059 271.8278  2.00574583139310
GPS BIIRM-5 (PRN 29)    
1 32384U 07062A   26293.19815926 -.00000005  00000+0  00000+0 0  9992
2 32384  54.9410 269.1164 0035699 170.2679 194.2625  2.00566865138029
GPS BIIRM-6 (PRN 07)    
1 32711U 08012A   26292.78381463  .00000057  00000+0  00000+0 0  9996
2 32711  54.5097 144.9437 0211924 248.8110 108.9952  2.00554144136257
GPS BIIRM-8 (PRN 05)    
1 35752U 09043A   26293.27883750 -.00000081  00000+0  00000+0 0  9998
2 35752  56.2799  22.5492 0050167  86.6352 283.5738  2.00574990125870
GPS BIIF-1  (PRN 25)    
1 36585U 10022A   26293.12086999 -.00000016  00000+0  00000+0 0  9994
2 36585  54.2522 203.5331 0115842  55.9406 322.4745  2.00551617120104
GPS BIIF-3  (PRN 24)    
1 38833U 12053A   26291.96415553  .00000050  00000+0  00000+0 0  9997
2 38833  53.6047 138.5228 0187455  68.1282 293.9366  2.00557580101921
GPS BIIF-4  (PRN 27)    
1 39166U 13023A   26292.82783757 -.00000006  00000+0  00000+0 0  9997
2 39166  54.4168 263.8869 0143933  51.2534 310.0160  2.00563117 98384
GPS BIIF-5  (PRN 30)    
1 39533U 14008A   26292.82875507  .00000056  00000+0  00000+0 0  9998
2 39533  53.6693 144.2308 0083652 231.5365 127.7942  2.00567993 92181
GPS BIIF-6  (PRN 06)    
1 39741U 14026A   26293.11066994 -.00000050  00000+0  00000+0 0  9999
2 39741  56.4285 326.6462 0040602 324.0988  35.6881  2.00552156 91042
GPS BIIF-7  (PRN 09)    
1 40105U 14045A   26292.69920760  .00000040  00000+0  00000+0 0  9996
2 40105  55.4446  83.5072 0036666 121.2979 239.0754  2.00566448 88576
GPS BIIF-8  (PRN 03)    
1 40294U 14068A   26291.57466276 -.00000079  00000+0  00000+0 0  9996
2 40294  57.0650  26.2130 0066492  74.0041 286.7526  2.00558951 87681
GPS BIIF-9  (PRN 26)    
1 40534U 15013A   26292.70446635 -.00000016  00000+0  00000+0 0  9998
2 40534  53.1505 199.0320 0114908  42.0205 318.8991  2.00568634 84327
GPS BIIF-10 (PRN 08)    
1 40730U 15033A   26292.87185308 -.00000008  00000+0  00000+0 0  9994
2 40730  53.8953 261.9373 0119136  30.9798 329.7072  2.00549673 82496
GPS BIIF-11 (PRN 10)    
1 41019U 15062A   26292.42246010 -.00000078  00000+0  00000+0 0  9993
2 41019  57.0358  26.0366 0117750 231.6259 127.3392  2.00566956 80326
GPS BIIF-12 (PRN 32)    
1 41328U 16007A   26293.00854753  .00000044  00000+0  00000+0 0  9992
2 41328  55.6119  84.5132 0098933 247.4145 111.5509  2.00570831 78349
GPS BIII-1  (PRN 04)    
1 43873U 18109A   26292.89898432  .00000049  00000+0  00000+0 0  9997
2 43873  55.7665  87.2686 0041085 196.5973 335.5681  2.00566391 57573
GPS BIII-2  (PRN 18)    
1 44506U 19056A   26292.78941075 -.00000053  00000+0  00000+0 0  9999
2 44506  55.5680 326.1827 0066669 201.1745 158.2607  2.00572428 52569
GPS BIII-3  (PRN 23)    
1 45854U 20041A   26293.11932022 -.00000079  00000+0  00000+0 0  9990
2 45854  56.7429  24.1076 0069412 207.0028 324.9024  2.00572908 46548
GPS BIII-4  (PRN 14)    
1 46826U 20078A   26293.14619999 -.00000017  00000+0  00000+0 0  9990
2 46826  53.9602 205.7161 0076893 208.3899 321.8325  2.00565045 44017
GPS BIII-5  (PRN 11)    
1 48859U 21054A   26292.65696028 -.00000056  00000+0  00000+0 0  9999
2 48859  55.1062 327.4486 0029337 232.6583 129.7638  2.00561936 39259
GPS BIII-6  (PRN 28)    
1 55268U 23009A   26291.83265792  .00000046  00000+0  00000+0 0  9990
2 55268  55.1360 143.6550 0005189 335.2652 191.6403  2.00562808 27724
GPS BIII-7  (PRN 01)    
1 62339U 24242A   26290.99441080 -.00000069  00000+0  00000+0 0  9995
2 62339  54.7874 329.1958 0020610   2.3265   1.7897  2.00556198 13725
GPS BIII-8  (PRN 21)    
1 64202U 25116A   26291.72389249 -.00000081  00000+0  00000+0 0  9991
2 64202  55.3115  26.1709 0009986 332.1612  22.6970  2.00567191 10346
GPS BIII-9  (PRN 20)    
1 67588U 26017A   26292.33985088  .00000038  00000+0  00000+0 0  9994
2 67588  55.1783  83.7757 0021025 265.8045  93.9684  2.00567938434103
GPS BIII-10 (PRN 13)    
1 68791U 26087A   26292.32468198 -.00000017  00000+0  00000+0 0  9993
2 68791  54.9490 202.8832 0022802 103.8525  89.8430  2.00551170  3328
`;

const DEFAULT_OBSERVER = { lat: 54.35, lon: 18.65, label: 'default (Gda\u0144sk)' };

const toRad = (deg: number) => (deg * Math.PI) / 180;
const toDeg = (rad: number) => (rad * 180) / Math.PI;

function parseTLE(text: string): Array<{ name: string; prn: number; rec: ReturnType<typeof satellite.twoline2satrec> }> {
  const lines = text.replace(/\r/g, '').split('\n').map(l => l.trimEnd());
  const sats: Array<{ name: string; prn: number; rec: ReturnType<typeof satellite.twoline2satrec> }> = [];
  for (let i = 0; i + 2 < lines.length; i += 3) {
    const name = lines[i];
    const l1 = lines[i + 1];
    const l2 = lines[i + 2];
    if (!name || !l1 || !l2 || !l1.startsWith('1 ') || !l2.startsWith('2 ')) continue;
    const m = name.match(/PRN\s*(\d+)/i);
    if (!m) continue;
    try {
      sats.push({ name, prn: parseInt(m[1], 10), rec: satellite.twoline2satrec(l1, l2) });
    } catch {
      // skip malformed entry
    }
  }
  return sats;
}

function SkyMapChart({ detectedSats }: SkyMapProps) {
  const [tleText, setTleText] = useState<string>(GPS_TLE_SNAPSHOT);
  const [tleSource, setTleSource] = useState<'live' | 'snapshot'>('snapshot');
  const [observer, setObserver] = useState(DEFAULT_OBSERVER);
  const [now, setNow] = useState<number>(Date.now());

  // Try a live TLE refresh; keep the snapshot on any failure (no CORS / offline).
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    fetch('https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle', { signal: ctrl.signal })
      .then(r => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then(text => {
        if (text.split('\n').length > 30) {
          setTleText(text);
          setTleSource('live');
        }
      })
      .catch(() => { /* keep snapshot */ })
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, []);

  // Observer location: browser geolocation, fallback to the default site.
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      pos => setObserver({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: 'browser location' }),
      () => { /* permission denied / unavailable: keep default */ },
      { timeout: 8000, maximumAge: 600000 },
    );
  }, []);

  // Re-propagate every 30 s so the sky map stays live.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(t);
  }, []);

  const positions = useMemo(() => {
    const date = new Date(now);
    const gmst = satellite.gstime(date);
    const observerGd = {
      latitude: toRad(observer.lat),
      longitude: toRad(observer.lon),
      height: 0.12,
    };
    const out: Array<{ prn: number; az: number; el: number }> = [];
    for (const { prn, rec } of parseTLE(tleText)) {
      try {
        const pv = satellite.propagate(rec, date);
        if (!pv.position || typeof pv.position === 'boolean' || !('x' in pv.position)) continue;
        const ecf = satellite.eciToEcf(pv.position, gmst);
        const look = satellite.ecfToLookAngles(observerGd, ecf);
        const el = toDeg(look.elevation);
        if (el <= 0) continue; // below horizon
        out.push({ prn, az: toDeg(look.azimuth), el });
      } catch {
        // propagation error: skip this satellite
      }
    }
    return out;
  }, [tleText, observer, now]);

  const detected = useMemo(() => new Set(detectedSats.map(s => s.prn)), [detectedSats]);
  const snrByPrn = useMemo(() => {
    const m = new Map<number, number | undefined>();
    for (const s of detectedSats) m.set(s.prn, s.snr);
    return m;
  }, [detectedSats]);

  // SVG polar layout: zenith in the center, N up, horizon at the rim.
  const size = 420;
  const c = size / 2;
  const R = 185;
  const pos = (az: number, el: number) => {
    const r = R * (1 - el / 90);
    const a = toRad(az);
    return { x: c + r * Math.sin(a), y: c - r * Math.cos(a) };
  };
  const ring = (el: number) => R * (1 - el / 90);
  const detectedVisible = positions.filter(p => detected.has(p.prn));

  return (
    <Box sx={{ textAlign: 'center' }}>
      <Typography variant="h6" sx={{ marginBottom: '4px' }}>
        Live Sky Map — GNSS satellites above the horizon
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block">
        Observer: {observer.lat.toFixed(3)}°, {observer.lon.toFixed(3)}° ({observer.label}) ·
        TLE: {tleSource} (epoch 2026-10-19) · gold = detected by the demodulator now
      </Typography>
      <svg width={size} height={size} style={{ maxWidth: '100%', height: 'auto' }} role="img" aria-label="Sky map">
        <circle cx={c} cy={c} r={R} fill="none" stroke="#3a4552" strokeWidth={1.5} />
        <circle cx={c} cy={c} r={ring(30)} fill="none" stroke="#2c3540" strokeWidth={1} />
        <circle cx={c} cy={c} r={ring(60)} fill="none" stroke="#2c3540" strokeWidth={1} />
        <line x1={c - R} y1={c} x2={c + R} y2={c} stroke="#2c3540" strokeWidth={1} />
        <line x1={c} y1={c - R} x2={c} y2={c + R} stroke="#2c3540" strokeWidth={1} />
        <text x={c} y={c - R - 6} fill="#8a93b5" fontSize={13} textAnchor="middle">N</text>
        <text x={c + R + 10} y={c + 4} fill="#8a93b5" fontSize={13} textAnchor="start">E</text>
        <text x={c} y={c + R + 16} fill="#8a93b5" fontSize={13} textAnchor="middle">S</text>
        <text x={c - R - 10} y={c + 4} fill="#8a93b5" fontSize={13} textAnchor="end">W</text>
        <text x={c + 5} y={c - 6} fill="#8a93b5" fontSize={11} textAnchor="start">90°</text>
        <text x={c + 5} y={c - ring(60) + 12} fill="#8a93b5" fontSize={11} textAnchor="start">60°</text>
        <text x={c + 5} y={c - ring(30) + 12} fill="#8a93b5" fontSize={11} textAnchor="start">30°</text>
        <text x={c + 5} y={c - R + 12} fill="#8a93b5" fontSize={11} textAnchor="start">0°</text>
        {positions.map(p => {
          const pt = pos(p.az, p.el);
          const isDetected = detected.has(p.prn);
          const snr = snrByPrn.get(p.prn);
          return (
            <g key={p.prn}>
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isDetected ? 7 : 4}
                fill={isDetected ? '#FFC107' : '#5f6b7a'}
                opacity={isDetected ? 1 : 0.75}
              />
              {isDetected && (
                <text x={pt.x + 10} y={pt.y + 4} fill="#FFC107" fontSize={12}>
                  {p.prn}{snr !== undefined ? ` (${snr.toFixed(1)})` : ''}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <Typography variant="caption" color="text.secondary" display="block">
        Detected: {detectedSats.length} · above horizon: {positions.length} · detected &amp; visible: {detectedVisible.length}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block">
        Run the GNSS decoder (Decode tab) to fill in the gold markers — they follow the PRNs found in the live IQ stream.
      </Typography>
    </Box>
  );
}

export default SkyMapChart;
