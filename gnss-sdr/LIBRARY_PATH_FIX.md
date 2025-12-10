# SDRplay Library Path Fix

## Problem

When running `SoapySDRUtil --find="driver=sdrplay"`, you see:

```
[ERROR] SoapySDR::loadModule(/opt/homebrew/lib/SoapySDR/modules0.8/libsdrPlaySupport.so)
  dlopen() failed: dlopen(...) Library not loaded: @rpath/libsdrplay_api.so.3
No devices found! driver=sdrplay
```

## Cause

The SoapySDR SDRplay module can't find `libsdrplay_api.so.3` because:
- The library is in `/usr/local/lib/`
- But `DYLD_LIBRARY_PATH` environment variable is not set
- macOS dynamic linker can't find the library via `@rpath`

## Solution

You need to add `/usr/local/lib` to your `DYLD_LIBRARY_PATH`.

### Quick Fix (Current Terminal Session Only)

```bash
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
```

Then test:
```bash
SoapySDRUtil --find="driver=sdrplay"
```

You should now see your SDRplay device(s) listed!

### Permanent Fix

**For zsh (macOS default):**

1. Edit your `~/.zshrc`:
   ```bash
   sudo nano ~/.zshrc
   ```

2. Add this line at the end:
   ```bash
   export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
   ```

3. Save and reload:
   ```bash
   source ~/.zshrc
   ```

**For bash:**

1. Edit your `~/.bash_profile`:
   ```bash
   nano ~/.bash_profile
   ```

2. Add the same line:
   ```bash
   export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
   ```

3. Save and reload:
   ```bash
   source ~/.bash_profile
   ```

### Automated Script

We provide a script that does this automatically:

```bash
cd gnss-sdr
chmod +x fix_sdrplay_library_path.sh
./fix_sdrplay_library_path.sh
```

**Note:** If you get "Permission denied" on `.zshrc`, it means the file is owned by root. Use the manual method above with `sudo`.

## Verification

After applying the fix, verify it works:

```bash
# Should show your SDRplay device(s)
SoapySDRUtil --find="driver=sdrplay"
```

Expected output:
```
######################################################
##     Soapy SDR -- the SDR abstraction library     ##
######################################################

Found device 0
  driver = sdrplay
  label = SDRplay Dev0 RSPduo 2305039634 - Single Tuner
  mode = ST
  serial = 2305039634

Found device 1
  driver = sdrplay
  label = SDRplay Dev1 RSPduo 2305039634 - Dual Tuner
  ...
```

## Why This is Needed

1. **SDRplay API** is installed in `/usr/local/lib/`
2. **SoapySDR module** (`libsdrPlaySupport.so`) is in `/usr/local/lib/SoapySDR/modules0.8/`
3. The module has a dynamic dependency on `@rpath/libsdrplay_api.so.3`
4. macOS needs `DYLD_LIBRARY_PATH` to resolve `@rpath` to `/usr/local/lib/`

## Impact on Live Mode

Without this fix:
- `./start_all.sh live` will **FAIL**
- GNSS-SDR won't be able to access SDRplay via Osmosdr
- You'll see errors like:
  ```
  [Osmosdr_Signal_Source] Cannot open SDRplay device
  ```

With this fix:
- `./start_all.sh live` works perfectly
- GNSS-SDR can access SDRplay directly via Osmosdr
- Real-time satellite tracking works

## Alternative Solutions

### 1. Create Symlink in Homebrew Path

```bash
sudo ln -s /usr/local/lib/libsdrplay_api.so.3 /opt/homebrew/lib/libsdrplay_api.so.3
```

### 2. Modify SoapySDR Module RPATH

```bash
# Advanced - modifies the binary
install_name_tool -change @rpath/libsdrplay_api.so.3 \
  /usr/local/lib/libsdrplay_api.so.3 \
  /usr/local/lib/SoapySDR/modules0.8/libsdrPlaySupport.so
```

**We don't recommend these** - the environment variable approach is cleaner and safer.

## Troubleshooting

### "Permission denied" when editing .zshrc

Your `.zshrc` is owned by root. Use:
```bash
sudo nano ~/.zshrc
```

Or fix permissions:
```bash
sudo chown $USER ~/.zshrc
```

### Still showing "No devices found"

1. **Check if SDRplay is connected:**
   ```bash
   lsusb | grep -i sdrplay
   # or
   system_profiler SPUSBDataType | grep -i sdrplay
   ```

2. **Check if API is running:**
   ```bash
   ps aux | grep sdrplay_apiService
   ```

3. **Restart API service:**
   ```bash
   sudo killall sdrplay_apiService
   # It will auto-restart
   sleep 2
   ps aux | grep sdrplay_apiService
   ```

4. **Check if another program is using it:**
   ```bash
   lsof | grep sdrplay
   ```

### Library path not persisting

Make sure you:
1. Added the `export` line to the correct file (`.zshrc` for zsh, `.bash_profile` for bash)
2. Reloaded the file: `source ~/.zshrc`
3. **Restarted your terminal** (sometimes required)

### Verify environment variable

```bash
echo $DYLD_LIBRARY_PATH
# Should include: /usr/local/lib
```

## See Also

- [OSMOSDR_MONITORING.md](OSMOSDR_MONITORING.md) - Complete monitoring documentation
- [gnss_sdr_sdrplay_direct.conf](gnss_sdr_sdrplay_direct.conf) - Live mode configuration
- [SoapySDR Documentation](https://github.com/pothosware/SoapySDR/wiki)
