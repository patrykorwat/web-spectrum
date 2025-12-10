# GNSS-SDR Osmosdr Fix - December 2025

## Problem
GNSS-SDR was crashing after ~2 seconds when using direct Osmosdr access to SDRPlay.
Two main issues were identified:

1. **IQ Balance Mode Crash**: `soapy_source_c::set_iq_balance_mode() not supported`
   - gr-osmosdr tries to set IQ balance mode
   - SoapySDR-SDRplay doesn't support this function
   - Causes C++ exception and immediate program termination

2. **Stream Activation Failure**: `activateStream() - Init() failed: sdrplay_api_Fail`
   - SDRPlay API initialization fails
   - No data flows from device
   - Process stays alive but doesn't collect samples

## Solution

### Fix Applied (gnss_sdr_sdrplay_direct.conf)
Added configuration parameter to disable IQ balance mode:
```
SignalSource.iq_balance_mode=0
```

Also removed:
```
; SignalSource.samples=0  ; Commented out - was causing immediate exit
```

### Result
- ✅ GNSS-SDR no longer crashes
- ✅ Process runs continuously  
- ❌ Still no data flow due to stream activation failure

## Recommendation

**Use file-based mode instead:**

```bash
./start_all.sh file
```

This mode:
1. Records IQ samples from SDRPlay to `/tmp/gps_iq_samples.dat`
2. GNSS-SDR reads from file (avoids osmosdr driver issues)
3. Provides identical functionality without driver problems

## Alternative: Fix Osmosdr Driver (Advanced)

To fully fix live mode, you would need to:
1. Rebuild gr-osmosdr with SDRPlay API compatibility patches
2. OR use a different GNSS-SDR source (e.g., File_Signal_Source with named pipe)
3. OR update SDRPlay API to a compatible version

## Files Modified
- `gnss_sdr/gnss_sdr_sdrplay_direct.conf` - Added iq_balance_mode=0 fix
