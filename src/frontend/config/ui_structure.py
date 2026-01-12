from __future__ import annotations

# Constantes para evitar duplicação de literais
_LABEL_ACOES = "Ações"

MODULES = [
    {
        "id": "principal",
        "label": "Principal",
        "icon": "📌",
        "apps": [
            {"id": "overview", "label": "Visão Geral"},
        ],
    },
    {
        "id": "bot_studio",
        "label": "Bot Studio",
        "icon": "🤖",
        "apps": [
            {"id": "bots", "label": "Bots"},
            {"id": "bot_prompts", "label": "Prompts"},
            {"id": "bot_configs", "label": "Configurações"},
            {"id": "bot_monitoring", "label": "Monitoramento"},
            {"id": "bot_tests", "label": "Testes"},
            {"id": "bot_simulator", "label": "Simulador"},
        ],
    },
    {
        "id": "ai_agents",
        "label": "Agentes de IA",
        "icon": "🧠",
        "apps": [
            {"id": "agents", "label": "Agentes"},
            {"id": "agent_prompts", "label": "Prompts"},
            {"id": "agent_configs", "label": "Configurações de agentes"},
            {"id": "agent_monitoring", "label": "Monitoramento de agentes"},
            {"id": "agent_tests", "label": "Testes de agentes"},
        ],
    },
    {
        "id": "ia_rag",
        "label": "IA e RAG",
        "icon": "📚",
        "apps": [
            {"id": "rag_management", "label": "Gerenciamento RAG"},
            {"id": "rag_configs", "label": "Configurações RAG"},
            {"id": "ia_management", "label": "Gerenciamento de IA"},
            {"id": "ia_configs", "label": "Configurações de IA"},
        ],
    },
    {
        "id": "dashboards",
        "label": "Dashboard / Relatórios",
        "icon": "📊",
        "apps": [
            {"id": "dash_main", "label": "Principal"},
            {"id": "dash_analysis", "label": "Análises"},
            {"id": "dash_reports", "label": "Relatórios"},
        ],
    },
    {
        "id": "management",
        "label": "Gestão",
        "icon": "🛠️",
        "apps": [
            {"id": "users", "label": "Usuários"},
            {"id": "modules", "label": "Módulos"},
            {"id": "apps", "label": "Aplicações"},
            {"id": "permissions", "label": "Permissões"},
            {"id": "prompt_management", "label": "Gestão de Prompts"},
            {"id": "codification_prompts", "label": "Prompts Codificação"},
            {"id": "chatwoot_params", "label": "Parâmetros Chatwoot"},
            {"id": "backup_logs", "label": "Backup/Logs"},
            {"id": "system_configs", "label": "Configurações do Sistema"},
        ],
    },
    {
        "id": "tests",
        "label": "Testes",
        "icon": "🧪",
        "apps": [
            {"id": "tests_management", "label": "Gerenciamento dos Testes"},
            {"id": "tests_execution", "label": "Execução de Testes"},
        ],
    },
    {
        "id": "external_connections",
        "label": "Conexões Externas",
        "icon": "🔌",
        "apps": [
            {"id": "chatwoot_connection", "label": "Conexão Chatwoot"},
        ],
    },
    {
        "id": "integracoes",
        "label": "Integrações",
        "icon": "🔗",
        "apps": [
            {"id": "int_chatwoot_meta", "label": "Int. Meta"},
            {"id": "int_chatwoot_google", "label": "Int. Google Ads"},
        ],
    },
]

PLACEHOLDER_CONTENT = {
    "bots": {
        "desc": "Em breve: lista de bots, status e últimas execuções.",
        "sections": [
            {"title": "Bots", "body": "- Bot A (ativo)\n- Bot B (em configuração)\n- Bot C (pausado)"},
            {"title": _LABEL_ACOES, "body": "Criar bot, editar fluxos, clonar bot."},
        ],
    },
    "bot_prompts": {
        "desc": "Catálogo de prompts dos bots com versões Dev/Prod.",
        "sections": [
            {"title": "Sugestões", "body": "Revise prompts críticos, teste antes de publicar."},
            {"title": _LABEL_ACOES, "body": "Criar prompt, duplicar, publicar para produção."},
        ],
    },
    "bot_configs": {
        "desc": "Configurações do Bot Studio: integrações e parâmetros.",
        "sections": [
            {"title": "APIs e Tokens", "body": "Tokens de Chatwoot/LLM, webhooks, variáveis globais."},
            {"title": "Eventos", "body": "Assinaturas de eventos, retentativa e limites de taxa."},
        ],
    },
    "bot_monitoring": {
        "desc": "Monitoramento de bots: métricas e logs.",
        "sections": [
            {"title": "Métricas", "body": "Execuções hoje, taxa de erro, latência média."},
            {"title": "Timeline", "body": "Últimos eventos e alertas (mock)."},
        ],
    },
    "bot_tests": {
        "desc": "Testes de bots com mensagens de exemplo.",
        "sections": [
            {"title": "Runner", "body": "Envie mensagem de teste para um bot e veja a resposta."},
            {"title": "Histórico", "body": "Resultados recentes com status e duração."},
        ],
    },
    "agents": {
        "desc": "Lista de agentes de IA e seus papéis.",
        "sections": [
            {"title": "Agentes", "body": "Agente A (suporte), Agente B (vendas), Agente C (triagem)."},
            {"title": _LABEL_ACOES, "body": "Criar agente, editar habilidades, ativar/desativar."},
        ],
    },
    "agent_prompts": {
        "desc": "Prompts específicos de agentes, com versões e tags.",
        "sections": [
            {"title": "Gestão", "body": "Prompts por agente, ambientes Dev/Prod, histórico de versões."},
        ],
    },
    "agent_configs": {
        "desc": "Configurações de agentes: modelo, temperatura e ferramentas.",
        "sections": [
            {"title": "Modelo e Temperatura", "body": "Seleção de modelo, temperatura, max tokens."},
            {"title": "Ferramentas", "body": "Habilitar/Desabilitar integrações e ações permitidas."},
        ],
    },
    "agent_monitoring": {
        "desc": "Monitoramento de agentes: uso e sucesso.",
        "sections": [
            {"title": "Métricas", "body": "Interações hoje, latência, taxa de sucesso."},
            {"title": "Logs", "body": "Eventos recentes com status (mock)."},
        ],
    },
    "agent_tests": {
        "desc": "Testes de agentes com cenários pré-definidos.",
        "sections": [
            {"title": "Cenários", "body": "Cenário de saudação, roteamento, resposta curta/longa."},
            {"title": "Resultados", "body": "Tabela de execuções com status e duração."},
        ],
    },
    "rag_management": {
        "desc": "Gerenciamento de coleções RAG.",
        "sections": [
            {"title": "Coleções", "body": "Coleção A (10k docs), Coleção B (2k docs), última indexação."},
            {"title": _LABEL_ACOES, "body": "Indexar, pausar, remover coleção (placeholder)."},
        ],
    },
    "rag_configs": {
        "desc": "Configurações RAG: chunk, overlap e embeddings.",
        "sections": [
            {"title": "Parâmetros", "body": "Chunk size, overlap, provedor de embeddings."},
            {"title": "Qualidade", "body": "Notas sobre ajustes finos de recall/precisão (em breve)."},
        ],
    },
    "ia_management": {
        "desc": "Gerenciamento geral de IA (modelos e políticas).",
        "sections": [
            {"title": "Modelos ativos", "body": "Modelo principal, fallback, limites de custo (placeholder)."},
        ],
    },
    "ia_configs": {
        "desc": "Configurações de IA: chaves e limites.",
        "sections": [
            {"title": "Chaves", "body": "OpenAI/LLM: armazenar via .env; aqui apenas exibição segura (mock)."},
            {"title": "Limites", "body": "Rate limits, budgets e políticas (placeholder)."},
        ],
    },
    "dash_main": {
        "desc": "Visão geral de KPIs.",
        "sections": [
            {"title": "KPIs", "body": "Mensagens hoje, bots ativos, latência média (valores mock)."},
        ],
    },
    "dash_analysis": {
        "desc": "Análises e gráficos.",
        "sections": [
            {"title": "Insights", "body": "Gráficos e análises em breve (use line_chart com dados mock se necessário)."},
        ],
    },
    "dash_reports": {
        "desc": "Relatórios e exportações.",
        "sections": [
            {"title": "Relatórios", "body": "Listagem de relatórios e agendamentos (mock)."},
        ],
    },
    "users": {
        "desc": "Gestão de usuários.",
        "sections": [
            {"title": "Lista", "body": "Usuários com e-mail, papel e status (placeholder)."},
            {"title": _LABEL_ACOES, "body": "Convidar, editar papel, ativar/desativar."},
        ],
    },
    "modules": {
        "desc": "Gestão de módulos.",
        "sections": [
            {"title": "Módulos", "body": "Ativar/desativar módulos disponíveis (mock)."},
        ],
    },
    "apps": {
        "desc": "Gestão de aplicações.",
        "sections": [
            {"title": "Aplicações", "body": "Listagem de apps e status (placeholder)."},
        ],
    },
    "permissions": {
        "desc": "Permissões e papéis.",
        "sections": [
            {"title": "Papéis", "body": "Matriz papel x módulo com switches (mock)."},
        ],
    },
    "prompt_management": {
        "desc": "Gestão de prompts globais.",
        "sections": [
            {"title": "Prompts", "body": "Lista com tags e versões (placeholder)."},
        ],
    },
    "codification_prompts": {
        "desc": "Gestão de prompts focados em codificação e desenvolvimento.",
        "sections": [
            {"title": "Bases de Conhecimento", "body": "Snippets e padrões de código (placeholder)."},
            {"title": "Prompts", "body": "Lista de prompts de system/user para dev (placeholder)."},
        ],
    },
    "chatwoot_params": {
        "desc": "Configuração de parâmetros do Chatwoot.",
        "sections": [
            {"title": "Credenciais", "body": "Base URL, account_id, tokens (somente leitura; editar via .env)."},
            {"title": "Webhook", "body": "Status do webhook e URL configurada (placeholder)."},
            {"title": "Teste de conexão", "body": "Em breve: botão para pingar Chatwoot e validar token."},
        ],
    },
    "backup_logs": {
        "desc": "Backup e logs do sistema.",
        "sections": [
            {"title": "Backups", "body": "Exportar/baixar (desabilitado)."},
            {"title": "Logs", "body": "Links para logs recentes (mock)."},
        ],
    },
    "system_configs": {
        "desc": "Configurações do sistema.",
        "sections": [
            {"title": "Ambiente", "body": "URLs e chaves (somente leitura, vindo do .env)."},
        ],
    },
    "tests_management": {
        "desc": "Gerenciamento dos testes.",
        "sections": [
            {"title": "Suites", "body": "Unitários, E2E; status do último run (placeholder)."},
            {"title": "Logs", "body": "Acesso aos logs em logs/tests/."},
        ],
    },
    "tests_execution": {
        "desc": "Execução de testes.",
        "sections": [
            {"title": "Comandos", "body": "`pytest -q` para unitários; `RUN_E2E=1 pytest -q tests/e2e` para E2E."},
            {"title": "Estado", "body": "Botões desabilitados; use terminal para rodar."},
        ],
    },
    "chatwoot_connection": {
        "desc": "Configuração e status da conexão com o Chatwoot.",
        "sections": [
            {"title": "Status", "body": "Em breve: ping ao Chatwoot, verificação de tokens e webhook."},
            {"title": _LABEL_ACOES, "body": "Configurar base URL, token e account_id; testar envio de mensagem."},
        ],
    },
    "int_chatwoot_meta": {
        "desc": "Integração entre Chatwoot e Meta (WhatsApp/Facebook Ads).",
        "sections": [
            {"title": "Configurações", "body": "URL do Chatwoot e Token de API para a integração."},
            {"title": "Webhook", "body": "Endpoint para receber webhooks do Chatwoot e atualizar atributos de anúncios."},
        ],
    },
    "int_chatwoot_google": {
        "desc": "Integração entre Chatwoot e Google Ads.",
        "sections": [
            {"title": "Status", "body": "Em desenvolvimento."},
        ],
    },
}

APP_LABELS = {app["id"]: app["label"] for module in MODULES for app in module["apps"]}
