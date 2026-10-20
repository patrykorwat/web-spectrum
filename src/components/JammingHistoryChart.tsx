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

import React from 'react';
import { LineChart } from '@mui/x-charts/LineChart';
import { Box, Typography } from '@mui/material';

export interface JammingHistoryPoint {
  time: number;          // epoch ms of the update
  noiseFloorDb: number;  // relative dB (not calibrated dBm)
  totalPowerDb: number;  // relative dB
  cn0: number;           // average C/N0 of tracking satellites (0 = none)
  sats: number;          // number of tracking satellites
}

/**
 * Time series of the key jamming observables.
 *
 * Jamming signature: C/N0 drops on ALL satellites at the same time while the
 * noise floor / total power rises. A C/N0 drop on single satellites with a
 * stable noise floor points to antenna/multipath issues instead of jamming.
 */
export default function JammingHistoryChart({ history }: { history: JammingHistoryPoint[] }) {
  if (history.length < 2) return null;

  const data = history.slice().reverse(); // oldest -> newest
  const cn0Data = data.map(p => (p.cn0 > 0 ? p.cn0 : NaN));

  return (
    <Box sx={{ marginTop: '15px' }}>
      <Typography variant="h6" sx={{ marginBottom: '10px', fontSize: '0.95em' }}>
        📊 Jamming Observables History
      </Typography>
      <LineChart
        skipAnimation={true}
        width={900}
        height={220}
        series={[
          {
            data: data.map(p => p.totalPowerDb),
            label: 'Total power (dB, rel.)',
            color: '#FF7043',
            showMark: false,
            yAxisKey: 'leftAxis'
          },
          {
            data: data.map(p => p.noiseFloorDb),
            label: 'Noise floor (dB, rel.)',
            color: '#8D6E63',
            showMark: false,
            yAxisKey: 'leftAxis'
          },
          {
            data: cn0Data,
            label: 'Avg C/N0 (dB-Hz)',
            color: '#2196F3',
            showMark: false,
            yAxisKey: 'rightAxis'
          },
          {
            data: data.map(p => p.sats),
            label: 'Satellites',
            color: '#4CAF50',
            showMark: false,
            yAxisKey: 'rightAxis'
          }
        ]}
        xAxis={[{
          data: data.map((_, i) => i),
          label: 'Time (oldest → newest)'
        }]}
        yAxis={[
          {
            id: 'leftAxis',
            scaleType: 'linear',
            label: 'Power (dB, rel.)'
          },
          {
            id: 'rightAxis',
            scaleType: 'linear',
            label: 'C/N0 (dB-Hz) / sats'
          }
        ]}
        rightAxis="rightAxis"
        slotProps={{
          legend: {
            direction: 'row',
            position: { vertical: 'top', horizontal: 'middle' },
            padding: 0
          }
        }}
        margin={{ left: 60, right: 60, top: 40, bottom: 40 }}
      />
      <Typography variant="caption" sx={{ display: 'block', marginTop: '5px', color: 'text.secondary', textAlign: 'center' }}>
        Jamming: C/N0 drops on ALL satellites while the noise floor rises. Single-satellite dips with a flat floor = antenna/multipath, not jamming.
      </Typography>
    </Box>
  );
}
