# ✅ VALIDAÇÃO: Blueprint Monitor

Após implementar o Blueprint de Monitoramento, execute estes testes para validar que tudo está funcionando.

---

## 🧪 Testes Rápidos

### Teste 1: Verificar Imports

```bash
# Verifique se o Python consegue importar sem erros
python -c "from routes import monitor_bp, setup_monitor_blueprint; print('✅ Imports OK')"
```

**Resultado esperado:**
```
✅ Imports OK
```

---

### Teste 2: Verificar Estrutura de Pastas

```bash
# Windows PowerShell
Get-ChildItem routes\

# Linux/Mac
ls -la routes/
```

**Resultado esperado:**
```
Mode                 LastWriteTime         Length Name
────                 ─────────────────         ────── ────
-a----        18/04/2026   15:30             30 __init__.py
-a----        18/04/2026   15:30            250 monitor.py
```

---

### Teste 3: Verificar Arquivos Criados

```bash
# Windows
dir routes\monitor.py

# Linux/Mac
ls -l routes/monitor.py
```

**Resultado esperado:**
```
routes/monitor.py  (250 linhas)
```

---

### Teste 4: Verificar Modificações em app.py

```bash
# Verificar se os imports estão corretos
grep "from routes import monitor_bp" app.py

# Verificar se o blueprint está registrado
grep "app.register_blueprint(monitor_bp)" app.py
```

**Resultado esperado:**
```
from routes import monitor_bp, setup_monitor_blueprint
app.register_blueprint(monitor_bp)
```

---

### Teste 5: Verificar que Rotas Foram Removidas

```bash
# Verificar que @app.route('/') foi removida de app.py
grep "@app.route('/')" app.py
```

**Resultado esperado:**
```
(sem saída - a rota foi movida para o blueprint)
```

---

### Teste 6: Verificar que Rotas Estão no Blueprint

```bash
# Verificar que as rotas estão em routes/monitor.py
grep "@monitor_bp.route" routes/monitor.py
```

**Resultado esperado:**
```
@monitor_bp.route('/')
@monitor_bp.route('/add_channel', methods=['POST'])
@monitor_bp.route('/toggle_mute/<int:id>')
@monitor_bp.route('/delete_channel/<int:id>')
@monitor_bp.route('/force_check')
@monitor_bp.route('/progress')
@monitor_bp.route('/logs')
```

---

## 🚀 Teste de Execução

### Teste 7: Iniciar o Aplicativo

```bash
python app.py
```

**Resultado esperado:**
```
INFO:utils.logging_config:Migração: Tabela 'video_archive' verificada/criada com sucesso.
INFO:utils.logging_config:Migração: Tabela 'summary_queue' verificada/criada.
INFO:utils.logging_config:✅ Blueprint 'monitor_bp' registrado com sucesso
WARNING:root:Inicialização: Telegram não configurado.
 * Running on http://0.0.0.0:5000
 * Press CTRL+C to quit
```

**O quê procurar:**
- ✅ Migração completada
- ✅ Blueprint registrado com sucesso
- ✅ App rodando em 0.0.0.0:5000

---

### Teste 8: Testar URLs no Navegador

Após iniciar o app, acesse estas URLs:

| URL | Esperado |
|-----|----------|
| `http://localhost:5000/` | Página de monitoramento carrega |
| `http://localhost:5000/progress` | Retorna JSON com progresso |
| `http://localhost:5000/logs?full=false` | Retorna últimos 100 logs |

---

## 🔍 Teste Detalhado (Opcional)

### Teste 9: Verificar Logging em Cada Rota

Execute cada rota e verifique se há logging:

1. Acesse `http://localhost:5000/`
   - Verifique no console: vê uma mensagem de log?

2. Acesse `http://localhost:5000/progress`
   - Verifique se retorna JSON válido

3. Acesse `http://localhost:5000/logs`
   - Verifique se retorna um array JSON

---

### Teste 10: Verificar que url_for() Funciona

Se você clicou em um botão que redireciona, verifique se a URL é correta:

```bash
# A rota não deve retornar erro 404
# Deve redirecionar para: http://localhost:5000/
```

---

## 📊 Teste de Cobertura de Funcionalidade

| Funcionalidade | Teste | Status |
|---|---|---|
| Página principal (/) | Acesso visual | [ ] |
| Adicionar canal | Clique no botão | [ ] |
| Silenciar notificações | Clique no botão | [ ] |
| Deletar canal | Clique no botão | [ ] |
| Forçar verificação | Clique no botão | [ ] |
| Ver progresso | Acesso API | [ ] |
| Ver logs | Acesso API | [ ] |

---

## ⚠️ Troubleshooting

### Erro: "No such module 'routes'"

```
ModuleNotFoundError: No module named 'routes'
```

**Solução:**
1. Verifique se `routes/__init__.py` existe
2. Verifique se `routes/monitor.py` existe
3. Certifique-se de estar na pasta raiz do projeto

---

### Erro: "Blueprint is not a class"

```
TypeError: Blueprint is not a class
```

**Solução:**
```python
# Verifique se o import está correto em routes/monitor.py:
from flask import Blueprint
# Não:
from flask.blueprints import Blueprint
```

---

### Erro: "log_path is None"

```
AttributeError: 'NoneType' object has no attribute '...'
```

**Solução:**
Certifique-se de que `setup_monitor_blueprint()` foi chamada ANTES de `app.register_blueprint()`:

```python
if __name__ == '__main__':
    # ... setup ...
    
    # CORRETO:
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    
    # INCORRETO:
    app.register_blueprint(monitor_bp)
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
```

---

### Erro: "Endpoints have the same name"

```
AssertionError: The name 'index' is already registered for endpoint 'index'.
```

**Solução:**
Duas rotas têm o mesmo nome de função. Verifique se não há duplicatas em `app.py` e `routes/monitor.py`.

---

## ✅ Checklist Final

- [ ] Teste 1: Imports OK
- [ ] Teste 2: Estrutura de pastas OK
- [ ] Teste 3: Arquivos criados OK
- [ ] Teste 4: Modificações em app.py OK
- [ ] Teste 5: Rotas removidas de app.py OK
- [ ] Teste 6: Rotas estão em monitor.py OK
- [ ] Teste 7: App inicia sem erros OK
- [ ] Teste 8: URLs acessíveis no navegador OK
- [ ] Teste 9: Logging funciona OK
- [ ] Teste 10: url_for() funciona OK

---

## 🎯 Validação Completa

Se todos os testes passarem:

✅ **Blueprint Monitor está 100% funcional!**

```bash
# Comando final de validação
python -c "
from app import app, monitor_bp
routes = [rule.rule for rule in app.url_map.iter_rules()]
monitor_routes = [r for r in routes if 'monitor' in str(r) or r in ['/', '/add_channel', '/toggle_mute', '/delete_channel', '/force_check', '/progress', '/logs']]
print('✅ Rotas do monitor encontradas:', len(monitor_routes))
for route in sorted(monitor_routes):
    print(f'  - {route}')
"
```

---

## 📞 Próximos Passos

Após validação bem-sucedida:

1. ✅ Commit das mudanças no git
2. 🔄 Testar em ambiente de produção
3. 📋 Criar `routes/config.py` com rota `/update_config`
4. 🎨 Criar `routes/summary.py` com rotas de resumo
5. 📚 Criar `routes/archive.py` com rotas do cofre
6. 🏷️ Criar `routes/auction.py` com rotas de leilões

---

**Data de Conclusão:** 18 de Abril de 2026  
**Status:** ✅ **PRONTO PARA VALIDAÇÃO**
