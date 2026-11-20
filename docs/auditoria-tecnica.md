# Auditoria técnica de integração — 20/11/2026

**Atualização:** as 12 falhas e os 3 erros de encerramento registrados abaixo
foram resolvidos. A suíte completa terminou com **375 aprovados, 5 omitidos,
zero falhas e zero erros**. As omissões exigem uma base PostgreSQL descartável.
O resultado inicial foi mantido como histórico; ver a correção ao fim do documento.

Escopo: contratos FastAPI ↔ Next.js, configuração, documentação, compilação,
regressões isoladas e integridade do Git. Funcionalidades e alterações anteriores
do usuário foram preservadas. Não foram feitos commit, push, migrações,
instalação de dependências ou chamadas pagas a Jev.

## Estado inicial e critérios

Branch `fix/local-engine-history-and-playwright`, quatro commits à frente e zero
atrás da referência upstream local. Havia alterações em onze arquivos de
interface, `docs/frontend.md` não rastreado e capturas locais de revisão visual.
A referência remota não foi atualizada por fetch; essa contagem não certifica o
estado atual do servidor Git.

Critérios: preservar a interface e a extração, corrigir divergências comprovadas,
validar payloads e schemas, atualizar a documentação, compilar as duas rotas,
executar os testes disponíveis e distinguir falhas de aplicação de requisitos
de plataforma indisponíveis. O working tree deve continuar contendo o trabalho
pronto para revisão/commit, sem ser apagado para aparentar limpeza.

Workflow utilizado: `team-codex`, em sequência, com plano, critérios, execução e
verificação. Revisão da skill reutilizada após conferir os três hashes SHA-256
com o manifesto aprovado em `E:\IA\SkillSpector\reports\team-codex-1.0.0-20261119T120157-manifest.json`.
Nenhum runtime externo de agentes foi instalado ou iniciado.

## Problemas corrigidos

| Problema | Correção | Evidência |
| --- | --- | --- |
| Comparação/API-worker ignoravam a credencial Jev do `.env` aceita pelo extractor. | Ambos passaram a usar `src/common/semantic_model.api_key`, mantendo prioridade do ambiente e isolamento das credenciais de testes. | Quatro regressões cobrem arquivo, ambiente, chave de testes e ausência de fallback para produção. |
| Mudanças da URL via `popstate` podiam manter modo e resultado de outra comparação. | Sincronização de `mode` e `comparison`; limpeza de resultados, evidência e erro ao trocar/remover identidade. | Regressão no navegador com API real isolada. |
| A UI dizia que a estratégia semântica não chamava modelos e custava US$0. | Mensagens passaram a refletir o uso opcional de Jev; gastos reais por visita continuam vindo da API. | Regressão no navegador; cálculos de custo existentes preservados. |
| Faltava um exemplo versionado de configuração. | Adicionado `.env.example` sem segredos, distinguindo leitura do `.env` e variáveis que precisam ser exportadas. | Regras de ignore conferidas para raiz e `src/web`. |
| Documentação usava GET para evidências e confundia o proxy com o servidor iniciado pelo comando de desenvolvimento. | Documentados POST com IDs de asserções e uso de `dev:next` para API já iniciada. | Conferência dos routers e dos scripts reais. |
| Temporários de auditoria e revisão visual apareciam como candidatos ao Git. | Ignore restrito a `.pytest-audit*/` e `.taste-skill/ux-review/`. Brief e direção visual versionados foram mantidos. | `git check-ignore`; nenhum arquivo do usuário foi excluído. |

## Documentação

`docs/frontend.md` agora descreve stack e versões, grafo ativo e módulos sem
consumidores atuais, backend e persistência, exportação estática, fluxos HTTP,
payloads, limites, estados, erros, evidências, paginação, ambiente, instalação,
comandos de desenvolvimento/produção e testes. A stack é JavaScript/JSX; não
foi acrescentado TypeScript nem uma migração de contratos.

`README.md` corrige a execução de Next.js contra backend externo e referencia a
documentação. Os detalhes das quatro consultas contratuais continuam em
`docs/contratos/CONTRATO_BACKEND_FRONTEND_ITER1.md`.

## Verificações concluídas

- `npm run build --prefix src/web`: compilação e exportação de `/` e `/compare`
  aprovadas após as correções.
- `npm ls --depth=0 --prefix src/web`: Geist 1.9.2, Next.js 16.3.8, React e
  React DOM 19.3.0, sem dependência direta inválida.
- Testes nativos Node: **24 aprovados**.
- `tests/test_comparison.py`: **26 aprovados**, incluindo as quatro novas
  regressões de configuração. A execução apresentou um aviso de permissão no
  cache pytest preexistente; testes posteriores usam `-p no:cacheprovider`.
- `tests/test_comparison_portal.py`: **5 aprovados juntos** em 62,08 s, nos cenários
  de captura simulada de uma/duas fontes, API real, resultados, evidência POST,
  recarga, `popstate` e importação JSON válida/inválida com detalhe HTTP 422.
- Regressão adicional de mensagens de custo em `test_next_portal.py`: **1 aprovada**.
- Schemas JSON versionados de Input, Output e Presentation: igualdade exata com
  `model_json_schema()` dos modelos atuais.
- Smoke da aplicação FastAPI: `/`, `/compare`, `/compare/`, `/api/health`,
  `/api/docs`, `/api/comparisons/contract` e 12 assets Next.js retornaram 200;
  também conferidos SVGs, OpenAPI com 50 caminhos, erros 404/422 e rotas retiradas 410.
- Compilação Python de `src`, `clean_process`, `tests` e sintaxe Node dos scripts
  de desenvolvimento, configuração Next.js e host de navegador: aprovadas.
- `git diff --check`: aprovado; índice sem conflitos e sem marcadores de merge.
- Inspeção dos 187 arquivos rastreados: nenhuma falha de sintaxe Python nem
  import relativo de frontend não resolvido. Nenhum padrão examinado de chave
  privada/token foi encontrado; essa busca não equivale a certificação de segredos.
- `.env`, `.env.local`, `.env.test`, dependências, build, dados locais e temporários
  estão ignorados; `.env.example` está disponível para versionamento.

## Resultado inicial e pendências registradas na auditoria

A execução ampla de `pytest -q --basetemp .pytest-audit-integration`, iniciada
durante a auditoria, terminou em **339 aprovados, 5 omitidos, 12 falhas e 3 erros
de teardown**, em 1769,38 s. As regressões novas foram verificadas separadamente
com o código final. As verificações isoladas não substituem a aprovação da suíte
inteira no ambiente suportado.

As falhas foram classificadas pelos tracebacks:

| Grupo | Casos e evidência | Situação |
| --- | --- | --- |
| Plataforma Linux | 9 falhas nos módulos `test_browser_connection`, `test_browser_pool`, `test_persistent_service`, `test_seed_delete`, `test_worker_admission_loop`; dependem de `SIGKILL`, `os.killpg`, `/proc`/PSS ou encerramento de processos não validado em Windows. Os 3 erros de teardown vêm de `BrowserPool._stop` chamar `os.killpg` no Windows. | Pendentes de validação/correção no ambiente de execução suportado. A incompatibilidade Windows do motor não foi ocultada com skips ou mocks novos. |
| Tempo/concorrência | `test_scrape_api_persists_discovery_capture_and_jev_results`, `test_parallel_workers_respect_limit_and_depth`, `test_fifty_workers_share_budget_without_mixing_visits_or_expenses`. Na execução ampla em E:, o primeiro excedeu a espera de polling, o segundo não sobrepôs tarefas de 60 ms e o terceiro excedeu a barreira de 20 s. | Os mesmos três testes, sem alterar critérios, passaram isoladamente em **4,79 s**, com temporários em C:. A evidência aponta para sensibilidade ao ambiente de armazenamento/carga; não certifica desempenho de produção. |
| Interações | A suspeita inicial de falha em `test_scrape_actions.py` não se confirmou no resumo final. | As **14 regressões passaram** também na reprodução isolada, em 280,81 s. |

Os avisos da execução ampla foram de permissão no cache pytest preexistente.
Não foram relaxados limites de teste, alteradas heurísticas de extração nem
removidas funcionalidades para transformar esses resultados em aprovação.

O motor tem mecanismos de Linux (`/proc`, PSS, `os.killpg`, sinais e systemd).
O Ubuntu instalado no WSL não iniciou: o próprio WSL informou necessidade de
atualização do kernel. Não foi alterada a configuração do sistema para contornar
esse requisito. As regressões do motor devem ser executadas no ambiente Linux
suportado antes de certificar o push integralmente.

Não foi configurada uma base PostgreSQL descartável nesta auditoria;
essas provas ficam omitidas sem `SCRAPER_TEST_DSN`. Não foi usado o banco de
produção. Os recorridos vivos externos não foram executados.

Não há scripts de lint ou typecheck dedicados no projeto, nem configuração
TypeScript/ESLint. O passo TypeScript exibido pelo Next.js não demonstra tipagem
estática dos payloads JavaScript.

Há arquivos sem consumidores nas rotas atuais; foram documentados e mantidos.
Na auditoria inicial havia uma cópia byte a byte de `src/common/semantic_model.py`
em `tests/legacy/jev_connector.py`, preservada como fixture de regressão histórica.
O complemento abaixo acrescenta configuração somente ao módulo de produção;
a fixture histórica permanece preservada.

O working tree está modificado com trabalho anterior e correções desta auditoria.
Isso é esperado antes do commit e não deve ser descrito como `git status` limpo.
Nenhum commit/push foi efetuado. A conclusão de prontidão depende dos resultados
de suíte abaixo e das validações Linux/PostgreSQL pendentes.

## Complemento solicitado: configurar Jev pela interface

O portal Scrapper e `/compare/` oferecem o painel **Jev**. Sem credencial, o campo
de senha fica disponível para colar e salvar a chave. A gravação atômica ocorre
em `data/secrets/jev.json`, ignorado pelo Git; o arquivo é criado com permissões
0600 em Unix. Não há gravação em armazenamento do navegador, retorno da chave
pela API nem chamada paga para validar durante a gravação.

O leitor compartilhado usa ambiente administrado, chave da interface e `.env`,
nessa ordem. Os processos leem a configuração nas próximas operações sem
reinício. O modo de testes continua usando apenas sua credencial separada.
Uma chave administrada pelo ambiente é indicada como não editável na interface.
Comparações selecionam Jev automaticamente quando a configuração está disponível;
a opção explícita de dados estruturados continua disponível.

Os endpoints GET/PUT `/api/service/credentials/jev` expõem o contrato no OpenAPI,
retornam apenas status e rejeitam escrita cross-site, entrada inválida, conteúdo
excessivo e erros de armazenamento sem refletir a chave enviada. A instalação
continua privada e compartilhada; não foi introduzido um sistema de contas.

Dez testes de backend passaram, cobrindo troca e persistência de chave, leitura
por outro processo, ausência de exposição, rejeições HTTP, prioridade do ambiente,
isolamento de testes e consumo da chave por extractor e worker de comparação.
A suíte direcionada de integração, comparação, interpretação e uso Jev passou
com **47 testes**, incluindo o fluxo de colar/salvar em ambas as telas e iniciar
uma análise em modo Jev. O build final de Next.js e `git diff --check` passaram.
Também passaram duas regressões do portal para erro de extração/retry e resposta
HTTP não JSON, após incluir o novo router no servidor isolado de testes.
Os testes usam chaves fictícias e substituem o provedor; nenhuma chave real foi
solicitada nem feita chamada paga para validar este complemento. As pendências
Linux/PostgreSQL da auditoria anterior permanecem separadas deste fluxo.

## Correção das 12 falhas e dos 3 erros de encerramento

A compatibilidade de processos foi corrigida sem omitir os testes que falhavam:

- `src/persistent/processes.py` mantém grupos POSIX em Linux e usa
  `psutil>=7.2,<8` em Windows para enumerar descendentes, medir memória privada,
  pausar/reanudar e encerrar processos. Referências Windows preservam PID e
  instante de criação para reduzir o risco de atuar sobre um PID reutilizado.
- O pool encerra o host e o Chromium que lhe pertencem, inclusive quando o host
  termina antes do navegador, e fecha arquivos/streams durante a limpeza.
- Cancelar/excluir uma atividade em Windows identifica simultaneamente atividade
  e diretório do store. Não acessa `/proc` nessa plataforma nem encerra workers
  de outra instalação que tenham o mesmo ID de atividade.
- A interrupção individual passou a usar encerramento nativo da árvore no
  Windows; o caminho `taskkill` que não encerrava o processo na execução anterior
  deixou de ser utilizado por essa operação.
- A memória por atividade e por renderer deixou de retornar zero em Windows.
  A métrica é USS nessa plataforma; PSS em Linux foi preservado. As métricas não
  são equivalentes: ver a [documentação psutil 7.2](https://psutil.io/7.2/).
- Os testes simulam encerramento abrupto usando APIs disponíveis na plataforma,
  conservando as verificações de desconexão, isolamento, limite de memória,
  exclusão de histórico e continuidade de outra atividade. A verificação POSIX
  de código `-9` foi mantida; Windows verifica término anormal sem exigir um
  número de sinal POSIX inexistente.
- As três regressões de tempo/concorrência mantêm seus testes e limites
  originais, incluindo 50 workers e a barreira de 20 segundos. A suíte usa
  temporários em C:; o `--basetemp` em E: da auditoria inicial havia introduzido
  latência de gravação suficiente para esgotar os prazos.
- O fixture do portal intercepta somente a solicitação de reinício automático
  do motor. Assim as regressões de UI não iniciam um daemon real contra a fila
  da instalação. Captura, API, persistência e comportamento de workers continuam
  cobertos pelos testes próprios, inclusive com processos e Chromium reais.

Validação direcionada: **82 testes aprovados, zero falhas e zero erros** nos oito
módulos afetados. Duas novas regressões com processos reais verificam o término
dos descendentes, a preservação de um processo independente e a seleção conjunta
por atividade/store; ambas passaram. Também passou a regressão de recursos
Linux baseada em fixtures. O ajuste final de interrupção por memória foi
verificado novamente junto das duas regressões de isolamento: **3 aprovados**.

`psutil 7.2.2` foi instalado somente em `.venv` do projeto; os pacotes globais não
foram alterados. O requisito foi incluído em `requirements.txt`.

Validação completa em Windows: **375 aprovados e 5 omitidos**, em 1080,73 s.
O JUnit confirma 380 casos, zero falhas e zero erros. Os cinco omitidos são os
testes PostgreSQL, sem DSN de base descartável. Nenhum teste foi omitido por
incompatibilidade de plataforma, e nenhum limite de tempo foi aumentado.
Na suíte completa, os três casos de tempo/concorrência levaram respectivamente
0,546 s (API), 0,303 s (dois workers) e 3,436 s (cinquenta workers).
Também passaram o **build de produção do Next.js**, os **24 testes JavaScript**,
`git diff --check` e a conferência de índice sem conflitos. A validação do runtime Linux/systemd e de PostgreSQL
real não foi feita nesta execução Windows.

## Ajuste de interação no modal Jev

O controle de credencial dentro de `ProcessingSettings` utiliza um grupo sem
formulário próprio. O campo não participa como `required` da validação do
formulário externo; salvar por botão ou Enter não confirma parâmetros nem fecha
o modal. Enter vazio não envia requisição, e a validação dos limites numéricos
continua ativa. Os testes conferem o mesmo modal, limites e interpretação
preservados, exatamente um PUT e nenhuma execução iniciada ao salvar.

As três regressões finais de clique/Enter/validação passaram; o build e os 24
testes JavaScript também passaram. A tela de Atividade teve a referência de
callback corrigida e passou no teste de regressão. O smoke no localhost abriu
o modal e a tela de Atividade sem erros JavaScript nem escritas na API.
A API e o motor foram iniciados para revisão local em `http://localhost:8787`.

## Correção da captura real de duas URLs

As duas falhas apresentadas na interface eram `ERR_NETWORK_ACCESS_DENIED`,
confirmadas nas visitas da auditoria. API e worker haviam herdado um contexto
que permitia localhost, mas bloqueava a rede externa. Ambos foram reiniciados
com acesso de rede aprovado pela plataforma; nenhuma proteção de certificado,
regra de domínio ou heurística de extração foi desativada.

O backend passou a preservar diagnósticos seguros por fonte/etapa, incluindo
causas de rede, DNS, TLS, navegador indisponível, timeout e HTTP de erro. A UI
mostra essas mensagens e as inclui na contagem de diagnósticos, inclusive para
falhas históricas e para uma fonte que falhe numa comparação parcial.

Validações desta correção:

- **35 testes aprovados** de comparação/captura: incluem dois cenários com
  worker, Chromium, servidor HTTP local e processamento reais. Duas páginas
  genéricas produzem resultados; uma página 404 preserva o resultado da outra
  fonte e apresenta diagnóstico HTTP 404.
- **10 regressões de interface aprovadas**, incluindo falha de uma ou das duas
  fontes e exibição do motivo de rede em lugar de resultados vazios.
- **24 testes JavaScript**, build e `git diff --check` aprovados.
- As duas URLs fornecidas pelo usuário retornaram HTTP 200 no Chromium e
  concluíram captura/processamento no localhost, com resultados nas duas fontes.
  Evidência: comparação `f89eba5fdd9944a393d28483b352cfeb`.
- Um segundo par público, `https://example.org/` e `https://www.python.org/`,
  também concluiu o fluxo real: comparação `29c6f3b047514fd4a261abdebf139069`.
- O navegador confirmou resultados visíveis e diagnósticos históricos visíveis,
  sem erros JavaScript. API e motor permaneceram online.

As verificações públicas usaram dados estruturados, uma visita por fonte e
reconhecimento local desativado, para isolar captura/transporte de chamadas a
Jev. Não se afirma que qualquer página contenha preços, avaliações ou campos
comerciais interpretáveis: respostas sem evidência continuam não respondíveis.

### Validação da extração isolada

O erro `ERR_NETWORK_ACCESS_DENIED` da Farmashop na tela `Extraer` estava salvo
no recorrido `b78fe95598c642a4b60ffbc266f331bf`, iniciado às 12:22 UTC,
antes do reinício dos serviços com acesso de rede às 12:28 UTC. O histórico
foi preservado. Uma nova solicitação real a `POST /api/extract`, com a mesma
URL, concluiu às 12:40 UTC: uma visita aprovada, zero falhas, 22 blocos
estruturados e evidências HTML/captura salvas. Recorrido:
`6e2b975385204e658867cfb8408dd62b`.

O smoke com Chromium confirmou a mensagem `Extracción finalizada.`, o conteúdo
da Farmashop visível, ausência de banner de erro e persistência do resultado
após recarregar, sem erros JavaScript. A correção é do contexto de rede do
serviço local; não foi necessária alteração adicional no extrator.
