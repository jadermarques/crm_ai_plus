---
description: Registrar todas as alterações realizadas em um arquivo de log
---

# Regra de Registro de Alterações (Changelog)

Ao concluir qualquer alteração solicitada pelo usuário, SEMPRE registre em `/home/jader/projects/crm_ai_plus/.agent/changelog.md`:

## Formato de Registro (com indentação)

```markdown
## [DATA] às [HORA]
**Prompt:** [Resumo do que foi solicitado]

    **Modelo:** [Nome do modelo utilizado]

    **Tempo de Execução:** [Tempo aproximado]

    **Arquivos Alterados:**
        - [AÇÃO] `caminho/do/arquivo.py`

    **Resumo das Alterações:**
        [Descrição breve do que foi feito]

---
```

**Ações possíveis:** CRIADO, MODIFICADO, EXCLUÍDO

## Exemplo

```markdown
## 2026-01-11 às 23:30
**Prompt:** Adicionar campo de URL externa na integração Chatwoot-Meta

    **Modelo:** Claude (claude-sonnet-4-20250514)

    **Tempo de Execução:** ~5 minutos

    **Arquivos Alterados:**
        - MODIFICADO `src/core/integration_chatwoot_meta.py`
        - MODIFICADO `src/frontend/views/int_chatwoot_meta.py`

    **Resumo das Alterações:**
        Adicionada coluna `webhook_external_url` na tabela de configuração e campo no formulário para configurar URL externa do webhook.

---
```

## Instruções

1. Adicione novos registros NO TOPO do arquivo (mais recente primeiro)
2. Use o horário atual do sistema
3. Mantenha a INDENTAÇÃO (4 espaços) para os detalhes do prompt
4. Seja conciso no resumo
5. Liste TODOS os arquivos afetados
