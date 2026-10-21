/*!
meshuga/web-spectrum
Copyright (C) 2024 Patryk Orwat

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// Web Worker wrapper around GNSSDemodulator: acquisition takes seconds and
// must never run on the UI thread (it froze Chrome while decoding).

import { Protocol } from '../protocol';
import { GNSSDemodulator } from './demodulator';

const demod = new GNSSDemodulator();
const ctx: any = globalThis as any;

ctx.onmessage = (e: MessageEvent) => {
  const data = e.data as { type: string; protocol?: Protocol; buffer?: ArrayBuffer };
  if (data.type === 'setProtocol' && data.protocol !== undefined) {
    demod.setProtocol(data.protocol as Protocol);
  } else if (data.type === 'samples' && data.buffer) {
    const result = demod.processSamples(data.buffer);
    if (result) {
      ctx.postMessage({ type: 'result', result });
    }
  }
};
