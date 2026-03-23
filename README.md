# web-spectrum

<div align="center">
  <h3>📡 網路頻譜分析器與 GPS 訊號分析平台</h3>
  <p>
    <a href="https://meshuga.github.io/web-spectrum/">
      <img src="https://img.shields.io/badge/🌐-線上演示-blue" alt="Live Demo">
    </a>
    <a href="https://github.com/meshuga/web-spectrum/stargazers">
      <img src="https://img.shields.io/github/stars/meshuga/web-spectrum" alt="Stars">
    </a>
    <a href="https://github.com/meshuga/web-spectrum/issues">
      <img src="https://img.shields.io/github/issues/meshuga/web-spectrum" alt="Issues">
    </a>
    <a href="https://github.com/meshuga/web-spectrum/blob/main/LICENSE">
      <img src="https://img.shields.io/github/license/meshuga/web-spectrum" alt="License">
    </a>
  </p>
</div>

---

## 📖 簡介

**Web Spectrum** 是一個強大的網路頻譜分析器與 GPS 訊號分析平台，它結合了現代 Web 技術與專業的訊號處理能力，讓您能夠直接在瀏覽器中進行複雜的射頻（RF）訊號分析。

### ✨ 核心特點

- 🌐 **完全基於 Web** - 無需安裝桌面應用程式，完全在瀏覽器中運行
- 🔌 **多裝置支援** - 同時支援 tinySA Ultra、RTL-SDR、SDRPlay 等多種 SDR 裝置
- 📊 **即時頻譜分析** - 高效能的即時頻譜顯示與瀑布圖
- 🛰️ **專業級 GPS 分析** - 整合 GNSS-SDR 進行高精度 GNSS 訊號處理
- 🔍 **進階干擾偵測** - 自動檢測並分析 5 種不同類型的干擾訊號
- 🚀 **易於使用** - 直觀的使用者介面，適合初學者與專業人士
- 📱 **響應式設計** - 在桌機、平板、手機上皆能完美運作

### 🎯 使用場景

- **教育與研究** - 射頻通訊、訊號處理、GNSS 系統的教學與研究
- **無線電愛好** - 業餘無線電、掃描、實驗
- **安全測試** - ADS-B 追追蹤、頻譜監控、干擾偵測
- **專業應用** - 現場測試、訊號分析、導航系統驗證
- **GPS 測試** - GNSS 訊號品質分析、定位準確度評估

---

## 🌟 主要功能

### 📈 頻譜分析器
- **即時頻譜顯示** - 高更新頻率的即時頻譜圖
- **瀑布圖** - 時間頻域的連續顯示，追蹤訊號變化
- **訊號強度測量** - 即時 dBm 值顯示與峰值檢測
- **頻率標記** - 自動識別並標記高峰訊號
- **可配置參數** - 調整掃描範圍、解析度、平均次數等

### 🛰️ GPS 訊號記錄與分析
- **專業級 GNSS 處理** - 整合 GNSS-SDR 進行高精度分析
- **多系統支援** - GPS、Galileo、GLONASS、BeiDou 四大系統
- **自動干擾偵測** - 智能識別脈衝、掃描、雜訊、窄頻、偽裝干擾
- **位置計算** - 提供緯度、經度、高度的精確定位
- **衛星追蹤** - 即時顯示可見衛星與訊號品質
- **NMEA/KML/GPX 輸出** - 多種格式的匯出，支援 Google Earth 等工具

### 📡 資料解碼
- **ADS-B 航空追蹤** - 1090 MHz 頻段的飛機位置追蹤
- **ISM 協定解碼** - 433/868 MHz 頻段的無線電識別、遙控等
- **多系統 GNSS** - GPS L1、Galileo E1、GLONASS L1OF、BeiDou B1I
- **即時解碼** - 直接在瀏覽器中進行訊號解碼
- **訊息顯示** - 解碼結果的詳細資訊展示

---

## 🧩 支援的裝置

| 裝置 | 類型 | 價格範圍 | 適用場景 |
|------|------|----------|----------|
| **tinySA Ultra** | 頻譜分析器 | ~$200 | 便攜式頻譜分析、訊號測試 |
| **RTL-SDR (RTL2832U)** | 軟體無線電 | $25-40 | 預算有限的 SDR 應用、教育用途 |
| **RTL-SDR V4** | 進階軟體無線電 | ~$40 | 改良型、更高品質的 SDR 接收 |
| **SDRPlay RSPduo** | 專業 SDR 接收器 | ~$300 | 專業測試、雙調諧器應用 |
| **SDRPlay RSP1A** | 專業 SDR 接收器 | ~$200 | 專業級測試與分析 |

### 🔧 裝置選擇建議

**入門級** → RTL-SDR V4
- 性價比最高，適合學習與實驗
- 支援 GPS 分析、ADS-B、ISM 等功能

**進階級** → tinySA Ultra
- 專業頻譜分析功能
- 便攜設計，適合外場測試

**專業級** → SDRPlay RSPduo
- 雙調諧器，可同時接收兩個頻段
- 優靈敏度，專業測試首選

---

## 🌐 支援的瀏覽器

由於使用了 Web Serial 與 WebUSB API，僅限支援這些 API 的瀏覽器：

| 瀏覽器 | 版本要求 | 支援狀態 |
|--------|----------|----------|
| **Chrome** | 89+ | ✅ 完全支援 |
| **Edge** | 89+ | ✅ 完全支援 |
| **Opera** | 75+ | ✅ 完全支援 |
| **Firefox** | - | ❌ 不支援 |
| **Safari** | - | ❌ 不支援 |

查看更多資訊：
- [caniuse.com/web-serial](https://caniuse.com/web-serial)
- [caniuse.com/webusb](https://caniuse.com/webusb)

---

## 🚀 快速開始

### 安裝前置需求

**系統要求：**
- **作業系統**：macOS 10.15+、Windows 10/11、Linux（Ubuntu 20.04+ 建議）
- **RAM**：最少 4 GB（建議 8 GB+ 用於 GPS 分析）
- **儲存空間**：至少 2 GB 可用空間
- **網路**：穩定的網際網路連線（僅安裝時需要）

**軟體需求：**
- Node.js 16+ ([下載](https://nodejs.org/))
- Python 3.8+ ([下載](https://www.python.org/))
- Git

### 一鍵安裝

```bash
# 1. 克隆倉庫
git clone https://github.com/meshuga/web-spectrum.git
cd web-spectrum

# 2. 安裝 Node.js 依賴
npm install

# 3. 安裝 Python 依賴
pip3 install -r requirements.txt

# 4. 啟動應用程式
npm start
```

瀏覽器將自動開啟 http://localhost:3005

### 📍 GNSS-SDR 安裝（GPS 分析必需）

GNSS-SDR 是專業級 GNSS 訊號處理軟體，用於高精度 GPS 分析。

#### macOS 安裝

```bash
cd gnss-sdr
./install_gnss_sdr.sh
```

安裝腳本會自動：
- ✅ 安裝所有 Homebrew 依賴（Boost、GLOG、Armadillo 等）
- ✅ 從原始碼下載並建置 GNSS-SDR
- ✅ 安裝至 `/usr/local/bin/gnss-sdr`
- ⏱️ 需時約 30-40 分鐘（視 CPU 性能而定）

**驗證安裝：**
```bash
gnss-sdr --version
# 輸出示例：gnss-sdr version 0.0.19
```

#### Linux 安裝

```bash
# Ubuntu/Debian
sudo apt-get install -y \
  build-essential cmake git \
  libboost-all-dev libgflags-dev \
  libgoogle-glog-dev libarmadillo-dev

git clone https://github.com/gnss-sdr/gnss-sdr.git
cd gnss-sdr
git checkout v0.0.19
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install
```

### 🎛️ SDRPlay API 安裝（僅 SDRPlay 裝置需要）

#### macOS

```bash
# 1. 前往 SDRplay 官方網站
# https://www.sdrplay.com/downloads/

# 2. 下載並安裝 SDRplay API

# 3. 驗證安裝
ls /Library/SDRplayAPI/
# 輸出示例：3.15.1
```

#### Linux

```bash
# 下載並安裝 SDRplay API
wget https://www.sdrplay.com/downloads/SDRplay_RSP_API-Linux3.07.1.run
chmod +x SDRplay_RSP_API-Linux3.07.1.run
sudo ./SDRplay_RSP_API-Linux3.07.1.run
```

### 📦 Python 依賴詳細說明

完整的依賴列表請參閱 [requirements.txt](requirements.txt)。

**核心套件：**
```bash
# 選項 1：標準安裝（推薦大部分用戶）
pip3 install -r requirements.txt

# 選項 2：macOS 使用 Homebrew Python
pip3 install --break-system-packages -r requirements.txt

# 選項 3：使用虛擬環境（最乾淨，推薦開發者）
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

**依賴套件說明：**

| 套件 | 版本 | 用途 |
|------|------|------|
| numpy | 1.21+ | 訊號處理、FFT、相關運算核心 |
| websockets | 10.0+ | WebSocket 伺服器，即時資料串流 |
| requests | 2.26+ | HTTP 客戶端（Gypsum GPS 解碼器） |
| python-dateutil | 2.8+ | GPS 時間戳記與日期解析 |
| matplotlib | 3.4+ | 頻譜圖與視覺化繪製 |

---

## 🎮 使用指南

### 啟動應用程式

```bash
# 啟動網頁前端（埠口 3005）
npm start

# 啟動後端服務（埠口 5001 和 8766）
./start_backend.sh
```

⚠️ **重要**：如需使用 GPS 分析功能，必須同時運行前端與後端服務。

### 📱 介面導覽

1. **首頁** - 選擇裝置類型裡（TinySA、RTL-SDR、SDRPlay）
2. **頻譜分析** - 即時頻譜顯示與控制面板
3. **GPS 解碼** - GNSS 訊號記錄與分析
4. **ADS-B/ISM 解碼** - 航空追蹤與無線電識別
5. **設定** - 裝置配置與參數調整

### 🛰️ 使用 GPS 記錄功能

**步驟 1：連接裝置**
- 將 SDR 裝置連接到電腦
- 在網頁介面點擊「連接裝置」按鈕
- 確認裝置已成功識別

**步驟 2：配置參數**
- 設置記錄持續時間（建議 2-5 分鐘）
- 調整增益參數（自動增益或手動）
- 選擇 GPS 解碼器（GNSS-SDR 或 Gypsum）

**步驟 3：開始記錄**
1. 點點擊「⏺ 開始記錄」按鈕
2. 等待記錄完成（可見即時進度）
3. 自動開始處理

**步驟 4：查看結果**
- 📊 頻譜瀑布圖 - GPS 訊號與干擾的視覺化
- 🎯 定位結果 - 緯度、經度、高度
- 🛰️ 衛星追蹤 - 可見衛星與訊號強度
- ⚠️ 干擾分析 - 檢測到的干擾類型與強度
- 📁 匯出 - NMEA、KML、GPX 格式檔案

### 📊 記錄持續時間建議

| 用途 | 時間 | 檔案大小 | 優點 |
|------|------|----------|------|
| **快速測試** | 30-60 秒 | ~468-937 MB | 快速驗證、測試 |
| **標準分析** | 2-5 分鐘 | ~1.9-4.7 GB | 平衡速度與精度 |
| **專業測試** | 5-10 分鐘 | ~4.7-9.4 GB | 最高精度、長時間穩定追蹤 |

---

## 🏗️ 架構設計

### 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                        用戶瀏覽器                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  React 前端應用 (localhost:3005)                     │  │
│  │  ├─ 頻譜分析器 UI                                     │  │
│  │  ├─ GPS 記錄與分析 UI                               │  │
│  │  ├─ ADS-B/ISM 解碼 UI                               │  │
│  │  └─ 裝置管理 UI                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      Python 後端服務                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  統一後端 API (localhost:5001)                       │  │
│  │  ├─ 裝置自動檢測                                   │  │
│  │  ├─ 記錄管理                                       │  │
│  │  └─ 檔案處理                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  GNSS-SDR 橋接器 (localhost:8766)                   │  │
│  │  ├─ 即時位置追蹤                                   │  │
│  │  └─ 處理狀態串流                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         ↕ Serial/USB API          ↕ 文件系統
┌─────────────┐              ┌──────────────────┐
│   SDR 裝置   │              │   GNSS-SDR       │
│ ├─ TinySA   │              │   (專業處理)     │
│ ├─ RTL-SDR  │              └──────────────────┘
│ └─ SDRPlay  │
└─────────────┘
```

### 技術棧

**前端：**
- React 18 - 現代化的使用者介面框架
- Web Serial API - 串口通訊
- WebUSB API - USB 裝置直接控制
- Canvas/WebGL - 高效能訊號視覺化
- WebSocket - 即時資料串流

**後端：**
- Python 3.8+ - 核心處理邏輯
- FastAPI/Flask - RESTful API 服務
- NumPy - 訊號處理計算
- SciPy - 科學計算與 FFT
- OpenCV - 影像處理

**專業工具：**
- GNSS-SDR - 專業 GNSS 訊號處理
- SoapySDR - 統一 SDR API 抽象層
- SDRPlay API - SDRPlay 裝置直接控制

---

## ⚙️ 進階配置

### 自訂 GNSS-SDR 參數

編輯 `sdrplay-gps/gnss_config.txt`：

```ini
[GNSS-SDR]
; 接收機配置
Receiver.default=GNSS-SDR
SignalsSource.fs_hz=2048000
SignalSource.implementation=File_Signal_Source

; 訊號跟蹤
Tracking.dump=true
Tracking.dump_filename=../data/track_ch_
```

### 調整頻譜分析參數

在前端設定頁面可調整：
- **頻率範圍** - 掃描的起始與結束頻率
- **解析度** - FFT 點數（數值越大越精確但越慢）
- **平均次數** - 降低雜訊的平滑次數
- **視窗函數** - Hamming、Blackman、Hann 等

### 後端 API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/devices` | GET | 列出所有可用 SDR 裝置 |
| `/api/start-recording` | POST | 開始訊號記錄 |
| `/api/stop-recording` | POST | 停止記錄 |
| `/api/recordings` | GET | 列出所有記錄 |
| `/api/recordings/{id}` | GET | 獲取記錄詳情 |
| `/api/process/{id}` | POST | 處理記錄與生成分析 |

---

## ❓ 常見問題解答（FAQ）

### ❌ 裝置無法連接

**問題**：瀏覽器無法偵測到 SDR 裝置

**解決方案**：
1. 確認裝置已正確連接並供電
2. 確認使用支援的瀏覽器（Chrome、Edge、Opera）
3. 檢查瀏覽器是否有串口/USB 訪問權限
4. 嘗試重新插入 USB 或更換 USB 埠口
5. 檢查是否有其他程式佔用裝置（如 GQRX、SDR#）

### ⚠️ GNSS-SDR 安裝失敗

**問題**：GNSS-SDR 安裝腳本報錯

**解決方案**：
1. 確認 Xcode Command Line Tools 已安裝（macOS）
  ```bash
  xcode-select --install
  ```
2. 確認 Homebrew 已正確安裝並更新
  ```bash
  brew update && brew upgrade
  ```
3. 手動檢查依賴套件是否安裝完全
  ```bash
  brew list | grep -E 'boost|glog|armadillo'
  ```
4. 查看完整安裝日誌以尋找具體錯誤

### 🐌 處理速度過慢

**問題**：GPS 記錄處理時間過長

**優化建議**：
1. 減少記錄持續時間（嘗試 2 分鐘）
2. 使用 Gypsum 解碼器（較快但精度較低）
3. 確認電腦有足夠 RAM（建議 16GB+）
4. 檢查是否有背景程式佔用資源

### 📊 頻譜圖顯示異常

**問題**：頻譜圖顯示不正常或有雜訊

**解決方案**：
1. 增加平均次數以降低雜訊
2. 調整增益參數
3. 檢查天線連接與位置
4. 嘗試不同的視窗函數
5. 確認裝置工作正常

### 💾 磁碟空間不足

**問題**：GPS 記錄檔案過大

**解決方案**：
1. 減少記錄持續時間
2. 在設定中暫時禁用原始檔案保存
3. 定期清理舊的記錄檔案
4. 將記錄目錄移至較大的磁碟

### 🔧 其他問題

前往 [GitHub Issues](https://github.com/meshuga/web-spectrum/issues) 查看更多問題或提交新問題。

---

## 📝 開發指南

### 開發環境設置

```bash
# 1. Fork 並克隆倉庫
git clone https://github.com/YOUR_USERNAME/web-spectrum.git
cd web-spectrum

# 2. 安裝依賴
npm install
pip3 install -r requirements.txt

# 3. 啟動開發模式
npm start
```

### 可用腳本

| 腳本 | 說明 |
|------|------|
| `npm start` | 啟動開發伺服器（自動重新載入） |
| `npm test` | 執行測試套件 |
| `npm run build` | 建置生產版本 |
| `npm run lint` | 執行程式碼檢查 |
| `npm run deploy` | 部署到 GitHub Pages |

### 專案結構

```
web-spectrum/
├── public/                 # 靜態資源
│   └── index.html
├── src/                    # React 前端原始碼
│   ├── components/        # React 組件
│   ├── pages/             # 頁面組件
│   ├── services/          # API 與業務邏輯
│   └── utils/             # 輔助函數
├── sdrplay-gps/           # Python 後端
│   ├── recording_api_simple.py   # API 伺服器
│   ├── gnss_sdr_bridge.py       # GNSS-SDR 橋接
│   └── ...
├── gnss-sdr/              # GNSS-SDR 安裝腳本
├── requirements.txt       # Python 依賴
└── package.json           # Node.js 依賴
```

### 貢獻指南

我們歡迎所有形式的貢獻！

**貢獻方式：**
- 🐛 報告錯誤
- 💡 提出新功能建議
- 📝 改進文檔
- 🔧 提交程式碼修復
- 🎨 優化 UI/UX
- 🌍 翻譯文檔

**提交 Pull Request：**
1. Fork 本專案
2. 建立功能分支（`git checkout -b feature/AmazingFeature`）
3. 提交變更（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 開啟 Pull Request

請參閱 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 了解更多詳情。

---

## 🗺️ 路線圖

### ✅ 已完成功能
- [x] 基本頻譜分析
- [x] TinySA Ultra 支援
- [x] RTL-SDR 支援
- [x] ADS-B 解碼
- [x] ISM 協定解碼
- [x] GNSS-SDR 整合
- [x] GPS 記錄與分析
- [x] 干擾偵測
- [x] SDRPlay 支援

### 🚧 開發中功能
- [ ] macOS Apple Silicon 原生支援
- [ ] 更多 GNSS 星系支援（QZSS、IRNSS）
- [ ] 進階頻譜分析工具（頻譜估計、調變識別）
- [ ] 雲端處理選項
- [ ] 行動應用版本（React Native）
- [ ] 自動化測試套件

### 📋 計劃中功能
- [ ] 多裝置同時運作
- [ ] 頻譜資料庫記錄與歷史查詢
- [ ] AI 輔助訊號分類
- [ ] 裝置遠程控制
- [ ] 即時協作功能
- [ ] 更多解碼器支援（APRS、DVB-T2 等）
- [ ] 專業測試報告生成

---

## 📚 參考資源

### 📺 YouTube 影片
- [Web (r)evolution in lab electronics? Building a Web Spectrum Analyzer for TinySA Ultra](https://www.youtube.com/watch?v=XeK0TL0F8DI)
- [Signal decoding with TinySA Ultra](https://www.youtube.com/watch?v=bqgmftWSKPc)
- [RTL-SDR signal decoding in a web application](https://www.youtube.com/watch?v=Wm7sMXXT5Xs)

### 📖 專業文檔
- [GNSS-SDR 官方文檔](https://www.gnss-sdr.org/docs/)
- [RTL-SDR Wiki](https://www.rtl-sdr.com/)
- [SDRPlay 官方文檔](https://www.sdrplay.com/docs/)
- [Web Serial API 文檔](https://developer.chrome.com/docs/capabilities/serial)
- [WebUSB API 文檔](https://developer.chrome.com/docs/capabilities/usb)

### 🔗 相關專案
- [GQRX](https://gqrx.dk/) - 開源 SDR 接收軟體
- [SDRangel](https://www.sdrangel.com/) - 進階 SDR 處理軟體
- [GNU Radio](https://www.gnuradio.org/) - 訊號處理框架

---

## 📄 授權條款

本專案採用 [MIT License](LICENSE) 授權。

```
MIT License

Copyright (c) 2024 Meshuga

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 👨‍💻 貢獻者

感謝所有為本專案做出貢獻的開發者！

<a href="https://github.com/meshuga/web-spectrum/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=meshuga/web-spectrum" />
</a>

---

## 🙏 致謝

- [GNSS-SDR 團隊](https://www.gnss-sdr.org/) - 專業 GNSS 處理軟體
- [RTL-SDR 社群](https://www.rtl-sdr.com/) - RTL-SDR 知識與支援
- [SDRPlay](https://www.sdrplay.com/) - 專業 SDR 裝置與 API
- [React 社群](https://react.dev/) - 現代化的 Web 框架

---

## 📮 聯繫我們

- 🐦 **Twitter**: [@web_spectrum](https://twitter.com/web_spectrum)
- 📧 **Email**: support@webspectrum.dev
- 💬 **Discord**: [加入我們的 Discord 社群](https://discord.gg/webspectrum)
- 🐙 **GitHub**: [meshuga/web-spectrum](https://github.com/meshuga/web-spectrum)

---

<div align="center">

**⭐ 如果這個專案對你有幫助，請給我們一顆星！⭐**

Made with ❤️ by Meshuga and Contributors

</div>

---

### 📄 其他語言

- [English](README_EN.md) - 英文
- [繁體中文](README.md) - 繁體中文（本版本）
