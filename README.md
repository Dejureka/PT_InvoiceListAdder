# PT Invoice List Adder

從 Bosch **PT GmbH** 發票（`.pdf` / Outlook `.msg`）擷取欄位，寫入 `PT INV LIST.xlsx`（僅 A–F）。

## 免安裝可攜版（公司環境推薦）

適用：不能跑安裝程式、不能裝 Python，但可以複製資料夾執行。

1. 到 [Releases](https://github.com/Dejureka/PT_InvoiceListAdder/releases) 下載 `PT_InvoiceListAdder_Portable_Win64.zip`
2. 解壓後得到資料夾 `PT_InvoiceListAdder`
3. **整個資料夾**複製到電腦或隨身碟
4. 雙擊 `PT_InvoiceListAdder.exe`
5. 拖入／選擇 `.msg` 或 `.pdf`，指定 `PT INV LIST.xlsx` 路徑後執行

同資料夾內可編輯 `data\lookups.json`（國家／Incoterm／運輸方式對照）。

> 這不是 Setup 安裝檔。若公司防毒攔截未簽章 `.exe`，需請 IT 白名單。

手動觸發打包：GitHub → Actions → **Build portable Windows** → Run workflow。

---

## 開發者：從原始碼執行

```bash
python -m venv venv
venv\Scripts\activate
pip install -e ".[gui]"
python -m pt_invoice_adder --gui
```

### CLI

```bash
python -m pt_invoice_adder --files "invoices" --list "PT INV LIST.xlsx" --dry-run
```

## 欄位對應 A–F

| 欄 | 標題 | 來源 |
|----|------|------|
| A | Invoice Date | Invoice Date dd.mm.yyyy |
| B | Country | Departure country / Incoterm → lookups |
| C | Shipment type | Dispatch type（大寫） |
| D | GMBH INV. | Invoice No. |
| E | total (總件數) | packing total |
| F | gross weight(KG) | packing GW |

不寫入 G–J。重複發票號略過。

寫入時會複製上一列的儲存格格式（類似 Format Painter）；成功新增後會自動用系統預設程式開啟清單檔供檢視。

## 授權

私人專案用途依倉庫設定。
