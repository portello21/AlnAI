# Skill: Supabase Best Practices
- **Escopo**: Padronização de consultas, upserts e tratamento de dados assíncronos.
- **Regras**:
  1. Sempre valide variáveis de ambiente antes de instanciar o cliente.
  2. Utilize upsert atômico para sincronização de estado local e remoto.
  3. Trate exceções de rede com fallback local no SQLite.