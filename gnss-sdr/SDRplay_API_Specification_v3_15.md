# SDRplay API Specification v3.15

## Software Defined Radio API
**SDRplay Limited**

---

## Revision History

| Revision | Release Date | Reason for Change | Originator |
|----------|--------------|-------------------|------------|
| Up to 2.x | Various | Support up to 2.x API (See old API documentation) | APC |
| 3.0 | 19th June 2018 | Support 3.0 API (Service/Daemon) | APC |
| 3.01 | 21st August 2018 | Improvements for dual tuner and exit handling | APC |
| 3.02 | 14th March 2019 | New AGC scheme. Fixes to RSP1/RSPduo control | APC |
| 3.03 | 9th April 2019 | Updated heartbeat & comms systems | APC |
| 3.04 | 8th July 2019 | Updated for Diversity and other improvements | APC |
| 3.06 | 22nd November 2019 | Added RSPdx Support and extra error reporting | APC |
| 3.07 | 8th June 2020 | Added debug function, fixed RSP1A Bias-T operation | APC |
| 3.08 | 13th September 2021 | Low power mode check, DeviceT valid flag, master/slave DAB mode | APC |
| 3.09 | 23rd November 2021 | RSPdx 50 MHz band, bug fixes including start-up & recovery state conditions | APC |
| 3.10 | 10th May 2022 | User mode (WinUSB) driver + ARM64 support | APC |
| 3.11 | 5th September 2022 | Fixes to surprise removal and service start-up | APC |
| 3.12 | 8th November 2022 | Updates to fsChanged and grChanged flags | APC |
| 3.13 | 10th August 2023 | Internal only | APC |
| 3.14 | 26th January 2024 | Added RSP1B Support | APC |
| 3.15 | 10th May 2024 | Added RSPdxR2 Support | APC |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [API Data Types](#2-api-data-types)
   - 2.1 [sdrplay_api.h](#21-sdrplay_apih)
   - 2.2 [sdrplay_api_rx_channel.h](#22-sdrplay_api_rx_channelh)
   - 2.3 [sdrplay_api_dev.h](#23-sdrplay_api_devh)
   - 2.4 [sdrplay_api_tuner.h](#24-sdrplay_api_tunerh)
   - 2.5 [sdrplay_api_control.h](#25-sdrplay_api_controlh)
   - 2.6 [sdrplay_api_rsp1a.h](#26-sdrplay_api_rsp1ah)
   - 2.7 [sdrplay_api_rsp2.h](#27-sdrplay_api_rsp2h)
   - 2.8 [sdrplay_api_rspDuo.h](#28-sdrplay_api_rspduoh)
   - 2.9 [sdrplay_api_rspDx.h](#29-sdrplay_api_rspdxh)
   - 2.10 [sdrplay_api_callback.h](#210-sdrplay_api_callbackh)
3. [Function Descriptions](#3-function-descriptions)
4. [API Usage](#4-api-usage)
5. [Gain Reduction Tables](#5-gain-reduction-tables)
6. [API File Location](#6-api-file-location)
7. [Legal Information](#7-legal-information)

---

## 1. Introduction

This document provides a description of the SDRplay Software Defined Radio API. This API provides a common interface to the RSP1, RSP2, RSP2pro, RSP1A, RSP1B, RSPduo, RSPdx and the RSPdxR2 from SDRplay Limited which make use of the Mirics USB bridge device (MSi2500) and the multi-standard tuner (MSi001).

From version 3.0 the API will be delivered as a service on Windows and as a daemon on non-Windows based systems. The service/daemon manages the control and data flow from each device to the end application.

### Basic Method of Operation

The basic method of operation is in 3 main stages:

1. Set the API parameters based on the selected device
2. Initialise the device to start the stream
3. Change variables and perform an update to the API

This process can be seen in the example code in section 4.

The first function call must be to `sdrplay_api_Open()` and the last must be to `sdrplay_api_Close()` otherwise the service can be left in an unknown state.

In the header file descriptions in section 2, you will find the parameters that need to be set depending on the type of device. All parameters have a default setting.

### RSPduo Operation

The RSPduo can operate in single tuner mode (just like an RSP2 for example), in dual tuner mode (both streams in a single instance) or in master/slave mode. If the RSPduo is already in use in master mode, then accessing the device again will mean that only slave mode is available. In master/slave mode, parameters that affect both tuners are only allowed to be set by the master.

Pages 4 and 5 of the RSPduo introduction document (https://www.sdrplay.com/wp-content/uploads/2018/05/RSPduo-Introduction-V3.pdf) present more information about valid states and supported sample rates for dual tuner operation.

### Parameter Structure

The structures are defined in a hierarchy. For example, to enable the Bias-T on RSP1A, use:

```c
deviceParams->rxChannelA->rsp1aTunerParams.biasTEnable = 1;
```

If this was before an initialisation, then there would be nothing else to do. To enable the Bias-T during stream, then after setting the variable, a call to the update function is required:

```c
sdrplay_api_Update(chosenDevice->dev, chosenDevice->tuner, 
    sdrplay_api_Update_Rsp1a_BiasTControl, sdrplay_api_Update_Ext1_None);
```

There is a section at the end of this document that details how to find and use the supplied API files.

**Note:** For the RSP1B, use RSP1A update and structure parameters.

**Note:** For the RSPdxR2, use RSPdx update and structure parameters.

---

## 2. API Data Types

The header files providing the definitions of the external data types and functions provided by this API are:

- `sdrplay_api.h`
- `sdrplay_api_rx_channel.h`
- `sdrplay_api_dev.h`
- `sdrplay_api_tuner.h`
- `sdrplay_api_control.h`
- `sdrplay_api_rsp1a.h`
- `sdrplay_api_rsp2.h`
- `sdrplay_api_rspDuo.h`
- `sdrplay_api_rspDx.h`
- `sdrplay_api_callback.h`

### 2.1 sdrplay_api.h

The top-level header file to be included in all applications making use of the sdrplay_api API. Defines the available functions and the structures used by them - further detail of sub-structures is contained in the subsequent sections describing the contents of each header file.

#### 2.1.1 API Functions

```c
sdrplay_api_ErrT sdrplay_api_Open(void);
sdrplay_api_ErrT sdrplay_api_Close(void);
sdrplay_api_ErrT sdrplay_api_ApiVersion(float *apiVer);
sdrplay_api_ErrT sdrplay_api_LockDeviceApi(void);
sdrplay_api_ErrT sdrplay_api_UnlockDeviceApi(void);
sdrplay_api_ErrT sdrplay_api_GetDevices(sdrplay_api_DeviceT *devices,
                                         unsigned int *numDevs,
                                         unsigned int maxDevs);
sdrplay_api_ErrT sdrplay_api_SelectDevice(sdrplay_api_DeviceT *device);
sdrplay_api_ErrT sdrplay_api_ReleaseDevice(sdrplay_api_DeviceT *device);
const char* sdrplay_api_GetErrorString(sdrplay_api_ErrT err);
sdrplay_api_ErrorInfoT* sdrplay_api_GetLastError(sdrplay_api_DeviceT *device);
sdrplay_api_ErrT sdrplay_api_GetLastErrorByType(sdrplay_api_DeviceT *device,
                                                  int type,
                                                  unsigned long long *time);
sdrplay_api_ErrT sdrplay_api_DisableHeartbeat(void);
sdrplay_api_ErrT sdrplay_api_DebugEnable(HANDLE dev, sdrplay_api_DbgLvl_t enable);
sdrplay_api_ErrT sdrplay_api_GetDeviceParams(HANDLE dev,
                                               sdrplay_api_DeviceParamsT **deviceParams);
sdrplay_api_ErrT sdrplay_api_Init(HANDLE dev,
                                   sdrplay_api_CallbackFnsT *callbackFns,
                                   void *cbContext);
sdrplay_api_ErrT sdrplay_api_Uninit(HANDLE dev);
sdrplay_api_ErrT sdrplay_api_Update(HANDLE dev,
                                     sdrplay_api_TunerSelectT tuner,
                                     sdrplay_api_ReasonForUpdateT reasonForUpdate,
                                     sdrplay_api_ReasonForUpdateExtension1T reasonForUpdateExt1);
sdrplay_api_ErrT sdrplay_api_SwapRspDuoActiveTuner(HANDLE dev,
                                                     sdrplay_api_TunerSelectT *currentTuner,
                                                     sdrplay_api_RspDuo_AmPortSelectT tuner1AmPortSel);
sdrplay_api_ErrT sdrplay_api_SwapRspDuoDualTunerModeSampleRate(HANDLE dev,
                                                                 double *currentSampleRate,
                                                                 double newSampleRate);
sdrplay_api_ErrT sdrplay_api_SwapRspDuoMode(sdrplay_api_DeviceT *currDevice,
                                              sdrplay_api_DeviceParamsT **deviceParams,
                                              sdrplay_api_RspDuoModeT rspDuoMode,
                                              double sampleRate,
                                              sdrplay_api_TunerSelectT tuner,
                                              sdrplay_api_Bw_MHzT bwType,
                                              sdrplay_api_If_kHzT ifType,
                                              sdrplay_api_RspDuo_AmPortSelectT tuner1AmPortSel);
```

#### 2.1.2 Constant Definitions

```c
#define SDRPLAY_API_VERSION          (float)(3.15)
#define SDRPLAY_MAX_DEVICES          (16)  // Maximum devices supported by the API
#define SDRPLAY_MAX_TUNERS_PER_DEVICE (2)  // Maximum number of tuners available on one device
#define SDRPLAY_MAX_SER_NO_LEN       (64)  // Maximum length of device serial numbers
#define SDRPLAY_MAX_ROOT_NM_LEN      (32)  // Maximum length of device names

// Supported device IDs
#define SDRPLAY_RSP1_ID     (1)
#define SDRPLAY_RSP1A_ID    (255)
#define SDRPLAY_RSP2_ID     (2)
#define SDRPLAY_RSPduo_ID   (3)
#define SDRPLAY_RSPdx_ID    (4)
#define SDRPLAY_RSP1B_ID    (6)
#define SDRPLAY_RSPdxR2_ID  (7)
```

#### 2.1.3 Enumerated Data Types

**Error Code Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Success = 0,
    sdrplay_api_Fail = 1,
    sdrplay_api_InvalidParam = 2,
    sdrplay_api_OutOfRange = 3,
    sdrplay_api_GainUpdateError = 4,
    sdrplay_api_RfUpdateError = 5,
    sdrplay_api_FsUpdateError = 6,
    sdrplay_api_HwError = 7,
    sdrplay_api_AliasingError = 8,
    sdrplay_api_AlreadyInitialised = 9,
    sdrplay_api_NotInitialised = 10,
    sdrplay_api_NotEnabled = 11,
    sdrplay_api_HwVerError = 12,
    sdrplay_api_OutOfMemError = 13,
    sdrplay_api_ServiceNotResponding = 14,
    sdrplay_api_StartPending = 15,
    sdrplay_api_StopPending = 16,
    sdrplay_api_InvalidMode = 17,
    sdrplay_api_FailedVerification1 = 18,
    sdrplay_api_FailedVerification2 = 19,
    sdrplay_api_FailedVerification3 = 20,
    sdrplay_api_FailedVerification4 = 21,
    sdrplay_api_FailedVerification5 = 22,
    sdrplay_api_FailedVerification6 = 23,
    sdrplay_api_InvalidServiceVersion = 24
} sdrplay_api_ErrT;
```

**Debug Level Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_DbgLvl_Disable = 0,
    sdrplay_api_DbgLvl_Verbose = 1,
    sdrplay_api_DbgLvl_Warning = 2,
    sdrplay_api_DbgLvl_Error = 3,
    sdrplay_api_DbgLvl_Message = 4,
} sdrplay_api_DbgLvl_t;
```

**Update Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Update_None = 0x00000000,
    
    // Reasons for master only mode
    sdrplay_api_Update_Dev_Fs = 0x00000001,
    sdrplay_api_Update_Dev_Ppm = 0x00000002,
    sdrplay_api_Update_Dev_SyncUpdate = 0x00000004,
    sdrplay_api_Update_Dev_ResetFlags = 0x00000008,
    
    sdrplay_api_Update_Rsp1a_BiasTControl = 0x00000010,
    sdrplay_api_Update_Rsp1a_RfNotchControl = 0x00000020,
    sdrplay_api_Update_Rsp1a_RfDabNotchControl = 0x00000040,
    
    sdrplay_api_Update_Rsp2_BiasTControl = 0x00000080,
    sdrplay_api_Update_Rsp2_AmPortSelect = 0x00000100,
    sdrplay_api_Update_Rsp2_AntennaControl = 0x00000200,
    sdrplay_api_Update_Rsp2_RfNotchControl = 0x00000400,
    sdrplay_api_Update_Rsp2_ExtRefControl = 0x00000800,
    
    sdrplay_api_Update_RspDuo_ExtRefControl = 0x00001000,
    
    sdrplay_api_Update_Master_Spare_1 = 0x00002000,
    sdrplay_api_Update_Master_Spare_2 = 0x00004000,
    
    // Reasons for master and slave mode
    sdrplay_api_Update_Tuner_Gr = 0x00008000,
    sdrplay_api_Update_Tuner_GrLimits = 0x00010000,
    sdrplay_api_Update_Tuner_Frf = 0x00020000,
    sdrplay_api_Update_Tuner_BwType = 0x00040000,
    sdrplay_api_Update_Tuner_IfType = 0x00080000,
    sdrplay_api_Update_Tuner_DcOffset = 0x00100000,
    sdrplay_api_Update_Tuner_LoMode = 0x00200000,
    
    sdrplay_api_Update_Ctrl_DCoffsetIQimbalance = 0x00400000,
    sdrplay_api_Update_Ctrl_Decimation = 0x00800000,
    sdrplay_api_Update_Ctrl_Agc = 0x01000000,
    sdrplay_api_Update_Ctrl_AdsbMode = 0x02000000,
    sdrplay_api_Update_Ctrl_OverloadMsgAck = 0x04000000,
    
    sdrplay_api_Update_RspDuo_BiasTControl = 0x08000000,
    sdrplay_api_Update_RspDuo_AmPortSelect = 0x10000000,
    sdrplay_api_Update_RspDuo_Tuner1AmNotchControl = 0x20000000,
    sdrplay_api_Update_RspDuo_RfNotchControl = 0x40000000,
    sdrplay_api_Update_RspDuo_RfDabNotchControl = 0x80000000,
} sdrplay_api_ReasonForUpdateT;

typedef enum
{
    sdrplay_api_Update_Ext1_None = 0x00000000,
    
    // Reasons for master only mode
    sdrplay_api_Update_RspDx_HdrEnable = 0x00000001,
    sdrplay_api_Update_RspDx_BiasTControl = 0x00000002,
    sdrplay_api_Update_RspDx_AntennaControl = 0x00000004,
    sdrplay_api_Update_RspDx_RfNotchControl = 0x00000008,
    sdrplay_api_Update_RspDx_RfDabNotchControl = 0x00000010,
    sdrplay_api_Update_RspDx_HdrBw = 0x00000020,
    sdrplay_api_Update_RspDuo_ResetSlaveFlags = 0x00000040,
} sdrplay_api_ReasonForUpdateExtension1T;
```

#### 2.1.4 Data Structures

**Device Enumeration Structure:**

```c
typedef struct
{
    char SerNo[SDRPLAY_MAX_SER_NO_LEN];
    unsigned char hwVer;
    sdrplay_api_TunerSelectT tuner;
    sdrplay_api_RspDuoModeT rspDuoMode;
    unsigned char valid;
    double rspDuoSampleFreq;
    HANDLE dev;
} sdrplay_api_DeviceT;
```

**Device Parameters Structure:**

```c
typedef struct
{
    sdrplay_api_DevParamsT *devParams;
    sdrplay_api_RxChannelParamsT *rxChannelA;
    sdrplay_api_RxChannelParamsT *rxChannelB;
} sdrplay_api_DeviceParamsT;
```

**Extended Error Message Structure:**

```c
typedef struct
{
    char file[256];
    char function[256];
    int line;
    char message[1024];
} sdrplay_api_ErrorInfoT;
```

### 2.2 sdrplay_api_rx_channel.h

#### 2.2.1 Data Structures

**Receive Channel Structure:**

```c
typedef struct
{
    sdrplay_api_TunerParamsT tunerParams;
    sdrplay_api_ControlParamsT ctrlParams;
    sdrplay_api_Rsp1aTunerParamsT rsp1aTunerParams;
    sdrplay_api_Rsp2TunerParamsT rsp2TunerParams;
    sdrplay_api_RspDuoTunerParamsT rspDuoTunerParams;
    sdrplay_api_RspDxTunerParamsT rspDxTunerParams;
} sdrplay_api_RxChannelParamsT;
```

### 2.3 sdrplay_api_dev.h

Provides definitions of non-tuner related parameters.

#### 2.3.1 Enumerated Data Types

**Transfer Mode Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_ISOCH = 0,
    sdrplay_api_BULK = 1
} sdrplay_api_TransferModeT;
```

#### 2.3.2 Data Structures

**ADC Sampling Frequency Parameters Structure:**

```c
typedef struct
{
    double fsHz;                    // default: 2000000.0
    unsigned char syncUpdate;       // default: 0
    unsigned char reCal;            // default: 0
} sdrplay_api_FsFreqT;
```

**Synchronous Update Parameters Structure:**

```c
typedef struct
{
    unsigned int sampleNum;         // default: 0
    unsigned int period;            // default: 0
} sdrplay_api_SyncUpdateT;
```

**Reset Update Operations Structure:**

```c
typedef struct
{
    unsigned char resetGainUpdate;  // default: 0
    unsigned char resetRfUpdate;    // default: 0
    unsigned char resetFsUpdate;    // default: 0
} sdrplay_api_ResetFlagsT;
```

**Non-Receive Channel Related Device Parameters:**

```c
typedef struct
{
    double ppm;                     // default: 0.0
    sdrplay_api_FsFreqT fsFreq;
    sdrplay_api_SyncUpdateT syncUpdate;
    sdrplay_api_ResetFlagsT resetFlags;
    sdrplay_api_TransferModeT mode; // default: sdrplay_api_ISOCH
    unsigned int samplesPerPkt;     // default: 0 (output param)
    sdrplay_api_Rsp1aParamsT rsp1aParams;
    sdrplay_api_Rsp2ParamsT rsp2Params;
    sdrplay_api_RspDuoParamsT rspDuoParams;
    sdrplay_api_RspDxParamsT rspDxParams;
} sdrplay_api_DevParamsT;
```

### 2.4 sdrplay_api_tuner.h

#### 2.4.1 Constant Definitions

```c
#define MAX_BB_GR (59)  // Maximum baseband gain reduction
```

#### 2.4.2 Enumerated Data Types

**Bandwidth Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_BW_Undefined = 0,
    sdrplay_api_BW_0_200 = 200,
    sdrplay_api_BW_0_300 = 300,
    sdrplay_api_BW_0_600 = 600,
    sdrplay_api_BW_1_536 = 1536,
    sdrplay_api_BW_5_000 = 5000,
    sdrplay_api_BW_6_000 = 6000,
    sdrplay_api_BW_7_000 = 7000,
    sdrplay_api_BW_8_000 = 8000
} sdrplay_api_Bw_MHzT;
```

**IF Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_IF_Undefined = -1,
    sdrplay_api_IF_Zero = 0,
    sdrplay_api_IF_0_450 = 450,
    sdrplay_api_IF_1_620 = 1620,
    sdrplay_api_IF_2_048 = 2048
} sdrplay_api_If_kHzT;
```

**LO Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_LO_Undefined = 0,
    sdrplay_api_LO_Auto = 1,
    sdrplay_api_LO_120MHz = 2,
    sdrplay_api_LO_144MHz = 3,
    sdrplay_api_LO_168MHz = 4
} sdrplay_api_LoModeT;
```

**Minimum Gain Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_EXTENDED_MIN_GR = 0,
    sdrplay_api_NORMAL_MIN_GR = 20
} sdrplay_api_MinGainReductionT;
```

**Tuner Selected Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Tuner_Neither = 0,
    sdrplay_api_Tuner_A = 1,
    sdrplay_api_Tuner_B = 2,
    sdrplay_api_Tuner_Both = 3,
} sdrplay_api_TunerSelectT;
```

#### 2.4.3 Data Structures

**Current Gain Value Structure:**

```c
typedef struct
{
    float curr;
    float max;
    float min;
} sdrplay_api_GainValuesT;
```

**Gain Setting Parameter Structure:**

```c
typedef struct
{
    int gRdB;                                    // default: 50
    unsigned char LNAstate;                      // default: 0
    unsigned char syncUpdate;                    // default: 0
    sdrplay_api_MinGainReductionT minGr;        // default: sdrplay_api_NORMAL_MIN_GR
    sdrplay_api_GainValuesT gainVals;           // output parameter
} sdrplay_api_GainT;
```

**RF Frequency Parameter Structure:**

```c
typedef struct
{
    double rfHz;                    // default: 200000000.0
    unsigned char syncUpdate;       // default: 0
} sdrplay_api_RfFreqT;
```

**DC Calibration Parameter Structure:**

```c
typedef struct
{
    unsigned char dcCal;            // default: 3 (Periodic mode)
    unsigned char speedUp;          // default: 0 (No speedup)
    int trackTime;                  // default: 1
    int refreshRateTime;            // default: 2048
} sdrplay_api_DcOffsetTunerT;
```

**Tuner Parameter Structure:**

```c
typedef struct
{
    sdrplay_api_Bw_MHzT bwType;                 // default: sdrplay_api_BW_0_200
    sdrplay_api_If_kHzT ifType;                 // default: sdrplay_api_IF_Zero (master) or
                                                 //          sdrplay_api_IF_0_450 (slave)
    sdrplay_api_LoModeT loMode;                 // default: sdrplay_api_LO_Auto
    sdrplay_api_GainT gain;
    sdrplay_api_RfFreqT rfFreq;
    sdrplay_api_DcOffsetTunerT dcOffsetTuner;
} sdrplay_api_TunerParamsT;
```

### 2.5 sdrplay_api_control.h

#### 2.5.1 Enumerated Data Types

**AGC Loop Bandwidth Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_AGC_DISABLE = 0,
    sdrplay_api_AGC_100HZ = 1,
    sdrplay_api_AGC_50HZ = 2,
    sdrplay_api_AGC_5HZ = 3,
    sdrplay_api_AGC_CTRL_EN = 4  // Latest AGC scheme
} sdrplay_api_AgcControlT;
```

**ADS-B Configuration Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_ADSB_DECIMATION = 0,
    sdrplay_api_ADSB_NO_DECIMATION_LOWPASS = 1,
    sdrplay_api_ADSB_NO_DECIMATION_BANDPASS_2MHZ = 2,
    sdrplay_api_ADSB_NO_DECIMATION_BANDPASS_3MHZ = 3
} sdrplay_api_AdsbModeT;
```

#### 2.5.2 Data Structures

**DC Offset Control Parameters Structure:**

```c
typedef struct
{
    unsigned char DCenable;         // default: 1
    unsigned char IQenable;         // default: 1
} sdrplay_api_DcOffsetT;
```

**Decimation Control Parameters Structure:**

```c
typedef struct
{
    unsigned char enable;           // default: 0
    unsigned char decimationFactor; // default: 1
    unsigned char wideBandSignal;   // default: 0
} sdrplay_api_DecimationT;
```

**AGC Control Parameters Structure:**

```c
typedef struct
{
    sdrplay_api_AgcControlT enable;     // default: sdrplay_api_AGC_50HZ
    int setPoint_dBfs;                  // default: -60
    unsigned short attack_ms;           // default: 0
    unsigned short decay_ms;            // default: 0
    unsigned short decay_delay_ms;      // default: 0
    unsigned short decay_threshold_dB;  // default: 0
    int syncUpdate;                     // default: 0
} sdrplay_api_AgcT;
```

**Control Parameters Structure:**

```c
typedef struct
{
    sdrplay_api_DcOffsetT dcOffset;
    sdrplay_api_DecimationT decimation;
    sdrplay_api_AgcT agc;
    sdrplay_api_AdsbModeT adsbMode;     // default: sdrplay_api_ADSB_DECIMATION
} sdrplay_api_ControlParamsT;
```

#### 2.5.3 Valid Setpoint Values vs Sample Rate

- **-72 <= setpoint_dBfs <= -20dB** (or 0dB depending on setting of sdrplay_api_GainT.minGr) for sample rates < 8.064 MSPS
- **-60 <= setpoint_dBfs <= -20dB** (or 0dB depending on setting of sdrplay_api_GainT.minGr) for sample rates in the range 8.064 – 9.216 MSPS
- **-48 <= setpoint_dBfs <= -20dB** (or 0dB depending on setting of sdrplay_api_GainT.minGr) for sample rates > 9.216 MSPS

### 2.6 sdrplay_api_rsp1a.h

**Note:** These parameters are also for the RSP1B

#### 2.6.1 Constant Definitions

```c
#define RSPIA_NUM_LNA_STATES        10  // Number of LNA states in all bands
#define RSPIA_NUM_LNA_STATES_AM     7   // Number of LNA states in AM band
#define RSPIA_NUM_LNA_STATES_LBAND  9   // Number of LNA states in L band
```

#### 2.6.2 Data Structures

**RSP1A RF Notch Control Parameters Structure:**

```c
typedef struct
{
    unsigned char rfNotchEnable;      // default: 0
    unsigned char rfDabNotchEnable;   // default: 0
} sdrplay_api_Rsp1aParamsT;
```

**RSP1A Bias-T Control Parameters Structure:**

```c
typedef struct
{
    unsigned char biasTEnable;        // default: 0
} sdrplay_api_Rsp1aTunerParamsT;
```

### 2.7 sdrplay_api_rsp2.h

#### 2.7.1 Constant Definitions

```c
#define RSPII_NUM_LNA_STATES         9  // Number of LNA states in all bands
#define RSPII_NUM_LNA_STATES_AMPORT  5  // Number of LNA states for HiZ port
#define RSPII_NUM_LNA_STATES_420MHZ  6  // Number of LNA states in 420MHz band
```

#### 2.7.2 Enumerated Data Types

**RSP2 Antenna Selection Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Rsp2_ANTENNA_A = 5,
    sdrplay_api_Rsp2_ANTENNA_B = 6,
} sdrplay_api_Rsp2_AntennaSelectT;
```

**RSP2 AM Port Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Rsp2_AMPORT_1 = 1,
    sdrplay_api_Rsp2_AMPORT_2 = 0,
} sdrplay_api_Rsp2_AmPortSelectT;
```

#### 2.7.3 Data Structures

**RSP2 External Reference Control Parameters Structure:**

```c
typedef struct
{
    unsigned char extRefOutputEn;     // default: 0
} sdrplay_api_Rsp2ParamsT;
```

**RSP2 Tuner Parameters Structure:**

```c
typedef struct
{
    unsigned char biasTEnable;                      // default: 0
    sdrplay_api_Rsp2_AmPortSelectT amPortSel;      // default: sdrplay_api_Rsp2_AMPORT_2
    sdrplay_api_Rsp2_AntennaSelectT antennaSel;    // default: sdrplay_api_Rsp2_ANTENNA_A
    unsigned char rfNotchEnable;                    // default: 0
} sdrplay_api_Rsp2TunerParamsT;
```

### 2.8 sdrplay_api_rspDuo.h

#### 2.8.1 Constant Definitions

```c
#define RSPDUO_NUM_LNA_STATES         10  // Number of LNA states in all bands
#define RSPDUO_NUM_LNA_STATES_AMPORT  5   // Number of LNA states for HiZ port
#define RSPDUO_NUM_LNA_STATES_AM      7   // Number of LNA states in AM band
#define RSPDUO_NUM_LNA_STATES_LBAND   9   // Number of LNA states in L band
```

#### 2.8.2 Enumerated Data Types

**RSPduo Operating Mode Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_RspDuoMode_Unknown = 0,
    sdrplay_api_RspDuoMode_Single_Tuner = 1,
    sdrplay_api_RspDuoMode_Dual_Tuner = 2,
    sdrplay_api_RspDuoMode_Master = 4,
    sdrplay_api_RspDuoMode_Slave = 8,
} sdrplay_api_RspDuoModeT;
```

**RSPduo AM Port Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_RspDuo_AMPORT_1 = 1,
    sdrplay_api_RspDuo_AMPORT_2 = 0,
} sdrplay_api_RspDuo_AmPortSelectT;
```

#### 2.8.3 Data Structures

**RSPduo External Reference Control Parameters Structure:**

```c
typedef struct
{
    int extRefOutputEn;               // default: 0
} sdrplay_api_RspDuoParamsT;
```

**RSPduo Reset Slave Flags Structure:**

```c
typedef struct
{
    unsigned char resetGainUpdate;    // default: 0
    unsigned char resetRfUpdate;      // default: 0
} sdrplay_api_RspDuo_ResetSlaveFlagsT;
```

**RSPduo Tuner Parameters Structure:**

```c
typedef struct
{
    unsigned char biasTEnable;                        // default: 0
    sdrplay_api_RspDuo_AmPortSelectT tuner1AmPortSel; // default: sdrplay_api_RspDuo_AMPORT_2
    unsigned char tuner1AmNotchEnable;                // default: 0
    unsigned char rfNotchEnable;                      // default: 0
    unsigned char rfDabNotchEnable;                   // default: 0
    sdrplay_api_RspDuo_ResetSlaveFlagsT resetSlaveFlags;
} sdrplay_api_RspDuoTunerParamsT;
```

### 2.9 sdrplay_api_rspDx.h

#### 2.9.1 Constant Definitions

```c
#define RSPDX_NUM_LNA_STATES                28  // Number of LNA states in all bands
#define RSPDX_NUM_LNA_STATES_AMPORT2_0_12   19  // Number of LNA states when using AM Port 2 (0-12MHz)
#define RSPDX_NUM_LNA_STATES_AMPORT2_12_50  20  // Number of LNA states when using AM Port 2 (12-50MHz)
#define RSPDX_NUM_LNA_STATES_AMPORT2_50_60  25  // Number of LNA states when using AM Port 2 (50-60MHz)
#define RSPDX_NUM_LNA_STATES_VHF_BAND3      27  // Number of LNA states in VHF and Band3
#define RSPDX_NUM_LNA_STATES_420MHZ         21  // Number of LNA states in 420MHz band
#define RSPDX_NUM_LNA_STATES_LBAND          19  // Number of LNA states in L-band
#define RSPDX_NUM_LNA_STATES_DX             22  // Number of LNA states in DX path
```

#### 2.9.2 Enumerated Data Types

**RSPdx Antenna Selection Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_RspDx_ANTENNA_A = 0,
    sdrplay_api_RspDx_ANTENNA_B = 1,
    sdrplay_api_RspDx_ANTENNA_C = 2,
} sdrplay_api_RspDx_AntennaSelectT;
```

**RSPdx HDR Mode Bandwidth Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_RspDx_HDRMODE_BW_0_200 = 0,
    sdrplay_api_RspDx_HDRMODE_BW_0_500 = 1,
    sdrplay_api_RspDx_HDRMODE_BW_1_200 = 2,
    sdrplay_api_RspDx_HDRMODE_BW_1_700 = 3,
} sdrplay_api_RspDx_HdrModeBwT;
```

#### 2.9.3 Data Structures

**RSPdx Control Parameters Structure:**

```c
typedef struct
{
    unsigned char hdrEnable;                        // default: 0
    unsigned char biasTEnable;                      // default: 0
    sdrplay_api_RspDx_AntennaSelectT antennaSel;   // default: sdrplay_api_RspDx_ANTENNA_A
    unsigned char rfNotchEnable;                    // default: 0
    unsigned char rfDabNotchEnable;                 // default: 0
} sdrplay_api_RspDxParamsT;
```

**RSPdx Tuner Parameters Structure:**

```c
typedef struct
{
    sdrplay_api_RspDx_HdrModeBwT hdrBw;  // default: sdrplay_api_RspDx_HDRMODE_BW_1_700
} sdrplay_api_RspDxTunerParamsT;
```

### 2.10 sdrplay_api_callback.h

#### 2.10.1 Enumerated Data Types

**Power Overload Event Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_Overload_Detected = 0,
    sdrplay_api_Overload_Corrected = 1,
} sdrplay_api_PowerOverloadCbEventIdT;
```

**RSPduo Event Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_MasterInitialised = 0,
    sdrplay_api_SlaveAttached = 1,
    sdrplay_api_SlaveDetached = 2,
    sdrplay_api_SlaveInitialised = 3,
    sdrplay_api_SlaveUninitialised = 4,
    sdrplay_api_MasterDllDisappeared = 5,
    sdrplay_api_SlaveDllDisappeared = 6,
} sdrplay_api_RspDuoModeCbEventIdT;
```

**Events Enumerated Type:**

```c
typedef enum
{
    sdrplay_api_GainChange = 0,
    sdrplay_api_PowerOverloadChange = 1,
    sdrplay_api_DeviceRemoved = 2,
    sdrplay_api_RspDuoModeChange = 3,
    sdrplay_api_DeviceFailure = 4,
} sdrplay_api_EventT;
```

#### 2.10.2 Data Structures

**Event Callback Structure:**

```c
typedef struct
{
    unsigned int gRdB;
    unsigned int lnaGRdB;
    double currGain;
} sdrplay_api_GainCbParamT;
```

**Power Overload Structure:**

```c
typedef struct
{
    sdrplay_api_PowerOverloadCbEventIdT powerOverloadChangeType;
} sdrplay_api_PowerOverloadCbParamT;
```

**RSPduo Structure:**

```c
typedef struct
{
    sdrplay_api_RspDuoModeCbEventIdT modeChangeType;
} sdrplay_api_RspDuoModeCbParamT;
```

**Combination of Event Callback Structures:**

```c
typedef union
{
    sdrplay_api_GainCbParamT gainParams;
    sdrplay_api_PowerOverloadCbParamT powerOverloadParams;
    sdrplay_api_RspDuoModeCbParamT rspDuoModeParams;
} sdrplay_api_EventParamsT;
```

**Streaming Data Parameter Callback Structure:**

```c
typedef struct
{
    unsigned int firstSampleNum;
    int grChanged;
    int rfChanged;
    int fsChanged;
    unsigned int numSamples;
} sdrplay_api_StreamCbParamsT;
```

**Callback Function Definition Structure:**

```c
typedef struct
{
    sdrplay_api_StreamCallback_t StreamACbFn;
    sdrplay_api_StreamCallback_t StreamBCbFn;
    sdrplay_api_EventCallback_t EventCbFn;
} sdrplay_api_CallbackFnsT;
```

#### 2.10.3 Callback Function Prototypes

```c
typedef void (*sdrplay_api_StreamCallback_t)(short *xi,
                                               short *xq,
                                               sdrplay_api_StreamCbParamsT *params,
                                               unsigned int numSamples,
                                               unsigned int reset,
                                               void *cbContext);

typedef void (*sdrplay_api_EventCallback_t)(sdrplay_api_EventT eventId,
                                              sdrplay_api_TunerSelectT tuner,
                                              sdrplay_api_EventParamsT *params,
                                              void *cbContext);
```

---

## 3. Function Descriptions

### 3.1 sdrplay_api_Open

```c
sdrplay_api_ErrT sdrplay_api_Open(void)
```

**Description:**  
Opens the API and configures the API for use. This function must be called before any other API function.

**Parameters:**  
- `void` - No parameters

**Return:**  
- `sdrplay_api_Success` - API successfully opened
- `sdrplay_api_Fail` - API failed to open

### 3.2 sdrplay_api_Close

```c
sdrplay_api_ErrT sdrplay_api_Close(void)
```

**Description:**  
Tidies up and closes the API. After calling this function it is no longer possible to access other API functions until `sdrplay_api_Open()` is successfully called again.

**Parameters:**  
- `void` - No parameters

**Return:**  
- `sdrplay_api_Success` - API successfully closed

### 3.3 sdrplay_api_ApiVersion

```c
sdrplay_api_ErrT sdrplay_api_ApiVersion(float *apiVer)
```

**Description:**  
This function checks that the version of the include file used to compile the application is consistent with the API version being used.

**Parameters:**  
- `apiVer` - Pointer to a float which returns the version of the API

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer
- `sdrplay_api_InvalidServiceVersion` - Service version doesn't match
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.4 sdrplay_api_LockDeviceApi

```c
sdrplay_api_ErrT sdrplay_api_LockDeviceApi(void)
```

**Description:**  
Attempts to lock the API for exclusive use of the current application. Once locked, no other applications will be able to use the API. Typically used to lock the API prior to calling `sdrplay_api_GetDevices()` to ensure only one application can select a given device.

**Parameters:**  
- `void` - No parameters

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.5 sdrplay_api_UnlockDeviceApi

```c
sdrplay_api_ErrT sdrplay_api_UnlockDeviceApi(void)
```

**Description:**  
See description for `sdrplay_api_LockDeviceApi()`.

**Parameters:**  
- `none` - No parameters

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.6 sdrplay_api_GetDevices

```c
sdrplay_api_ErrT sdrplay_api_GetDevices(sdrplay_api_DeviceT *devices,
                                         unsigned int *numDevs,
                                         unsigned int maxDevs)
```

**Description:**  
This function returns a list of all available devices (up to a maximum defined by maxDev parameter). Once the list has been retrieved, a device can be selected based on the required characteristics.

**Parameters:**  
- `devices` - Pointer to an array of device enumeration structures used to return the list of available devices
- `numDevs` - Pointer to a variable which on return will indicate the number of available devices
- `maxDevs` - Specifies the maximum number of devices that can be returned in the list

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.7 sdrplay_api_SelectDevice

```c
sdrplay_api_ErrT sdrplay_api_SelectDevice(sdrplay_api_DeviceT *device)
```

**Description:**  
Once a device is selected from the list of devices returned in `sdrplay_api_GetDevices()`, and the additional information for the device configured, this function will select the device. Once a device has been selected, it is no longer available for other applications (unless the device is a RSPduo in master/slave mode).

**Parameters:**  
- `device` - Pointer to the sdrplay_api_DeviceT structure for the selected device

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.8 sdrplay_api_ReleaseDevice

```c
sdrplay_api_ErrT sdrplay_api_ReleaseDevice(sdrplay_api_DeviceT *device)
```

**Description:**  
Releases a device and makes that device available for other applications.

**Parameters:**  
- `device` - Pointer to the sdrplay_api_DeviceT structure for the device to be released

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.9 sdrplay_api_GetErrorString

```c
const char* sdrplay_api_GetErrorString(sdrplay_api_ErrT err)
```

**Description:**  
Upon receipt of an error code, a print friendly error string can be obtained using the function. The returned pointer is a pointer to a static array and does not need to be freed.

**Parameters:**  
- `err` - Error code to be converted to a string

**Return:**  
- `const char *` - Pointer to a string containing the error definition

### 3.10 sdrplay_api_GetLastError

```c
sdrplay_api_ErrorInfoT* sdrplay_api_GetLastError(sdrplay_api_DeviceT *device)
```

**Description:**  
Upon receipt of an error code, extended information on the location and reason for the error can be obtained using the function. The returned pointer is a pointer to a static array and does not need to be freed.

**Parameters:**  
- `device` - Pointer to the sdrplay_api_DeviceT structure for the device currently used

**Return:**  
- `sdrplay_api_ErrorInfoT *` - Pointer to a structure containing the last error information

### 3.11 sdrplay_api_GetLastErrorByType

```c
sdrplay_api_ErrorInfoT* sdrplay_api_GetLastError(sdrplay_api_DeviceT *device,
                                                   int type,
                                                   unsigned long long *time)
```

**Description:**  
Upon receipt of an error code and message type, extended information on the error can be obtained using the function.

**Parameters:**  
- `device` - Pointer to the sdrplay_api_DeviceT structure for the device currently used
- `type` - Message type (0=DLL message, 1=DLL device message, 2=Service message, 3=Service device message)
- `Time` - Pointer to the time of the error

**Return:**  
- `sdrplay_api_ErrorInfoT *` - Pointer to a structure containing the last error information

### 3.12 sdrplay_api_DisableHeartbeat

```c
sdrplay_api_ErrT sdrplay_api_DisableHeartbeat(void)
```

**Description:**  
Debug only function. Allows code to be stepped through without API threads timing out. MUST be called before `sdrplay_api_SelectDevice` is called.

**Parameters:**  
- `void` - No parameters

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Failure to call sdrplay_api_LockDeviceApi

### 3.13 sdrplay_api_DebugEnable

```c
sdrplay_api_ErrT sdrplay_api_DebugEnable(HANDLE dev, sdrplay_api_DbgLvl_t dbgLvl)
```

**Description:**  
Enable or disable debug output logging. This logging can help with debugging issues but will increase the processing load and in some extreme cases, may cause data dropout.

**Parameters:**  
- `dev` - Handle of selected device from current device enumeration structure (can be NULL for reduced logging prior to selecting a device)
- `dbgLvl` - Specify the level of debug required using the relevant enum parameter

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.14 sdrplay_api_GetDeviceParams

```c
sdrplay_api_ErrT sdrplay_api_GetDeviceParams(HANDLE dev,
                                               sdrplay_api_DeviceParamsT **deviceParams)
```

**Description:**  
Devices are configured via the parameters contained in the device parameter structure. After selecting a device, the default device parameters are returned and can be modified as required before `sdrplay_api_Init()` is called.

**Parameters:**  
- `Dev` - Handle of selected device from current device enumeration structure
- `deviceParams` - Pointer to a pointer to the device parameters used to setup/control the device

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_NotInitialised` - Device has not been selected
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.15 sdrplay_api_Init

```c
sdrplay_api_ErrT sdrplay_api_Init(HANDLE dev,
                                   sdrplay_api_CallbackFnsT *callbackFns,
                                   void *cbContext)
```

**Description:**  
This function will initialise the tuners according to the device parameter structure. After successfully completing initialisation, it will set up a thread inside the API which will perform the processing chain.

**Processing chain (in order):**
- ReadUSBdata - fetch packets of IQ samples from USB interface
- DCoffsetCorrection - enabled by default
- Agc - enabled by default
- DownConvert - enabled in LIF mode when parameters are consistent with down-conversion to baseband
- Decimate - disabled by default
- IQimbalanceCorrection - enabled by default

**Conditions for LIF down-conversion to be enabled:**
- `(fsHz == 8192000) && (bwType == sdrplay_api_BW_1_536) && (ifType == sdrplay_api_IF_2_048)`
- `(fsHz == 8000000) && (bwType == sdrplay_api_BW_1_536) && (ifType == sdrplay_api_IF_2_048)`
- `(fsHz == 8000000) && (bwType == sdrplay_api_BW_5_000) && (ifType == sdrplay_api_IF_2_048)`
- `(fsHz == 2000000) && (bwType <= sdrplay_api_BW_0_300) && (ifType == sdrplay_api_IF_0_450)`
- `(fsHz == 2000000) && (bwType == sdrplay_api_BW_0_600) && (ifType == sdrplay_api_IF_0_450)`
- `(fsHz == 6000000) && (bwType <= sdrplay_api_BW_1_536) && (ifType == sdrplay_api_IF_1_620)`

**Parameters:**  
- `dev` - Handle of selected device from current device enumeration structure
- `callbackFns` - Pointer to a structure specifying the callback functions to use to send processed data and events
- `cbContext` - Pointer to a context passed to the API that will be returned as a parameter in the callback functions

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_NotInitialised` - Device has not been selected
- `sdrplay_api_InvalidParam` - NULL pointer
- `sdrplay_api_AlreadyInitialised` - There has been a previous call to this function
- `sdrplay_api_OutOfRange` - One or more parameters are set incorrectly
- `sdrplay_api_HwError` - HW error occurred during tuner initialisation
- `sdrplay_api_RfUpdateError` - Failed to update Rf frequency
- `sdrplay_api_StartPending` - Master device not running
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.16 sdrplay_api_Uninit

```c
sdrplay_api_ErrT sdrplay_api_Uninit(HANDLE dev)
```

**Description:**  
Stops the stream and uninitialises the tuners. In RSPduo master/slave mode, the master application cannot be uninitialised until the slave application is stopped.

**Parameters:**  
- `Dev` - Handle of selected device from current device enumeration structure

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_NotInitialised` - Device has not been selected
- `sdrplay_api_StopPending` - Slave device running
- `sdrplay_api_ServiceNotResponding` - Communication channel with service broken

### 3.17 sdrplay_api_Update

```c
sdrplay_api_ErrT sdrplay_api_Update(HANDLE dev,
                                     sdrplay_api_TunerSelectT tuner,
                                     sdrplay_api_ReasonForUpdateT reasonForUpdate,
                                     sdrplay_api_ReasonForUpdateExtension1T reasonForUpdateExt1)
```

**Description:**  
This function is used to indicate that parameters have been changed and need to be applied. Used to change any combination of values of the parameters. If required it will stop the stream, change the values and then start the stream again, otherwise it will make the changes directly.

**Valid sdrplay_api_ReasonForUpdateT parameters:**

- `sdrplay_api_Update_None` - No changes relating to ReasonForUpdateT
- `sdrplay_api_Update_Dev_Fs` - deviceParams->devParams->fsFreq->*
- `sdrplay_api_Update_Dev_Ppm` - deviceParams->devParams->ppm
- `sdrplay_api_Update_Dev_SyncUpdate` - deviceParams->devParams->syncUpdate->*
- `sdrplay_api_Update_Dev_ResetFlags` - deviceParams->devParams->resetFlags->*
- `sdrplay_api_Update_Rsp1a_BiasTControl` - deviceParams->rxChannel*->rsp1aTunerParams->biasTEnable
- `sdrplay_api_Update_Rsp1a_RfNotchControl` - deviceParams->devParams->rsp1aParams->rfNotchEnable
- `sdrplay_api_Update_Rsp1a_RfDabNotchControl` - deviceParams->devParams->rsp1aParams->rfDabNotchEnable
- `sdrplay_api_Update_Tuner_Gr` - deviceParams->rxChannel*->tunerParams->gain->gRdB or LNAstate
- `sdrplay_api_Update_Tuner_Frf` - deviceParams->rxChannel*->tunerParams->rfFreq->*
- And more...

**Parameters:**  
- `dev` - Handle of selected device from current device enumeration structure
- `tuner` - Specifies which tuner(s) to apply the update to
- `reasonForUpdate` - Specifies the reason for the call depending on which parameters have been changed
- `reasonForUpdateExt1` - Specifies the reason for the call (extension parameters)

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer or invalid operating mode
- `sdrplay_api_OutOfRange` - One or more parameters are set incorrectly
- `sdrplay_api_HwError` - HW error occurred during tuner initialisation
- `sdrplay_api_FsUpdateError` - Failed to update sample rate
- `sdrplay_api_RfUpdateError` - Failed to update Rf frequency
- `sdrplay_api_GainUpdateError` - Failed to update gain
- `sdrplay_api_NotEnabled` - Feature not enabled
- `sdrplay_api_ServiceNotResponding` - Communication with the service is broken

### 3.18 sdrplay_api_SwapRspDuoActiveTuner

```c
sdrplay_api_ErrT sdrplay_api_SwapRspDuoActiveTuner(HANDLE dev,
                                                     sdrplay_api_TunerSelectT *currentTuner,
                                                     sdrplay_api_RspDuo_AmPortSelectT tuner1AmPortSel)
```

**Description:**  
After a call to `sdrplay_api_Init()` for an RSPduo in single tuner mode, this function can be called to change between tuners while maintaining the exact same settings.

**Parameters:**  
- `dev` - Handle of selected device from current device enumeration structure
- `currentTimer` - Pointer to the selected tuner stored in the current device enumeration structure
- `tuner1AmPortSel` - Specifies whether to use the HiZ port when switching to TunerA when the AM band is selected

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer or invalid operating mode
- `sdrplay_api_OutOfRange` - One or more parameters are set incorrectly
- `sdrplay_api_HwError` - HW error occurred during tuner initialisation
- `sdrplay_api_RfUpdateError` - Failed to update Rf frequency
- `sdrplay_api_ServiceNotResponding` - Communication with the service is broken

### 3.19 sdrplay_api_SwapRspDuoDualTunerModeSampleRate

```c
sdrplay_api_ErrT sdrplay_api_SwapRspDuoDualTunerModeSampleRate(HANDLE dev,
                                                                 double *currentSampleRate)
```

**Description:**  
After a call to `sdrplay_api_Init()` for an RSPduo in master/slave mode, this function can be called to change sample rates between 6MHz and 8MHz. This function can only be called by the master application.

**Parameters:**  
- `dev` - Handle of selected device from current device enumeration structure
- `currentSampleRate` - Pointer to the selected sample rate stored in the current device enumeration structure

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer or invalid operating mode
- `sdrplay_api_OutOfRange` - One or more parameters are set incorrectly
- `sdrplay_api_HwError` - HW error occurred during tuner initialisation
- `sdrplay_api_RfUpdateError` - Failed to update Rf frequency
- `sdrplay_api_StopPending` - Slave device running
- `sdrplay_api_ServiceNotResponding` - Communication with the service is broken

### 3.20 sdrplay_api_SwapRspDuoMode

```c
sdrplay_api_ErrT sdrplay_api_SwapRspDuoMode(sdrplay_api_DeviceT *currDevice,
                                              sdrplay_api_DeviceParamsT **deviceParams,
                                              sdrplay_api_RspDuoModeT rspDuoMode,
                                              double sampleRate,
                                              sdrplay_api_TunerSelectT tuner,
                                              sdrplay_api_Bw_MHzT bwType,
                                              sdrplay_api_If_kHzT ifType,
                                              sdrplay_api_RspDuo_AmPortSelectT tuner1AmPortSel)
```

**Description:**  
After a call to `sdrplay_api_Init()` for an RSPduo, this function can be called to change the operating mode. This function can only be called by the master application.

**Parameters:**  
- `currDevice` - Pointer to the sdrplay_api_DeviceT structure for the device currently used
- `deviceParams` - Pointer to a pointer to the device parameters used to setup/control the device
- `rspDuoMode` - RSPduo operating mode
- `sampleRate` - Target sample rate
- `tuner` - Target tuner
- `bwType` - Target hardware IF bandwidth
- `ifType` - Target IF mode frequency
- `tuner1AmPortSel` - If using tuner 1, this parameter allows the selection of the AM port

**Return:**  
- `sdrplay_api_Success` - Successful completion
- `sdrplay_api_Fail` - Command failed
- `sdrplay_api_InvalidParam` - NULL pointer or invalid operating mode
- `sdrplay_api_OutOfRange` - One or more parameters are set incorrectly
- `sdrplay_api_HwError` - HW error occurred during tuner initialisation
- `sdrplay_api_RfUpdateError` - Failed to update Rf frequency
- `sdrplay_api_StopPending` - Slave device running
- `sdrplay_api_ServiceNotResponding` - Communication with the service is broken

### 3.21 Streaming Data Callback

```c
typedef void (*sdrplay_api_StreamCallback_t)(short *xi,
                                               short *xq,
                                               sdrplay_api_StreamCbParamsT *params,
                                               unsigned int numSamples,
                                               unsigned int reset,
                                               void *cbContext)
```

**Description:**  
This callback is triggered when there are samples to be processed.

**Parameters:**  
- `Xi` - Pointer to the real data in the buffer
- `Xq` - Pointer to the imaginary data in the buffer
- `params` - Pointer to the stream callback parameter's structure
- `numSamples` - The number of samples in the current buffer
- `Reset` - Indicates if a re-initialisation has occurred within the API and that local buffering should be reset
- `cbContext` - Pointer to context passed into sdrplay_api_Init()

**Return:** None

### 3.22 Event Callback

```c
typedef void (*sdrplay_api_EventCallback_t)(sdrplay_api_EventT eventId,
                                              sdrplay_api_TunerSelectT tuner,
                                              sdrplay_api_EventParamsT *params,
                                              void *cbContext)
```

**Description:**  
This callback is triggered whenever an event occurs. The list of events is specified by the `sdrplay_api_EventT` enumerated type.

**Parameters:**  
- `eventId` - Indicates the type of event that has occurred
- `Tuner` - Indicates which tuner(s) the event relates to
- `params` - Pointer to the event callback union (the structure used depends on the eventId)
- `cbContext` - Pointer to context passed into sdrplay_api_Init()

**Return:** None

---

## 4. API Usage

(Example code showing complete usage - see pages 32-37 of original document for full sample application code)

The sample application demonstrates:
- Opening the API
- Enumerating devices
- Selecting a device
- Configuring parameters
- Initializing streaming
- Handling callbacks
- Updating parameters during streaming
- Uninitializing and cleanup

---

## 5. Gain Reduction Tables

### LNA GR (dB) by Frequency Range and LNAstate for RSP1

| Frequency (MHz) | LNAstate | 0 | 1 | 2 | 3 | 4 |
|-----------------|----------|---|---|---|---|---|
| 0-420 | | 0 | 24 | 19¹ | 43² |
| 420-1000 | | 0 | 7 | 19¹ | 26² |
| 1000-2000 | | 0 | 5 | 19¹ | 24² |

### LNA GR (dB) by Frequency Range and LNAstate for RSP1A/RSP1B

| Frequency (MHz) | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|-----------------|---|---|---|---|---|---|---|---|---|---|
| 0-60 | 0 | 6 | 12 | 18 | 37 | 42 | 61² | | | |
| 60-420 | 0 | 6 | 12 | 18 | 20 | 26 | 32 | 38 | 57 | 62 |
| 420-1000 | 0 | 7 | 13 | 19 | 20 | 27 | 33 | 39 | 45 | 64² |
| 1000-2000 | 0 | 6 | 12 | 20 | 26 | 32 | 38 | 43 | 62² | |

### LNA GR (dB) by Frequency Range and LNAstate for RSP2

| Frequency (MHz) | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|-----------------|---|---|---|---|---|---|---|---|---|
| 0-420 (Port A or B) | 0 | 10 | 15 | 21 | 24 | 34 | 39 | 45 | 64² |
| 420-1000 | 0 | 7 | 10 | 17 | 22 | 41² | | | |
| 1000-2000 | 0 | 5 | 21 | 15³ | 15³ | 34² | | | |
| 0-60 (HiZ Port) | 0 | 6 | 12 | 18 | 37² | | | | |

### LNA GR (dB) by Frequency Range and LNAstate for RSPduo

| Frequency (MHz) | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|-----------------|---|---|---|---|---|---|---|---|---|---|
| 0-60 (50Ω Ports) | 0 | 6 | 12 | 18 | 37 | 42 | 61² | | | |
| 60-420 | 0 | 6 | 12 | 18 | 20 | 26 | 32 | 38 | 57 | 62 |
| 420-1000 | 0 | 7 | 13 | 19 | 20 | 27 | 33 | 39 | 45 | 64² |
| 1000-2000 | 0 | 6 | 12 | 20 | 26 | 32 | 38 | 43 | 62² | |
| 0-60 (HiZ Port) | 0 | 6 | 12 | 18 | 37² | | | | | |

### LNA GR (dB) by Frequency Range and LNAstate for RSPdx/RSPdxR2

(See page 39 of original document for complete table - very large table with 28 LNA states across multiple frequency ranges)

**Notes:**
- ¹ Mixer GR only
- ² Includes LNA GR plus mixer GR
- ³ In LNAstate 3, external LNA GR only; in LNAstate 4, external plus internal LNA GR

---

## 6. API File Location

The API is delivered in two halves:
- **Service** - An executable that automatically starts when the host device boots
- **DLL/Library** - A library (.dll on Windows, .so on non-Windows) that should be loaded by the SDR application

### Default Folder Locations

**Windows:**  
`C:\Program Files\SDRplay`

**Non-Windows:**  
`/usr/local/lib` (library) & `/usr/local/bin` (service executable)

### Finding API Location on Windows

The API location can be found from the registry:

```
HKEY_LOCAL_MACHINE\SOFTWARE\SDRplay\Service\API\Install_Dir
```
or
```
HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\SDRplay\Service\API\Install_Dir
```

Then add either:
- `x86\sdrplay_api.dll` (for 32-bit)
- `x64\sdrplay_api.dll` (for 64-bit)

### Example Code for Loading the API

```c
// Find entries in registry
RegOpenKey(HKEY_LOCAL_MACHINE, TEXT("SOFTWARE\\SDRplay\\Service\\API"), &APIkey);
RegQueryValueEx(APIkey, "Install_Dir", NULL, NULL, (LPBYTE)&APIkeyValue, &APIkeyValue_length);

// Build path to DLL
sprintf(apiPath, "%s\\x64\\sdrplay_api.dll", APIkeyValue);

// Load the library
LPCSTR ApiDllName = (LPCSTR)apiPath;
ApiDll = LoadLibrary(ApiDllName);

// Setup function pointers
sdrplay_api_Open_t sdrplay_api_Open_fn = NULL;
sdrplay_api_Open_fn = (sdrplay_api_Open_t)GetProcAddress(ApiDll, "sdrplay_api_Open");

// Use the function
sdrplay_api_ErrT err;
err = sdrplay_api_Open_fn();

// After API has been closed, free the library
FreeLibrary(ApiDll);
```

---

## 7. Legal Information

### Redistribution and Use

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

### Disclaimer

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### Mirics License

SDRPlay modules use a Mirics chipset and software. The information supplied hereunder is provided to you by SDRPlay under license from Mirics. Mirics hereby grants you a perpetual, worldwide, royalty free license to use the information herein for the purpose of designing software that utilizes SDRPlay modules.

### Company Information

- **SDRPlay** is the trading name of SDRPlay Limited, a company registered in England #09035244
- **Mirics** is the trading name of Mirics Limited, a company registered in England #05046393
- Mirics FlexiRF™, Mirics FlexiTV™ and Mirics™ are trademarks of Mirics

### Contact

For more information, contact: https://www.sdrplay.com/support

---

*End of Document*
