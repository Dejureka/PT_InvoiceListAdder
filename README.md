# PT Invoice List Adder

從 Bosch **PT GmbH** 發票（`.pdf` / Outlook `.msg`）擷取欄位，並附加到 `PT INV LIST.xlsx`。

Extract Bosch PT GmbH invoice fields from `.msg`/`.pdf` and append to **PT INV LIST.xlsx**.

## 安裝 / Install

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e /path/to/PT_InvoiceListAdder
# 或 / or:
pip install -r requirements.txt
export PYTHONPATH=src             # 若未 editable install
```

選用 GUI 依賴（CustomTkinter、拖放）：

```bash
pip install "pt-invoice-adder[gui]"
# 或 pip install customtkinter tkinterdnd2
```

## 執行 GUI

```bash
python -m pt_invoice_adder
# 或
python -m pt_invoice_adder --gui
```

- 可拖放 PDF/MSG/資料夾（需 `tkinterdnd2`；沒有也能用「選擇檔案／選擇資料夾」）
- 指定 PT INV LIST.xlsx 路徑
- 設定會存到工作目錄 `config.json`，或 `~/.pt_invoice_adder.json`

## 執行 CLI

```bash
python -m pt_invoice_adder \
  --files "/path/to/invoices" "/path/to/a.msg" \
  --list "/path/to/PT INV LIST.xlsx" \
  --dry-run
```

去掉 `--dry-run` 即實際寫入。輸出為 JSON 列，並顯示 `added` / `skipped`。

## 欄位對應 A–F（工作表1）

| 欄 | 標題 | 來源 |
|----|------|------|
| A | Invoice Date | `Invoice Date dd.mm.yyyy` |
| B | Country | Departure country / Incoterm 地名 → `lookups.json` COO |
| C | Shipment type | Dispatch type（大寫）；空白則依毛重查表 |
| D | GMBH INV. | Invoice No. |
| E | total (總件數) | packing `total : N` |
| F | gross weight(KG) | packing NW/GW 列之毛重 |

重複的 **GMBH INV.（欄 D）** 會略過不寫入。

## 編輯 lookups.json

路徑：`data/lookups.json`

- `incoterms`：Incoterm 清單（用於 `FCA PLACE` 等列）
- `coo`：`{"full":"Malaysia","code":"MY"}` 精確對應
- `ship_type`：`{"type":"Sea","weight_kg":100}` — 取 **≤ 毛重** 的最大門檻（等同 Excel XLOOKUP -1）

## PyInstaller 範例

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name PT_InvoiceListAdder \
  --add-data "data/lookups.json:data" \
  --hidden-import=extract_msg \
  --hidden-import=pdfminer \
  src/pt_invoice_adder/__main__.py
```

Windows 的 `--add-data` 請改用 `data/lookups.json;data`。

## 測試

```bash
pip install pytest
pytest /path/to/PT_InvoiceListAdder/tests -q
```

## 限制

- GUI 需要系統套件 **tkinter**（Debian/Ubuntu：`sudo apt install python3-tk`）。無 GUI 環境請用 CLI。
- 拖放（DnD）為**選用**依賴 `tkinterdnd2`；未安裝時「選擇檔案／選擇資料夾」仍可用。
- CustomTkinter 為選用；否則使用標準 tkinter。
- PDF 文字依 pypdf，失敗時改用 pdfminer；掃描影像 PDF 無文字層時無法擷取。
- 僅附加 A–F；Delivery No. / others / File / B/L 請手動填。
