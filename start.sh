#!/bin/bash
cd /Users/fongyeungwong/Documents/FactorMining-Interviewer
exec python3 -m streamlit run app.py --server.headless true --server.port "${PORT:-8502}"
