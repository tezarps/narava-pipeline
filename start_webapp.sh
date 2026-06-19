#!/bin/bash
cd /Users/admin/Documents/narava-pipeline
exec /opt/homebrew/bin/python3 -m uvicorn webapp.app:app --host 0.0.0.0 --port 7474
