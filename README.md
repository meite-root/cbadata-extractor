# CBA Data Extractor

A minimal, auditable web application that converts pasted collective-bargaining-agreement text into clause-level legal classifications and contract-level research variables.

The interface exposes every transformation separately:

1. Paste contract text (OCR is deliberately out of scope)
2. Remove non-core material
3. Split into sections
4. Split into sentences
5. Parse grammar
6. Keep Subject-Verb-Object clauses
7. Classify agents
8. Identify modal and verb structure
9. Classify legal type
10. Build contract-level measures
11. Assign worker-right topics

## Outputs

- Provisional metadata with supporting text
- Contract-level clause counts and shares
- Worker, firm, union and manager variables by legal type
- Seven worker-right topic counts and shares
- Clause-level audit records showing the rule applied
- JSON and classified-clause CSV downloads

## Methodology boundary

Steps 2-10 are transparent implementations of the processing logic described in Arold, Ash, MacLeod and Naidu, *Worker Rights in Collective Bargaining*. They are not the authors' private source code.

For Step 11, the paper embedded all worker-right sentences, fitted 30 k-means clusters across its complete corpus, manually labeled those clusters and grouped them into seven broad topics. The published materials available to this project do not include the fitted centroids or complete manual crosswalk. The MVP therefore performs transparent broad-topic assignment using section context and dictionaries. It identifies this approximation in the interface and export.

Metadata extraction and broad NAICS assignment are also provisional. Every extracted value includes supporting evidence and should be reviewed.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
pytest -q
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. A demonstration contract is available at `sample/sample_contract.txt`.

If the spaCy English model is unavailable, the app remains functional using a clearly labeled heuristic fallback. Production deployment should install `en_core_web_sm`.

## Droplet deployment

On the already-created Ubuntu droplet:

```bash
cd /opt
git clone git@github.com:meite-root/cbadata-extractor.git
cd cbadata-extractor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
pytest -q
```

Install the service:

```bash
cp deploy/cba-data-extractor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cba-data-extractor
systemctl status cba-data-extractor
```

Edit `deploy/nginx.conf` and replace `YOUR_DROPLET_IP_OR_DOMAIN`, then:

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/cba-data-extractor
ln -s /etc/nginx/sites-available/cba-data-extractor /etc/nginx/sites-enabled/cba-data-extractor
nginx -t
systemctl restart nginx
```

The API limits pasted text to approximately two million characters. Contract text is processed in memory and is not persisted by the application.

