---
description: Regra para garantir que novas funcionalidades tenham testes automatizados
---

# Regra "Zero Nova Feature Sem Teste"

Para garantir a estabilidade e qualidade do código, **toda nova funcionalidade** de backend ou integração deve ser acompanhada de seu respectivo teste automatizado.

## Diretrizes

1.  **Localização:** Os testes devem ser criados na pasta `tests/`.
2.  **Escopo:** Implemente pelo menos o teste do "Caminho Feliz" (Happy Path), que garante que a funcionalidade executa corretamente com dados válidos.
3.  **Execução:** Verifique se o teste passa executando `pytest`.

## Exemplo

Se criar `src/backend/api/nova_funcionalidade.py`, crie `tests/test_nova_funcionalidade.py`.

```python
# tests/test_nova_funcionalidade.py
from src.backend.api.nova_funcionalidade import minha_funcao

def test_minha_funcao_happy_path():
    resultado = minha_funcao(dados_validos)
    assert resultado == esperado
```

## Checklist

- [ ] Arquivo de teste correspondente criado/atualizado em `tests/`
- [ ] Teste de "Happy Path" implementado
- [ ] `pytest` executado com sucesso para o novo teste
