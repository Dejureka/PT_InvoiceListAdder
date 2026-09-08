#!/bin/bash
export DISPLAY=:5
export PYTHONPATH=/workspace/PT_InvoiceListAdder/src
cd /workspace/PT_InvoiceListAdder
exec /workspace/venv/bin/python launch_gui.py
