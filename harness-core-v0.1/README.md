# Fábrica Harness Core V0.1

Núcleo canônico, independente de runtime/provider. O Core preserva contratos e expõe ports; adapters traduzem tecnologias externas sem redefinir identidade, autoridade, política ou estado institucional.

## Verificação

```bash
python -m pip install -e '.[dev]'
pytest
python scripts/export_schemas.py
```
