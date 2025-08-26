# Hotel Rate Tracker (Free MVP)

This repo holds:
- A **Streamlit** dashboard (`dashboard/streamlit_app.py`)
- A simple **pipeline** that writes `data/beckley_rates.json`
- **GitHub Actions** that can run nightly and commit updated data

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app/run_jobs.py      # generates data/beckley_rates.json
streamlit run dashboard/streamlit_app.py
