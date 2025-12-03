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

import './App.css';

import React, { useState } from 'react';

import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import MuiDrawer, { drawerClasses } from '@mui/material/Drawer';
import { styled } from '@mui/material/styles';

import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';


import TroubleshootIcon from '@mui/icons-material/Troubleshoot';
import EqualizerIcon from '@mui/icons-material/Equalizer';

import Typography from '@mui/material/Typography';
import Breadcrumbs, { breadcrumbsClasses } from '@mui/material/Breadcrumbs';
import NavigateNextRoundedIcon from '@mui/icons-material/NavigateNextRounded';

import Spectrum from './pages/Spectrum.tsx';
import Decoder from './pages/Decoder.tsx';
import RtlDecoder from './pages/RtlDecoder.tsx';
import SdrPlayDecoder from './pages/SdrPlayDecoder.tsx';
import { Button } from '@mui/material';

// eslint-disable-next-line no-extend-native
Uint8Array.prototype.indexOfMulti = function(searchElements, fromIndex) {
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

// eslint-disable-next-line no-extend-native
Uint8Array.prototype.endsWith = function(suffix) {
  if(this.length<suffix.length) {
    return false;
  }
  for(var i = this.length - suffix.length, j = 0; i < this.length; i++, j++) {
      if(this[i] !== suffix[j]) {
          return false;
      }
  }
  return true;
};

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const drawerWidth = 240;

const Drawer = styled(MuiDrawer)({
  width: drawerWidth,
  flexShrink: 0,
  boxSizing: 'border-box',
  mt: 10,
  [`& .${drawerClasses.paper}`]: {
    width: drawerWidth,
    boxSizing: 'border-box',
  },
});

const StyledBreadcrumbs = styled(Breadcrumbs)(({ theme }) => ({
  margin: theme.spacing(1, 0),
  [`& .${breadcrumbsClasses.separator}`]: {
    color: ((theme as any).vars || theme).palette.action.disabled,
    margin: 1,
  },
  [`& .${breadcrumbsClasses.ol}`]: {
    alignItems: 'center',
  },
}));

const mainListItems = [
  { group: 'TinySA Ultra'},
  { text: 'Spectrum', icon: <EqualizerIcon /> },
  { text: 'Decode', icon: <TroubleshootIcon /> },
  { group: 'RTL-SDR'},
  { text: 'Decode', icon: <TroubleshootIcon /> },
  { group: 'SDRPlay'},
  { text: 'Decode', icon: <TroubleshootIcon /> },
];

function App() {
  const [menuSelection, setMenuSelection] = useState(1);

return (
  <ThemeProvider theme={darkTheme}>
    <CssBaseline />
    <Box sx={{ display: 'flex' }}>
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          [`& .${drawerClasses.paper}`]: {
            backgroundColor: 'rgb(28, 31, 32)',
          },
        }}
      >
        <Stack sx={{ flexGrow: 1, p: 1, justifyContent: 'space-between' }}>
          <List dense>
            {mainListItems.map((item, index) => (
              <ListItem key={index} disablePadding sx={{ display: 'block' }}>
                {item.group === undefined ?
                  <ListItemButton selected={index === menuSelection} onClick={() => setMenuSelection(index)}>
                    <ListItemIcon>{item.icon}</ListItemIcon>
                    <ListItemText primary={item.text} />
                  </ListItemButton>
                : <><b>{item.group}</b><Divider /></>}
              </ListItem>
            ))}
          </List>
        </Stack>
        <Stack
        direction="row"
        sx={{
          p: 2,
          gap: 1,
          alignItems: 'center',
          borderTop: '1px solid',
          borderColor: 'divider',
        }}
        >
          <Box sx={{ mr: 'auto' }}>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              Web Spectrum
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              <Button onClick={()=>window.open('https://github.com/meshuga/web-spectrum', '_blank')}>GitHub</Button>
            </Typography>
          </Box>
        </Stack>
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={() => ({
          flexGrow: 1,
          overflow: 'auto',
        })}
      >
        <Stack
          spacing={2}
          sx={{
            alignItems: 'center',
            mx: 3,
            pb: 5,
            mt: { xs: 8, md: 0 },
          }}
        >
          <Stack
            direction="row"
            sx={{
              display: { xs: 'none', md: 'flex' },
              width: '100%',
              alignItems: { xs: 'flex-start', md: 'center' },
              justifyContent: 'space-between',
              maxWidth: { sm: '100%', md: '1700px' },
              pt: 1.5,
            }}
            spacing={2}
          >
            <StyledBreadcrumbs
              aria-label="breadcrumb"
              separator={<NavigateNextRoundedIcon fontSize="small" />}
            >
              <Typography variant="body1">Web Spectrum</Typography>
              <Typography variant="body1">
                {menuSelection < 3 ? 'TinySA Ultra' : (menuSelection < 5 ? 'RTL-SDR' : 'SDRPlay')}
              </Typography>
              <Typography variant="body1" sx={{ color: 'text.primary', fontWeight: 600 }}>
                {mainListItems[menuSelection].text}
              </Typography>
            </StyledBreadcrumbs>
          </Stack>
          { menuSelection === 1 ? <Spectrum /> : (menuSelection === 2 ? <Decoder /> : (menuSelection === 4 ? <RtlDecoder /> : (menuSelection === 6 ? <SdrPlayDecoder /> : <RtlDecoder />))) }          
        </Stack>
      </Box>
    </Box>
  </ThemeProvider>
);
}

export default App;
