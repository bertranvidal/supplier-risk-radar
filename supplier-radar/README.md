# supplier-radar: technical reference

Overview, architecture and quick start are in the [root README](../README.md). This page lists the commands behind the training pipeline and the evaluation.

All commands run from this folder.

```bash
pip install -r requirements.txt
```

## 1. Training data

The labelled challenge data (`data/Supplier_Risk_1_Training.xlsx`, validation, holdout) and the extra training files (`synthetic.csv`, `neg_news.csv`, `supabase_train.csv`, `claude_labels.csv`) are already in `data/`. Regenerate or extend them with:

```bash
python3 -m radar.synth --n 3000       # synthetic articles from templates, labels by construction -> data/synthetic.csv
python3 fetch_negatives.py --n 800    # generic business news as "not a risk" -> data/neg_news.csv
python3 augment.py                    # paraphrases by back-translation (open translation models, no LLM)
python3 gen_llm_data.py --n 1500      # a local LLM (Ollama) rewrites synthetic news in other styles
python3 export_training.py            # labelled news from Supabase (needs .env)
```

`train_text.py` and the loaders pick up the optional files (`aug_*.csv`, `llm_synth.csv`, ...) automatically when they exist.

## 2. Training

Single model pair, 3 epochs for text and 2 for link, then calibration and the holdout:

```bash
bash train_all_local.sh
```

Full ensemble (3 seeds for each model, probabilities averaged at inference):

```bash
bash train_all.sh                      # measure on the real validation set
bash train_all.sh --with-val           # final version: also trains on validation
bash train_all.sh --with-val --with-holdout   # also trains on the independent holdout
```

Individual models: `python3 train_text.py --epochs 3 --bs 8` and `python3 train_link.py --epochs 2 --bs 8`. Weights are written to `models/` (ignored by git). Set `RADAR_MODELS=<folder>` to use another set. Training uses CUDA when available and CPU otherwise.

## 3. Evaluation and calibration

```bash
python3 evaluate.py --data holdout              # independent holdout (30 articles)
python3 evaluate.py --data val --mode rules     # rules baseline, no models
python3 calibrate.py                            # decision thresholds -> models/thresholds.json
python3 probe.py                                # what each ensemble member says about free text
python3 inspect_run.py data/Supplier_Risk_3_Test.xlsx   # readable sanity-check report
```

The validation set is no longer a clean measure (the synthetic templates were written while looking at it). Use the holdout.

## 4. Running

```bash
python3 run.py <news.xlsx>                         # models (default)
python3 run.py <news.xlsx> --mode rules            # rules baseline
python3 run.py <news.xlsx> --out out/my_result.xlsx
streamlit run dashboard.py                         # dashboard
uvicorn api:app --port 8000                        # API for the React app in frontend/
```

`--mode llm` (few-shot prompting of a local LLM through Ollama) is kept as an experiment; it is not recommended because the LLM can return malformed or invented supplier IDs.

## 5. Monitoring loop

```bash
python3 scraper.py --source all                     # RSS + NewsAPI + GDELT -> Supabase
python3 classify_supabase.py --mode models --unlabeled
python3 notify.py                                   # Slack / email for CRITICAL alerts
python3 labeler.py                                  # manual labelling UI
python3 distill_claude.py --limit 100               # optional: Claude labels (needs ANTHROPIC_API_KEY)
```

Create the tables first with `supabase_schema.sql` and configure `.env` from `.env.example`.
