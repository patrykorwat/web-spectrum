# Why SDRPlay Stream Activation Fails - Root Cause Analysis

## The Crash Chain

```
gr-osmosdr (GNSS-SDR)
    ↓ calls
soapy_source_c::set_iq_balance_mode()
    ↓ forwards to
SoapySDR::Device::setIQBalance()
    ↓ calls
SoapySDRPlay module
    ↓ throws
NOT_SUPPORTED exception
    ↓ propagates back to
GNSS-SDR
    ↓ result
CRASH (program exit after ~2 seconds)
```

## Technical Details

### The Problem Code
In `gr-osmosdr/lib/soapy/soapy_source_c.cc`, there's hardcoded initialization:

```cpp
// Initialize IQ balance correction (ALWAYS called during setup)
set_iq_balance_mode(true);  // ← THIS LINE CAUSES THE CRASH
```

### Why It Fails
The SoapySDR-SDRplay module (`SoapySDRPlay`) does **not implement** the `setIQBalance()` function. When gr-osmosdr calls it, Soapy throws a `NOT_SUPPORTED` exception which isn't caught, causing GNSS-SDR to terminate.

### Evidence from Logs
Every test showed the same pattern:
```
[INFO] Using format CF32.
Actual RX Rate: 2.048e+06 [SPS]...
Actual RX Freq: 1.57542e+09 [Hz]...
PLL Frequency tune error: 0 [Hz]...
soapy_source_c::set_iq_balance_mode() not supported  ← HERE
Total GNSS-SDR run time: 2.xxxxx [seconds]
GNSS-SDR program ended.
```

The crash happens **after** successful device initialization but **before** stream activation.

## Why Attempted Fixes Didn't Work

### 1. SignalSource.iq_balance_mode=0
```
Result: Created flowgraph wiring error
Reason: This parameter affects GNU Radio flowgraph structure, 
        not the gr-osmosdr driver behavior
Error: "output 1 is not connected internally"
```

### 2. Different Device Modes (ST/DT/MA)
```
Result: Same crash on all modes
Reason: set_iq_balance_mode() is called regardless of device type
```

### 3. Different osmosdr_args
```
Result: Same crash
Reason: The call happens in gr-osmosdr init code, before args are processed
```

## The Real Solutions

### Option 1: Patch gr-osmosdr (Best for permanent fix)
Modify `gr-osmosdr/lib/soapy/soapy_source_c.cc`:
```cpp
// Wrap in try-catch
try {
    set_iq_balance_mode(true);
} catch (const std::exception& e) {
    // Ignore if not supported
    std::cerr << "IQ balance not supported, continuing..." << std::endl;
}
```

Then rebuild gr-osmosdr:
```bash
brew reinstall gr-osmosdr --build-from-source
```

###Option 2: Patch SoapySDRPlay (Alternative)
Add a dummy implementation in SoapySDRPlay:
```cpp
void SoapySDRPlay::setIQBalance(const int direction, const size_t channel, const std::complex<double> &balance) {
    // Dummy implementation - do nothing
    return;
}
```

### Option 3: Use File-Based Mode (Current workaround)
```bash
./start_all.sh file
```

This bypasses gr-osmosdr entirely by:
1. Recording IQ samples to file via Python/SoapySDR
2. GNSS-SDR reads from file using File_Signal_Source
3. No gr-osmosdr involved = no crash

## Why File Mode Works

```
File Mode:
SDRPlay → Python/SoapySDR → /tmp/file → GNSS-SDR (File_Signal_Source)
         ↑ Direct SoapySDR API, no gr-osmosdr

Live Mode (broken):
SDRPlay → gr-osmosdr (soapy_source_c) → GNSS-SDR
         ↑ CRASH HERE on set_iq_balance_mode()
```

## Verification Steps

### Confirm SoapySDR-SDRplay doesn't support IQ balance:
```bash
SoapySDRUtil --probe="driver=sdrplay" | grep -i "iq"
```
Result: Shows `IQ Correction` as a setting, but `setIQBalance()` method not implemented

### Confirm device is functional:
```bash
SoapySDRUtil --find="driver=sdrplay"
```
Result: Device found and accessible

### Confirm gr-osmosdr calls the function:
Check logs for: `soapy_source_c::set_iq_balance_mode() not supported`

## Conclusion

The stream activation doesn't technically "fail" - the crash happens **before** stream activation during the IQ balance setup phase. The device, driver, and sample rate are all correct. The issue is purely a software compatibility problem between gr-osmosdr's expectations and SoapySDRPlay's implementation.

**Recommendation**: Use file-based mode until gr-osmosdr or SoapySDRPlay is patched.
