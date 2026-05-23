# Contributing to AgriTech v3

## Setup

```bash
git clone https://github.com/your-org/agritech.git
cd agritech_final
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
pip install pytest
```

## Project Layers

| Layer | Folder | Rule |
|-------|--------|------|
| Controllers | `api/` | Thin — parse request, call service, return JSON |
| Business logic | `services/` | No Flask imports, pure Python |
| ML wrappers | `ml_service/` | Always provide a fallback when model file is absent |
| Frontend | `static/js/main.js` | No frameworks, vanilla JS only |

## Running Tests

```bash
pytest tests/test_all.py -v
```

All PRs must keep the test suite at 100% pass rate.

## Code Style

- Python: PEP 8, max line 110 chars, type hints on all functions
- JavaScript: `const`/`let` only, async/await, no global state outside `S` object
- Commits: `feat:` `fix:` `docs:` `test:` `refactor:` prefixes

## Adding a New ML Model

1. Create `ml_service/mymodel.py` with a `predict_X()` function and a fallback
2. Register the file in `ml_service/model_manager.py` `MODEL_FILES` dict
3. Add a validator class in `ml_service/validators.py`
4. Add a route in `api/predict.py`
5. Add tests in `tests/test_all.py`
6. Document in `docs/API_DOCS.md` and `docs/MODELS_GUIDE.md`

## Pull Request Checklist

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] No secrets or API keys in code
- [ ] Fallback works when model file is absent
- [ ] API_DOCS.md updated if endpoints changed
- [ ] No breaking changes to existing response schemas
