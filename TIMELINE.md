# ⏳ Linha do Tempo e Diário de Bordo - Desafio Observabilidade B3

Este documento registra o passo a passo da concepção, arquitetura e desenvolvimento do projeto, servindo como guia para a apresentação técnica.

## 1. Planejamento e Especificação (Spec Kit)
- **Definição do Escopo:** Escolha do **Cenário 2 (Blockbuster Premiere Rush)** focado em resiliência, autorização de streaming e alta performance.
- **Criação do Spec (`spec.md`):** Estabelecidas as diretrizes técnicas, endpoints obrigatórios (`/stream/authorize` e `/metrics`), e os requisitos de observabilidade (métricas RED, logs estruturados em JSON e tracing distribuído).

## 2. Configuração do Repositório e Versionamento
- **Fork e Integração:** Realizado o fork seguro do repositório base para o GitHub pessoal e clonagem local via Cursor.
- **Padrão de Commits:** Adoção rigorosa de *Conventional Commits* em Português (pt-br) para assegurar histórico limpo e rastreável.
- **Primeiro Marco:** Commit da especificação técnica inicial (`docs: adiciona especificacao tecnica do cenario 2`).

## 3. Arquitetura Base (Backend & Clean Code)
- **Framework:** Implementação em **Python com FastAPI** devido à alta performance assíncrona e facilidade de instrumentação.
- **Estrutura Inicial:** Criação do arquivo `main.py` e do gerenciador de dependências (`requirements.txt`).
- **Endpoints Funcionais:** Subida bem-sucedida da rota de autorização simulada de streaming e do endpoint de métricas básicas.
- **Segundo Marco:** Commit da estrutura base do backend (`feat: implementa estrutura base do backend em fastapi com rotas de autorizacao e metricas`).