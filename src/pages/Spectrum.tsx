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

import React, { useState, useEffect } from 'react';

import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import Chip from '@mui/material/Chip';
import { LineChart } from '@mui/x-charts/LineChart';

import { FormControl } from '@mui/base/FormControl';

import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';

import Stack from '@mui/system/Stack';

import Label from '../components/Label';
import NumberInput from '../components/NumberInput';

import { downloadFile } from '../utils/io';

const width = 1024,
height = 500;

const tinySAUltra = { usbVendorId: 0x0483, usbProductId: 0x5740 }

const portBaudRate = {};
portBaudRate[tinySAUltra.usbProductId] = 115200;

const textEncoder = new TextEncoder();

const xAscii = 120;
const respDelimeter = [125, 123]; // }{

let port, reader;

function concatUint8Arrays(a: Uint8Array, b: Uint8Array): Uint8Array { // a, b TypedArray of same type
  var c = new Uint8Array(a.length + b.length);
  c.set(a, 0);
  c.set(b, a.length);
  return c;
}

// eslint-disable-next-line no-extend-native
(Uint8Array.prototype as any).indexOfMulti = function(searchElements, fromIndex) {
  fromIndex = fromIndex || 0;

  var index = Array.prototype.indexOf.call(this, searchElements[0], fromIndex);
  if(searchElements.length === 1 || index === -1) {
      // Not found or no other elements to check
      return index;
  }

  for(var i = index, j = 0; j < searchElements.length && i < this.length; i++, j++) {
      if(this[i] !== searchElements[j]) {
          return this.indexOfMulti(searchElements, index + 1);
      }
  }

  return(i === index + searchElements.length) ? index : -1;
};

const formatFrequency = (freq) => {
  let freqStr;
  if (freq > 1000000000) {
    freqStr = `${(freq / 1000000000).toFixed(2)} GHz`;
  } else if (freq > 1000000) {
    freqStr = `${(freq / 1000000).toFixed(2)} MHz`;
  } else if (freq > 1000) {
    freqStr = `${(freq / 1000).toFixed(2)} kHz`;
  } else {
    freqStr = `${Math.trunc(freq)} Hz`;
  }
  return freqStr;
};

const heatmap = ["05000b", "05000b", "0a000a", "0a000a", "0e000f", "0e000f", "130014", "130014", "190018", "190018", "1e001e", "1e001e", "230022", "230022", "290029", "290029", "2e002e", "2e002e", "320033", "320033", "370037", "370037", "3d003d", "3d003d", "450046", "450046", "4e014e", "4e014e", "560157", "560157", "5f005e", "5f005e", "670167", "670167", "6f0070", "6f0070", "780179", "780179", "81017b", "81017b", "870278", "870278", "8d0272", "8d0272", "94036c", "94036c", "9a0467", "9a0467", "a00560", "a00560", "a8065a", "a8065a", "ad0753", "ad0753", "b4084d", "b4084d", "bb0a47", "bb0a47", "c10a40", "c10a40", "c60b38", "c60b38", "cc0c33", "cc0c33", "d30e2c", "d30e2c", "d90d26", "d90d26", "df0f1f", "df0f1f", "e61019", "e61019", "ec1213", "ec1213", "f3120d", "f3120d", "f91306", "f91306", "fc1601", "fc1601", "fe2000", "fe2000", "ff2a01", "ff2a01", "ff3501", "ff3501", "ff3f00", "ff3f00", "ff4b01", "ff4b01", "ff5500", "ff5500", "ff5f01", "ff5f01", "ff6901", "ff6901", "ff7300", "ff7300", "ff7f00", "ff7f00", "ff8901", "ff8901", "ff9400", "ff9400", "ff9f01", "ff9f01", "ffa900", "ffa900", "ffb401", "ffb401", "ffbd02", "ffbd02", "ffc303", "ffc303", "ffc704", "ffc704", "ffcb06", "ffcb06", "ffd009", "ffd009", "ffd30a", "ffd30a", "ffd70d", "ffd70d", "ffdb0d", "ffdb0d", "ffdf10", "ffdf10", "fee310", "fee310", "ffe713", "ffe713", "ffec15", "ffec15", "ffef17", "ffef17", "fff319", "fff319", "fff61b", "fff61b", "fffb1d", "fffb1d", "feff20", "feff20", "f9fb1f", "f9fb1f", "f3f71f", "f3f71f", "eff41f", "eff41f", "eaf01f", "eaf01f", "e5ed20", "e5ed20", "dee920", "dee920", "dae720", "dae720", "d5e320", "d5e320", "cfdf20", "cfdf20", "cbdc21", "cbdc21", "c5d720", "c5d720", "c1d521", "c1d521", "bad020", "bad020", "b5cd21", "b5cd21", "afc920", "afc920", "abc621", "abc621", "a6c220", "a6c220", "a1c021", "a1c021", "9bbc20", "9bbc20", "96b823", "96b823", "93b82a", "93b82a", "91b932", "91b932", "8ebb3c", "8ebb3c", "8bbb43", "8bbb43", "8abc4c", "8abc4c", "88bd54", "88bd54", "85bd5c", "85bd5c", "83be64", "83be64", "80bf6e", "80bf6e", "7dbf75", "7dbf75", "7bc07e", "7bc07e", "7ac187", "7ac187", "78c290", "78c290", "75c298", "75c298", "72c4a1", "72c4a1", "70c5aa", "70c5aa", "6ec4b2", "6ec4b2", "6cc5ba", "6cc5ba", "6ac7c3", "6ac7c3", "6ac6c6", "6ac6c6", "72cbcd", "72cbcd", "7aced1", "7aced1", "83d1d5", "83d1d5", "8ed5d7", "8ed5d7", "97d8da", "97d8da", "a0dcdd", "a0dcdd", "a9dfe1", "a9dfe1", "b3e3e5", "b3e3e5", "bee7e9", "bee7e9", "c6e9eb", "c6e9eb", "d0eef0", "d0eef0", "d9f1f3", "d9f1f3", "e3f5f7", "e3f5f7", "edf9fa", "edf9fa", "f6fcfd", "f6fcfd", "fdffff", "fdffff"],
moveBy = 1;

let latestPowerPoints: Array<Array<Number>> = [];

function Spectrum() {
  const [portState, setPort] = useState(undefined);
  const [startFrequency, setStartFrequency] = useState(88);
  const [startFrequencyMag, setStartFrequencyMag] = useState(1000000);
  const [stopFrequency, setStopFrequency] =   useState(108);
  const [stopFrequencyMag, setStopFrequencyMag] =   useState(1000000);
  const [points, setPoints] = useState(450);
  const [powerLevels, setPowerLevels] = useState([]);
  const [powerPoints, setPowerPoints] = useState<Array<Array<Number>>>([]);

  useEffect(() => {
    latestPowerPoints = powerPoints;
  }, [powerPoints]);

  const [currLvl, setCurrLvl] = useState("N/A");

  const xPoints: Array<Number> = [];
  const span = (stopFrequency*stopFrequencyMag - startFrequency*startFrequencyMag) / points;
  for(let i=0;i<points; i++) {
    xPoints.push(startFrequency*startFrequencyMag + span * i);
  }

  const filters = [tinySAUltra];

  const reset = () => {
    setPowerLevels([]);
    setPowerPoints([]);

    const canvas = document.getElementById("canvas") as HTMLCanvasElement,
    canvasContext = canvas.getContext("2d") as CanvasRenderingContext2D;
    canvasContext.clearRect(0, 0, canvas.width, canvas.height);
  };
  const download = () => {
    let lines = ''
    for(let i=0; i<powerPoints.length; i++) {
      lines += powerPoints[i].join(',');
      lines += '\n';
    }
    downloadFile(`spectrum-${new Date().toISOString()}.csv`, 'data:text/csv;charset=UTF-8,' + encodeURIComponent(lines));
  };

  const drawLines = (powers) => {
    // min 90, mx 10, add case for values higher 
    let powerLevels: Array<Number> = []
    for(let i=0; i<powers.length; i++) {
      if(powers[i] <= -100) {
        powerLevels.push(0);
      } else if(powers[i] >= 10) {
        powerLevels.push(heatmap.length-1);
      } else {
        const range = 100 + 10
        const bucketSize = (range * 1.0) / heatmap.length
        const powerVal = powers[i] + 100;
        powerLevels.push(Math.floor(powerVal / bucketSize));
      }
    }
    setPowerLevels(powers);
    const canvas = document.getElementById("canvas") as HTMLCanvasElement,
    canvasContext = canvas.getContext("2d") as CanvasRenderingContext2D;
    canvasContext.drawImage(canvasContext.canvas, 0, 0, width, height - moveBy, 0, moveBy, width, height - moveBy);
    for(var i = 0; i < powerLevels.length; i++) {
      var mag = powerLevels[i];
      canvasContext.fillStyle = '#'+heatmap[mag as any];
      const pointVals = Math.floor(width/points);
      for(let j=0;j<pointVals; j++) {
        canvasContext.fillRect(i*pointVals+j, 0, 1, moveBy);
      }
    }
  };

  const processResponse = (response) => {
    const powers: Array<Number> = []
    for(let i=0; i<points; i++) {
      const x_char = response[3 * i]  // This should be 'x'
      if(x_char !== xAscii) {
        console.warn("malformed response, skipping");
        return;
      }

      const lsb = response[3 * i + 1]
      const msb = response[3 * i + 2]
      const value = (lsb + msb*256)
      const dbm = (value / 32.0) - 174 // convert the value to dBm (TinySA Ultra adjustment), see https://groups.io/g/tinysa/topic/97630860
      // for tinySA:  level_dBm  = ((byte3 + (byte4 * 256)) / 32) - 128

      powers.push(dbm)
    }

    drawLines(powers);
    setPowerPoints([...latestPowerPoints, powers])
  }

  let responseBuffer: Uint8Array = new Uint8Array([]);

  const readLoop = async () => {
    const writer = port.writable.getWriter();

    // see https://tinysa.org/wiki/pmwiki.php?n=Main.USBInterface
    let command = `abort on\r`;
    console.log(command)
    writer.write(textEncoder.encode(command));
  
    // see https://github.com/mykhailopylyp/TinySAScanner/blob/main/scan.py#L35
    command = `scanraw ${startFrequency*startFrequencyMag} ${stopFrequency*stopFrequencyMag} ${points} 3\r`;
    console.log(command)
    writer.write(textEncoder.encode(command));
    writer.releaseLock();

    while (port && port.readable) {
      try {
        reader = port.readable.getReader();
        for (;;) {
          // we don't pass own buffer as we need to keep buffers to find response
          const {value, done} = await reader.read();
  
          if (value) {
            responseBuffer = concatUint8Arrays(responseBuffer, value);
            // responseBuffer = new Uint8Array([ ...responseBuffer, ...value ]);

            let opening = -1, closing = -1;

            do {
              opening = (responseBuffer as any).indexOfMulti(respDelimeter);
              if(opening !== -1) {
                closing = (responseBuffer as any).indexOfMulti(respDelimeter, opening+2);
                if(closing !== -1) {
                  if (closing - opening - 2 !== points * 3) {
                    console.warn("Incorrect response size: " + (closing - opening - 2) + ". Should be: " + (points * 3))
                  } else {
                    processResponse(responseBuffer.slice(opening+2, closing))
                  }
                  responseBuffer = responseBuffer.slice(closing); // leave out for next batch
                }
              }
            } while(opening !== -1 && closing !== -1)
          }
          if (done) {
            break;
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        if (reader) {
          reader.releaseLock();
          reader = undefined;
        }
      }
    }
  };

  const defaultOptions = {
    "baudRate": 115200,
    "dataBits": 8,
    "parity": "none",
    "stopBits": 1,
    "flowControl": "none",
    "baudrate": 115200,
    "databits": 8,
    "stopbits": 1,
    "rtscts": false
};

const handleMouseMove = (event) => {
  const offsetX = event.nativeEvent.touches ? event.nativeEvent.touches[0].pageX : event.nativeEvent.offsetX
  const freq = startFrequency*startFrequencyMag + ((stopFrequency*stopFrequencyMag - startFrequency*startFrequencyMag)*(offsetX/width))
  const freqStr = formatFrequency(freq);

  setCurrLvl(freqStr)
};

return (
  <Container maxWidth="lg">
    <Box display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="10vh"
      sx={{ marginTop: '30px' }}>

      <Stack spacing={2} sx={{ marginRight: '30px' }}>
        <ButtonGroup variant="contained" aria-label="Basic button group">
        <Button disabled={portState !== undefined} onClick={ async () => {
        port = await navigator.serial.requestPort({ filters });
        const productId = port.getInfo().usbProductId;
        await port.open({...defaultOptions, baudRate: portBaudRate[productId] });
        setPort(port);
        console.log("connected")
        console.log(port)

        reset();

        readLoop();
      }}>Connect</Button>
      <Button disabled={portState === undefined} onClick={async ()=>{
      const writer = port.writable.getWriter();
        
      const command = `abort\r`;
      console.log(command)
      writer.write(textEncoder.encode(command));
      writer.releaseLock();

      const localPort = port;
      port = undefined;
      setPort(undefined)
      if (reader) {
        await reader.cancel();
        reader = undefined;
      }
      
      if (localPort) {
        try {
          await localPort.close();
        } catch (e) {
          console.error(e);
        }
      }
      }}>Disconnect</Button>
        </ButtonGroup>
        <Button onClick={reset}>Reset</Button>
        <Button onClick={download}>Download spectrum</Button>
      </Stack>

    <FormControl defaultValue="" >
      <Label>Points</Label>
      <NumberInput
        min={3}
        max={450}
        disabled={portState !== undefined}
        aria-label="Points"
        placeholder="Type a number…"
        value={points}
        onChange={(_, val) => setPoints(val ?? 450)}
      />
    </FormControl>
    <FormControl defaultValue="">
      <Label>Start frequency [Hz]</Label>
      <Stack direction="row" >
        <NumberInput
          disabled={portState !== undefined}
          aria-label="Start frequency"
          placeholder="Type a number…"
          value={startFrequency}
          onChange={(_, val) => setStartFrequency(val ?? 88)}
        />
        <Select
          disabled={portState !== undefined}
          value={startFrequencyMag}
          onChange={(event) => setStartFrequencyMag(Number(event.target.value))}
          sx={{ marginRight: '15px' }}
        >
          <MenuItem value={1}>Hz</MenuItem>
          <MenuItem value={1000}>kHz</MenuItem>
          <MenuItem value={1000000}>MHz</MenuItem>
          <MenuItem value={1000000000}>GHz</MenuItem>
        </Select>
      </Stack>
    </FormControl>
    
    <FormControl defaultValue="">
      <Label>Stop frequency [Hz]</Label>
      <Stack direction="row">
        <NumberInput
          disabled={portState !== undefined}
          aria-label="Stop frequency"
          placeholder="Type a number…"
          value={stopFrequency}
          onChange={(event, val) => setStopFrequency(val ?? 108)}
        />
        <Select
          disabled={portState !== undefined}
          value={stopFrequencyMag}
          onChange={(event) => setStopFrequencyMag(Number(event.target.value))}
        >
          <MenuItem value={1}>Hz</MenuItem>
          <MenuItem value={1000}>kHz</MenuItem>
          <MenuItem value={1000000}>MHz</MenuItem>
          <MenuItem value={1000000000}>GHz</MenuItem>
        </Select>
      </Stack>
    </FormControl>
    
  </Box>
  <Box
    display='flex'
    justifyContent='center'
  >
    <LineChart
      width={width+80}
      height={300}
      slotProps={{ legend: { hidden: true } }}
      series={[{ data: powerLevels, label: 'dB',  showMark: false, color: '#cc0052' }]}
      xAxis={[{ scaleType: 'linear', data: xPoints }]}
      sx={{ }}
    />
  </Box>
  <Box
    display='flex'
    justifyContent='center'
    sx={{ paddingLeft: '30px' }}
  >
    <canvas
      id="canvas" 
      width={width}
      height={height}
      onMouseMove={handleMouseMove}
      onTouchMove={handleMouseMove}
      onMouseOut={()=> setCurrLvl("N/A")}
      onTouchEnd={()=> setCurrLvl("N/A")}
      ></canvas>
  </Box>
  <Stack direction="row" spacing={1}>
      <Chip label={`Current Frequency: ${currLvl}`} variant="outlined" />
  </Stack>
</Container>
);
}

export default Spectrum;
