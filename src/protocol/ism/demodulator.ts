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

import { Protocol, ProtocolToMsgLength } from "../protocol";

const MAG_LUT = new Uint16Array(129 * 129 * 2);

// Populate the I/Q -> Magnitude lookup table. It is used because sqrt or
// round may be expensive and may vary a lot depending on the libc used.
//
// We scale to 0-255 range multiplying by 1.4 in order to ensure that every
// different I/Q pair will result in a different magnitude value, not losing
// any resolution.
for (let i = 0; i <= 128; i++) {
    for (let q = 0; q <= 128; q++) {
        MAG_LUT[i * 129 + q] = Math.round(Math.sqrt(i * i + q * q) * 360);
    }
}

// Our precondition for the measurments is that transmision is quantized into slices of 1ms.
// Usually, 1 is of length 240 us and 0 of 640 us, which leaves max gap of size 760 us.
// Below approximations are set to allow for correct detection of signals while sweeping over long  
const oneOOKwidth = 0.3; // [ms] equal or smaller is one, wider is zero
const maxGap = 1; // [ms] max gap equal to typical OOK signal length

export class Demodulator {
    constructor(private avgSamples: number = 128) {}

    private mag: Uint16Array | undefined;

    process(data, size, onMsg) {
        if (!this.mag) this.mag = new Uint16Array(size / 2);
        this.computeMagnitudeVector(data, size);

        const totalSamples = size / 2;

        const k = new Uint16Array(totalSamples/this.avgSamples);
        for (let i = 0; i < totalSamples/this.avgSamples; i++) {
            let val = 0;
            for (let j = 0; j < this.avgSamples; j++) {
                val += this.mag[i*this.avgSamples+j];
            }
            k[i] = val / this.avgSamples;
        }
        onMsg(k);
    }

    private computeMagnitudeVector = (data, size) => {
        for (let j = 0; j < size; j += 2) {
            let i = data[j] - 127;
            let q = data[j + 1] - 127;

            if (i < 0) i = -i;
            if (q < 0) q = -q;
            this.mag![j / 2] = MAG_LUT[i * 129 + q];
        }
    };

    detectPulses(protocol: Protocol, responses: Array<number>, stepMSecond: number, triggerLevel: number) {
        const expectedLength = ProtocolToMsgLength.get(protocol)!!;

        const pulsePackages: any = []; // contains auto detected groups of bits;

        // 0 - idle
        // 1 - pulse
        // 2 - gap
        let currentState = 0;

        let dataCounter;
        let packageData: any;
        let gapCounter;

        for(let i=0; i< responses.length; i++) {
            if (currentState === 0) {
            if (responses[i] < triggerLevel) {
                // it's idle state and idle state detected, continue
                continue
            } else {
                // new data package detected, new pulse must be initiated and package must be established
                currentState = 1;
                dataCounter = 1;
                packageData = [];
            }
            } else if (currentState === 1) {
            if (responses[i] < triggerLevel) {
                // no data received, it's a gap, can transform the peak into a bit
                currentState = 2;
                gapCounter = 1;
                if (dataCounter * stepMSecond <= oneOOKwidth) {
                // 1 bit detected, need to add to a package
                packageData.push("1");
                } else {
                // 0 detected, need to add to a package
                packageData.push("0");
                }
            } else {
                // we are still detecting a pulse, need to count the puse
                dataCounter++;
            }
            } else if (currentState === 2) {
            // gap detected, can continue gap, end transmission or detect new signal
            if (responses[i] < triggerLevel) {
                // no data received
                if (gapCounter * stepMSecond > maxGap) {
                // max gap exceeded with no new signal, end of transmission
                currentState = 0;
                pulsePackages.push(packageData);
                } else {
                // still in gap period
                gapCounter++;
                }
            } else {
                // we detected a new pulse
                currentState = 1;
                dataCounter = 0;
            }
            } else {
            console.warn("Unknown state, decoding logic is broken")
            break
            }
        }

        console.log("Found unfinished package in state: ", currentState, ", data: ", packageData)

        return this.decodePulseGroups(pulsePackages, expectedLength);
    };

    private decodePulseGroups(pulsePackages: Array<Array<number>>, expectedLength: number) {
        const responses: any = [];
        // remove leading zero from package
        for (let i=0; i< pulsePackages.length; i++) {
            // simple pre-abmle for GateTX type of a message (in Flipper nomenclature)
            pulsePackages[i].shift();

            // the received message was incomplete, we skip message
            if (pulsePackages[i].length !== expectedLength) {
                continue
            }

            const decimalOutput = parseInt(pulsePackages[i].join(""), 2);
            const hexOutput = decimalOutput.toString(16).toUpperCase();
            responses.push({
                time: new Date(),
                msg: hexOutput,
                decoded: hexOutput,
              });
        }
        return responses;
    };
}